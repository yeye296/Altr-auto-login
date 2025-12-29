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
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 增强版 Chrome 配置 (针对 GitHub Actions 优化) ---
    options = webdriver.ChromeOptions()
    # 使用新版无头模式 (更稳定，渲染更接近真实浏览器)
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--remote-debugging-port=9222') # 增加调试端口，防止端口冲突
    # 关键：移除“自动化控制”特征，防止被网站轻易识别
    options.add_argument('--disable-blink-features=AutomationControlled')
    # 伪装 User-Agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        # 自动下载并匹配最新版驱动
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 25) # 稍微延长等待时间

        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # --- 调试：打印当前页面标题，检查是否被 Cloudflare 拦截 ---
        print(f">>> [调试] 当前页面标题: {driver.title}")
        
        # 智能查找用户名输入框
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='email'], input[name='username'], input[name='user']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        
        # 查找密码输入框
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.clear()
        pwd_input.send_keys(password)
        
        # 点击登录
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        print(">>> [登录] 提交表单，等待跳转...")

        # 验证是否登录成功
        try:
            wait.until(EC.url_matches(r"overview|dashboard"))
            print(">>> [登录] 登录成功！")
        except TimeoutException:
            # 如果超时，打印一下当前 URL，看看是不是还在登录页
            print(f">>> [错误] 登录后未跳转，当前 URL: {driver.current_url}")
            raise Exception("Login timeout")

        # --- 3. 获取服务器列表 ---
        server_links = []
        buttons = driver.find_elements(By.CSS_SELECTOR, "a[href*='server?id=']")
        for btn in buttons:
            href = btn.get_attribute("href")
            if href and href not in server_links:
                server_links.append(href)
        
        print(f">>> [检测] 账号 {username} 下发现 {len(server_links)} 个服务器。")

        # --- 4. 逐个续费 ---
        for link in server_links:
            print(f"--- 正在处理服务器: {link} ---")
            driver.get(link)
            try:
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.action-button[onclick*='handleServerRenewal']")
                ))
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                renew_btn.click()
                print(">>> [操作] 点击了续费按钮")
                
                try:
                    WebDriverWait(driver, 3).until(EC.alert_is_present())
                    driver.switch_to.alert.accept()
                    print(">>> [弹窗] 已确认")
                except TimeoutException:
                    pass
                
                print(">>> [成功] 续费指令已发送")
                time.sleep(2)
            except TimeoutException:
                print(">>> [跳过] 未找到续费按钮")
            except Exception as e:
                print(f">>> [出错] 单个服务器处理出错: {e}")

    except WebDriverException as e:
        # 专门捕获浏览器崩溃/启动失败的错误
        print(f">>> [致命错误] 浏览器驱动异常: {e}")
        if driver:
            # 尝试打印网页源码，帮助判断是被拦截还是白屏
            try:
                print(f">>> [调试] 崩溃时的网页源码(前500字符):\n{driver.page_source[:500]}")
            except:
                pass

    except Exception as e:
        print(f">>> [失败] 账号 {username} 发生逻辑错误: {e}")
        if driver:
             try:
                print(f">>> [调试] 错误时的网页标题: {driver.title}")
             except:
                pass

    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")

def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未检测到环境变量 'ZAMPTO_ACCOUNTS'。")
        sys.exit(1)
    
    account_list = ACCOUNTS_ENV.split(',')
    for account_str in account_list:
        if ':' not in account_str: continue
        username, password = account_str.strip().split(':', 1)
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()
