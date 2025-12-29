import os
import time
import sys
# 导入 Selenium 相关库
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

# ================= 配置区域 =================
LOGIN_URL = "https://dash.zampto.net/"
OVERVIEW_URL = "https://dash.zampto.net/overview" 
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        # --- 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        
        pwd_input = None
        try:
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            pwd_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))

        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print(">>> [登录] 点击提交，等待跳转...")

        # --- 验证登录 ---
        login_success = False
        try:
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            login_success = True
            print(f">>> [登录] 登录成功！")
        except TimeoutException:
            if "homepage" in driver.current_url or "overview" in driver.current_url:
                login_success = True
            else:
                raise Exception("Login verification failed")

        if login_success and "overview" not in driver.current_url:
            driver.get(OVERVIEW_URL)
            wait.until(EC.url_contains("overview"))

        # --- 获取服务器列表 ---
        server_links = []
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "server-card")))
            cards = driver.find_elements(By.CLASS_NAME, "server-card")
            print(f">>> [列表] 发现了 {len(cards)} 个服务器卡片。")
            
            for card in cards:
                try:
                    link_element = card.find_element(By.CSS_SELECTOR, "a.btn.btn-primary[href*='server?id=']")
                    href = link_element.get_attribute("href")
                    server_name = card.get_attribute("data-server-name") or "Unknown"
                    if href:
                        print(f"    - 发现服务器: {server_name} (ID: {card.get_attribute('data-server-id')})")
                        server_links.append(href)
                except: pass
        except TimeoutException:
            print(">>> [提示] 未找到服务器卡片。")
            return

        # --- 逐个续费 ---
        print(f">>> [处理] 开始处理 {len(server_links)} 个服务器...")

        for index, link in enumerate(server_links):
            print(f"\n--- 正在处理第 {index + 1} 个服务器 ---")
            driver.get(link)
            
            try:
                # -------------------------------------------------------
                # 【修改点】: 监控 nextRenewalTime (到期时间)
                # -------------------------------------------------------
                expiry_before = ""
                has_expiry_element = False
                try:
                    wait.until(EC.presence_of_element_located((By.ID, "nextRenewalTime")))
                    expiry_element = driver.find_element(By.ID, "nextRenewalTime")
                    expiry_before = expiry_element.text.strip()
                    has_expiry_element = True
                    print(f">>> [状态] 当前剩余时长: {expiry_before}")
                except:
                    print(f">>> [注意] 未找到到期时间元素，无法计算延长时间。")

                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[onclick*='handleServerRenewal'], a.action-button.action-purple")
                ))
                
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                renew_btn.click()
                print(">>> [操作] 点击续费按钮...")
                
                # 处理弹窗
                try:
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    driver.switch_to.alert.accept()
                except TimeoutException:
                    pass
                
                # -------------------------------------------------------
                # 【验证】: 检查 nextRenewalTime 是否变化
                # -------------------------------------------------------
                if has_expiry_element:
                    print(">>> [验证] 正在等待有效期更新 (最多10秒)...")
                    try:
                        # 等待文字发生变化
                        WebDriverWait(driver, 10).until(
                            lambda d: d.find_element(By.ID, "nextRenewalTime").text.strip() != expiry_before
                        )
                        
                        expiry_after = driver.find_element(By.ID, "nextRenewalTime").text.strip()
                        print("------------------------------------------------")
                        print(f"✅ [成功] 续费成功！有效期已更新。")
                        print(f"   变更详情: [{expiry_before}]  -->  [{expiry_after}]")
                        print("------------------------------------------------")
                        
                    except TimeoutException:
                        print("------------------------------------------------")
                        print(f"⚠️ [警告] 10秒内有效期未发生变化。")
                        print(f"   当前仍显示: {expiry_before}")
                        print("------------------------------------------------")
                else:
                    time.sleep(2)
                    print(">>> [完成] 操作已执行 (无法读取有效期)。")
                
            except TimeoutException:
                print(">>> [跳过] 找不到续费按钮。")
            except Exception as e:
                print(f">>> [出错] {e}")

    except Exception as e:
        print(f">>> [失败] {e}")

    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 处理完毕。\n")

def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未设置环境变量 ZAMPTO_ACCOUNTS")
        sys.exit(1)
    
    for account_str in ACCOUNTS_ENV.split(','):
        if ':' in account_str:
            u, p = account_str.strip().split(':', 1)
            run_renewal_for_user(u.strip(), p.strip())

if __name__ == "__main__":
    main()
