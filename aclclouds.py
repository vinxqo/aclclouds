import time
import os
import json
import re
import random
import requests

# 智能环境配置：仅在未设置时才应用默认值
# 这样兼容 GitHub Actions 的 xvfb-run (会自动设置 DISPLAY) 和 Docker 环境
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"
    
if "XAUTHORITY" not in os.environ:
    # 仅当路径存在时才设置，避免在 GitHub Runner (home/runner) 中报错
    if os.path.exists("/home/headless/.Xauthority"):
        os.environ["XAUTHORITY"] = "/home/headless/.Xauthority"

print(f"[DEBUG] Env DISPLAY: {os.environ.get('DISPLAY')}")
print(f"[DEBUG] Env XAUTHORITY: {os.environ.get('XAUTHORITY')}")

from seleniumbase import SB

# ================= 配置区域 =================
PROXY_URL = os.getenv("PROXY", "")  # 代理
EMAIL = os.getenv("EMAIL")  # discord邮箱
PASSWORD = os.getenv("PASSWORD")  # discord密码
TG_TOKEN = os.getenv("TG_TOKEN")  # tg通知token
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # tg通知chat_id

# 目标 URL
LOGIN_URL = "https://dash.aclclouds.com/auth/oauth/discord"
PROJECT_URL = "https://dash.aclclouds.com/projects"
# ===========================================

