import os
import time
import json
import random
import requests
import re

from playwright.sync_api import sync_playwright


# ================= ENV =================
PROXY_URL = os.getenv("PROXY", "")
COOKIE = os.getenv("COOKIE") # 对应remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d=的cookies
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

LOGIN_URL = "https://dash.aclclouds.com/auth/login"
PROJECT_URL = "https://dash.aclclouds.com/projects"

class AclcloudsRenewal:

    def __init__(self):
        self.debug_dir = "debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def human_wait(self, a=6, b=10):
        time.sleep(random.uniform(a, b))

    # ================= TG =================
    def send_telegram_photo(self, image_path, caption=""):
        try:
            if not TG_TOKEN or not TG_CHAT_ID:
                self.log("⚠️ TG 未配置")
                return

            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"

            with open(image_path, "rb") as f:
                requests.post(
                    url,
                    data={
                        "chat_id": TG_CHAT_ID,
                        "caption": caption[:1000]
                    },
                    files={"photo": f}
                )

            self.log("📨 TG 已发送")

        except Exception as e:
            self.log(f"❌ TG失败: {e}")

    # ================= DEBUG =================
    def dump_debug(self, page, name, msg=""):
        try:
            img = f"{self.debug_dir}/{name}.png"
            html = f"{self.debug_dir}/{name}.html"

            page.screenshot(path=img, full_page=True)

            with open(html, "w", encoding="utf-8") as f:
                f.write(page.content())

            self.log(f"📸 saved: {name}")

            self.send_telegram_photo(
                img,
                f"{name}\n{msg}\n{page.url}"
            )

        except Exception as e:
            self.log(f"❌ debug error: {e}")

    # ================= BLOCK CHECK =================
    def is_blocked(self, page):
        try:
            html = page.content()
            return "Packet blocked" in html or "Click HERE" in html
        except:
            return False

    def get_expiry_time(self, page, timeout=10000):
        locator = page.locator(".projects-card-expiry .projects-expiry-value")    
        locator.wait_for(state="visible", timeout=timeout)
        return locator.inner_text().strip()
        
    # ================= RUN =================
    def run(self):

        self.log("🚀 Aclclouds 自动签到")

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False,
                proxy={"server": PROXY_URL} if PROXY_URL else None,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
            )

            context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            """)
            
            page = context.new_page()

            # ================= IP =================
            self.log("🌍 检查出口IP")
            page.goto("https://api.ipify.org?format=json")
            ip = json.loads(page.text_content("body"))["ip"]
            self.log(f"IP: {ip}")

            # ================= LOGIN =================
            self.log("🔗 进入主站")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            self.human_wait()

            context.add_cookies([
                {
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": COOKIE,
                    "domain": "dash.aclclouds.com",
                    "path": "/"
                }
            ])

            self.log("✅ 注入Cookie成功")
            # ================= Project =================
            self.log("📂 进入Project面板")
            page.goto(PROJECT_URL, wait_until="domcontentloaded")
            self.human_wait()
            #self.dump_debug(page, "project", "project loaded")

            # ================= 点击Renew按钮 =================            
            self.log("🖱️ 点击Renew按钮")
            self.log("🖱️ 查找Renew按钮")
            renew = page.locator("button:has-text('Renew')")
            if renew.count() == 0:
                time_text = self.get_expiry_time(page)
                self.dump_debug(page,"🎉Aclclouds 自动续期",f"🕒当前无需续期\n🚀剩余使用时间：{time_text}")
                return
            renew.wait_for(state="visible", timeout=10000)
            self.log("🖱️ 滚动到Renew按钮")
            renew.scroll_into_view_if_needed()
            self.human_wait()
            self.log("🖱️ 执行点击Renew")
            renew.click(timeout=10000, force=True)
            self.log("🖱️ 已点击Renew按钮")
          
            # ================= 点击Verify按钮 =================
            self.log("🖱️ 点击验证按钮")
            page.click(".auth-captcha-checkbox")
            self.human_wait()
            #self.dump_debug(page, "Verify", "Verify Clicked")
            time_text = self.get_expiry_time(page)
            self.dump_debug(page, "🎉Aclclouds-自动续期", f"🕒续期流程执行完毕\n🚀剩余使用时间：{time_text}")
            self.log("✅ 流程完毕")

            browser.close()


if __name__ == "__main__":
    AclcloudsRenewal().run()
