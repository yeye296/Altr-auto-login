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
from selenium.common.exceptions import TimeoutException

# ================= 配置区域 =================
# 登录地址
LOGIN_URL = "https://dash.zampto.net/"

# 从环境变量中获取账号信息
# 格式要求：账号1:密码1,账号2:密码2
# GitHub Secrets 变量名建议为: ZAMPTO_ACCOUNTS
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")

# ===========================================

def run_renewal_for_user(username, password):
    """
    针对单个用户执行：登录 -> 获取列表 -> 续费
    """
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 配置 Chrome (GitHub Actions 专用设置) ---
    options = webdriver.ChromeOptions()
    # 必须开启无头模式，因为 GitHub 服务器没有显示器
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    # 设置窗口大小，防止某些元素因窗口太小被隐藏
    options.add_argument('--window-size=1920,1080')
    # 伪装 User-Agent，防止被简单的反爬虫拦截
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # 初始化浏览器
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20) # 设置最长等待20秒

    try:
        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # 智能查找用户名输入框 (尝试查找 name 为 email, username 或 user 的框)
        # CSS选择器解释: input[name='email'] 意思是找到 name 属性等于 email 的 input 标签
        # 逗号表示 "或者"
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='email'], input[name='username'], input[name='user']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        
        # 查找密码输入框
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.clear()
        pwd_input.send_keys(password)
        
        # 点击登录按钮
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        print(">>> [登录] 提交表单，等待跳转...")

        # 验证是否登录成功 (URL 包含 overview 或 dashboard)
        try:
            wait.until(EC.url_matches(r"overview|dashboard"))
            print(">>> [登录] 登录成功！")
        except TimeoutException:
            print(f">>> [错误] 登录超时或失败，当前标题: {driver.title}")
            # 如果失败直接抛出错误，跳过此账号后续步骤
            raise Exception("Login failed")

        # --- 3. 获取服务器列表 ---
        # 策略：先找到所有详情页链接，存入列表，避免页面刷新导致元素失效
        server_links = []
        # 查找所有包含 server?id= 的 Manage 按钮
        buttons = driver.find_elements(By.CSS_SELECTOR, "a[href*='server?id=']")
        
        for btn in buttons:
            href = btn.get_attribute("href")
            # 去重并确保有效
            if href and href not in server_links:
                server_links.append(href)
        
        print(f">>> [检测] 账号 {username} 下发现 {len(server_links)} 个服务器。")

        # --- 4. 逐个续费 ---
        for link in server_links:
            print(f"--- 正在处理服务器: {link} ---")
            driver.get(link)
            
            try:
                # 定位续费按钮
                # 使用你提供的特征：class包含 action-button 且 onclick 包含 handleServerRenewal
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.action-button[onclick*='handleServerRenewal']")
                ))
                
                # 滚动到可见区域
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                
                renew_btn.click()
                print(">>> [操作] 点击了续费按钮")
                
                # 处理可能出现的“确定”弹窗
                try:
                    WebDriverWait(driver, 3).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 接受弹窗: {alert.text}")
                    alert.accept()
                except TimeoutException:
                    pass # 没有弹窗则继续
                
                print(">>> [成功] 续费指令已发送 (或无需确认)")
                time.sleep(2) # 缓冲时间
                
            except TimeoutException:
                print(">>> [跳过] 未找到续费按钮 (可能已续费或无需续费)")
            except Exception as e:
                print(f">>> [出错] 单个服务器处理出错: {e}")

    except Exception as e:
        print(f">>> [失败] 账号 {username} 处理过程中发生异常: {e}")
        # 在 GitHub Actions 输出中打印页面源码以便调试（如果需要）
        # print(driver.page_source[:500]) 

    finally:
        driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")

def main():
    # 检查环境变量是否存在
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未检测到环境变量 'ZAMPTO_ACCOUNTS'。")
        print(">>> 请在 GitHub Settings -> Secrets and variables -> Actions 中添加。")
        sys.exit(1)

    # 解析账号字符串 "user1:pass1,user2:pass2"
    account_list = ACCOUNTS_ENV.split(',')
    
    print(f">>> [系统] 检测到 {len(account_list)} 个待处理账号。")
    
    for account_str in account_list:
        if ':' not in account_str:
            print(f">>> [警告] 账号格式错误 (缺少冒号): {account_str}")
            continue
            
        username, password = account_str.strip().split(':', 1)
        # 执行单个账号的任务
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()
