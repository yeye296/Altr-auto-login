import time
import os
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
USER_EMAIL = os.environ.get("ALTR_EMAIL")
USER_PASSWORD = os.environ.get("ALTR_PASSWORD")
BASE_URL = "https://console.altr.cc/" 
# ===========================================

def run_auto_claim():
    print(">>> [启动] 正在初始化 GitHub Actions 环境...")
    
    if not USER_EMAIL or not USER_PASSWORD:
        print(">>> [错误] 未检测到账号或密码，请检查 GitHub Secrets 设置！")
        return

    # --- 浏览器配置 ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    })

    try:
        print(f">>> [访问] 正在打开首页: {BASE_URL}")
        driver.get(BASE_URL)
        time.sleep(5) 

        print(f">>> [定位] 当前页面 URL: {driver.current_url}")

        # --- 智能登录判断 ---
        if "sign-in" not in driver.current_url and "dashboard" not in driver.current_url:
            print(">>> [导航] 未自动跳转登录页，尝试寻找登录入口...")
            try:
                login_btn = driver.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in')] | //button[contains(text(), 'Sign in')]")
                print(">>> [动作] 找到登录按钮，点击跳转...")
                driver.execute_script("arguments[0].click();", login_btn)
                time.sleep(3)
            except:
                print(">>> [警告] 没找到明显的登录按钮，尝试强制跳转 /sign-in ...")
                driver.get("https://console.altr.cc/sign-in")
                time.sleep(3)

        # --- 执行登录 ---
        try:
            print(">>> [登录] 寻找输入框...")
            email_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            print(">>> [登录] 输入账号...")
            email_input.clear()
            for char in USER_EMAIL:
                email_input.send_keys(char)
                time.sleep(0.05)

            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys(USER_PASSWORD)
            time.sleep(0.5)

            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            print(">>> [登录] 点击提交...")
            driver.execute_script("arguments[0].click();", submit_btn)
            
            WebDriverWait(driver, 20).until(lambda d: "sign-in" not in d.current_url)
            print(f">>> [跳转] 登录成功，当前 URL: {driver.current_url}")

        except Exception as e:
            print(f">>> [登录检查] 登录流程遇到问题 (或已登录): {str(e)[:100]}")

        # --- 寻找 Rewards ---
        print(">>> [导航] 准备进入 Rewards 页面...")
        driver.get("https://console.altr.cc/rewards")
        time.sleep(5) 

        try:
            print(">>> [签到] 扫描签到按钮...")
            claim_button = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.w-full"))
            )
            
            btn_text = claim_button.text
            is_disabled = claim_button.get_attribute("disabled")
            
            print(f">>> [状态] 按钮文字: [{btn_text}]")

            if "Claimed today" in btn_text or is_disabled:
                print(">>> [结果] ✅ 任务完成：今日已签到。")
            else:
                print(">>> [动作] 发现未签到，点击按钮...")
                driver.execute_script("arguments[0].click();", claim_button)
                time.sleep(5)
                print(">>> [结果] ✅ 签到指令已执行。")
                
        except Exception as e:
            print(f">>> [失败] 无法找到签到按钮或页面加载失败。")
            # --- 修复部分在这里 ---
            print(f">>> [调试] 页面标题: {driver.title}")
            try:
                # 先获取文本，在外面处理掉换行符，避开 f-string 的语法限制
                raw_body = driver.find_element(By.TAG_NAME, 'body').text[:300]
                clean_body = raw_body.replace('\n', ' ')
                print(f">>> [调试] 页面内容摘要: {clean_body}")
            except:
                pass

    except Exception as e:
        print(f">>> [致命错误] 脚本崩溃: {e}")

    finally:
        print(">>> [结束] 关闭浏览器")
        driver.quit()

if __name__ == "__main__":
    run_auto_claim()