class AclcloudsRenewal:
    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] [INFO] {msg}", flush=True)

    def human_wait(self, min_s=6, max_s=10):
        """随机模拟人类等待时间"""
        time.sleep(random.uniform(min_s, max_s))

    def move_mouse_human(self, sb):
        """模拟人类鼠标晃动预热"""
        try:
            # 在页面不同位置“晃悠”一下鼠标，打破机器人直线模式
            for _ in range(3):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                sb.slow_click(f"body", force=True) # 借用 slow_click 的移动特性，或者直接用 move_to
                time.sleep(random.uniform(0.5, 1.2))
        except: pass

    def send_telegram_notify(self, message, photo_path=None):
        """发送 Telegram 通知 (带图片)"""
        if not TG_TOKEN or not TG_CHAT_ID:
            self.log("⚠️ 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过推送。")
            return
        
        try:
            if photo_path and os.path.exists(photo_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(photo_path, 'rb') as f:
                    # caption 参数用于发送带文字的图片
                    requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': message}, files={'photo': f})
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': message})
            
            self.log("✅ TG 推送已发送")
        except Exception as e:
            self.log(f"❌ TG 推送失败: {e}")

    def discord_login(self, sb, EMAIL, PASSWORD):
        self.log("🚀 透过discord进行登录")
        time.sleep(5)

        self.log("✏️ 输入账号密码")

        sb.fill('input[name="email"]', EMAIL)
        sb.fill('input[name="password"]', PASSWORD)

        self.log("📤 提交登录")
        sb.click('button[type="submit"]')

        time.sleep(10)

    # ======================
    # OAuth（原逻辑完全不动）
    # ======================
    def oauth_debug(self, sb):

        self.log("🔐 OAuth 页面分析开始")

        for i in range(20):

            self.log(f"🔍 分析 {i+1}/20")
            time.sleep(2)

            try:
                sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
                sb.execute_script("window.scrollTo(0, 0);")

                sb.execute_script("""
                    document.body.scrollTop = document.body.scrollHeight;
                    document.documentElement.scrollTop = document.documentElement.scrollHeight;
                """)

                sb.execute_script("""
                    let all = document.querySelectorAll('*');
                    for (let el of all) {
                        try {
                            if (el.scrollHeight > el.clientHeight) {
                                el.scrollTop = el.scrollHeight;
                            }
                        } catch(e) {}
                    }
                """)

                sb.send_keys("body", Keys.PAGE_DOWN)
                sb.send_keys("body", Keys.PAGE_DOWN)
                sb.send_keys("body", Keys.END)

                try:
                    ActionChains(sb.driver).send_keys(Keys.PAGE_DOWN).perform()
                except:
                    pass

            except:
                pass

            #self.shot(sb, f"oauth_debug_{i}.png", "OAuth状态")

            body = sb.get_text("body").lower()

            if "authorize" in body:
                try:
                    self.log("🟢 检测到 Authorize，尝试点击")

                    els = sb.find_elements("button") + sb.find_elements("a")

                    for el in els:
                        try:
                            if "authorize" in (el.text or "").lower():
                                sb.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});",
                                    el
                                )
                                time.sleep(1)
                                sb.execute_script("arguments[0].click();", el)
                                self.log("✅ 已点击 Authorize")
                                time.sleep(10)
                                break
                        except:
                            pass
                except:
                    pass

            if "client.hnhost.net" in sb.get_current_url():
                self.log("✅ 已跳回目标站点（OAuth完成）")
                return True

        return False

    def get_expiry_time(self, sb):
        selector = ".projects-card-expiry .projects-expiry-value"
        # 等待元素可见（SeleniumBase 内置等待）
        sb.wait_for_element_visible(selector, timeout=10)
        # 获取文本
        return sb.get_text(selector).strip()

    def run(self):
        self.log("=" * 40)
        self.log("🚀 Aclclouds - Renew流程")
        self.log("=" * 40)
        self.log("🎯 正在启动 Chrome 浏览器...")
        
        # 使用 headed=True 强制有头模式渲染到 VNC
        with SB(
            uc=True,            # 启用反检测模式
            test=True, 
            headed=True,        # 关键：强制有头模式
            headless=False,     # 明确禁用 headless
            xvfb=False,         # 禁用内部虚拟显示器，使用系统 DISPLAY
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-position=0,0,--start-maximized",
            proxy=PROXY_URL if PROXY_URL else None
        ) as sb:
            try:
                self.log("✅ 浏览器已启动！")
                
                # ... (省略中间步骤，保持原有逻辑不变) ...
                
                # 1. IP 检测
                self.log("🌍 正在检测出口 IP...")
                try:
                    sb.open("https://api.ipify.org?format=json")
                    ip_val = json.loads(re.search(r'\{.*\}', sb.get_text("body")).group(0)).get('ip', 'Unknown')
                    parts = ip_val.split('.')
                    self.log(f"✅ 当前出口 IP: {parts[0]}.{parts[1]}.***.{parts[-1]}")
                except:
                    self.log("⚠️ IP 检测跳过...")

                # 2. 访问登录首页
                self.log("🔗 访问登录首页...")
                sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=25)
                time.sleep(5)
                self.discord_login(sb, EMAIL, PASSWORD)
                time.sleep(5)
                self.oauth_debug(sb)
                self.log("✅ Discord登录成功")
                time.sleep(5)
                login_screenshot = f"{self.screenshot_dir}/login.png"
                sb.save_screenshot(login_screenshot)
                self.send_telegram_notify("访问登录页面", login_screenshot)
                return

                # 3. 进入Project页面
                self.log("📂 进入Project页面")
                sb.uc_open_with_reconnect(PROJECT_URL, reconnect_time=25)
                time.sleep(5)
                sb.scroll_to_bottom() # 滑动到底部
                #poject_screenshot = f"{self.screenshot_dir}/poject.png"
                #sb.save_screenshot(poject_screenshot)
                #self.send_telegram_notify("访问项目页面", poject_screenshot)

                # 4. 判断是否有Renew按钮
                selector = "button:contains('Renew')"
                self.log("🖱️ 查找Renew按钮")
                time_before = self.get_expiry_time(sb)
                if not sb.is_element_visible(selector):
                    renew_screenshot = f"{self.screenshot_dir}/renew.png"
                    sb.save_screenshot(renew_screenshot)
                    self.send_telegram_notify(f"🎉Aclclouds 自动续期\n🕒当前无需续期\n🚀剩余使用时间：{time_before}", renew_screenshot)
                    return
                # 点击Renew按钮
                self.log("✅ 找到Renew按钮")
                sb.wait_for_element_visible(selector, timeout=10)
                sb.scroll_to(selector)
                time.sleep(5)
                sb.click(selector)
                #renew_screenshot = f"{self.screenshot_dir}/renew.png"
                #sb.save_screenshot(renew_screenshot)
                #self.send_telegram_notify("已点击Renew按钮", renew_screenshot)

                # 5.点击Verify按钮
                selector = ".auth-captcha-checkbox"
                self.log("🖱️ 点击验证按钮")
                sb.wait_for_element_visible(selector, timeout=10)
                # 点击（SeleniumBase 默认自动处理可点击状态）
                self.log("✅ 找到Verify按钮")
                sb.click(selector)
                time.sleep(5)
                time_after = self.get_expiry_time(sb)
                verify_screenshot = f"{self.screenshot_dir}/verify.png"
                sb.save_screenshot(verify_screenshot)
                self.send_telegram_notify(f"🎉Aclclouds 自动续期\n🕒续期前剩余使用时间：{time_before}\n🚀续期后剩余使用时间：{time_after}", verify_screenshot)
                self.log("✅ 流程完毕")

            
            except Exception as e:
                self.log(f"❌ 运行异常: {e}")
                import traceback
                traceback.print_exc()
                sb.save_screenshot(f"{self.screenshot_dir}/error.png")


if __name__ == "__main__":
    AclcloudsRenewal().run()
