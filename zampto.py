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
# 强制指定概览页地址
OVERVIEW_URL = "https://dash.zampto.net/overview" 
# 从环境变量获取账号密码
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    """
    执行单个用户的续费操作
    参数:
      username: 用户名
      password: 密码
    """
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 浏览器配置 ---
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new') # 无头模式，不显示浏览器界面
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    # 模拟真实浏览器 User-Agent，防止被拦截
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        # 安装并启动 Chrome 驱动
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30) # 设置全局等待时间为30秒

        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # 输入账号
        print(">>> [登录] 正在输入账号...")
        # 等待输入框出现 (支持 identifier, email 或 username 字段名)
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        print(">>> [登录] 账号输入完毕")
        
        # 智能等待密码框
        pwd_input = None
        try:
            # 方案A: 尝试直接找密码框 (等2秒)
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            # 方案B: 找不到则点击“下一步”
            print(">>> [登录] 进入两步验证模式，点击下一步...")
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            next_btn.click()
            print(">>> [登录] 等待密码框加载...")
            pwd_input = wait.until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )

        # 输入密码
        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1) # 稍作停顿，模拟人工
        
        # 提交登录
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        print(">>> [登录] 点击提交，等待跳转...")

        # --- 3. 验证登录 & 强制跳转 (核心修复) ---
        login_success = False
        try:
            # 等待 URL 变成 overview 或 homepage
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            login_success = True
            print(f">>> [登录] 登录成功！当前页面: {driver.current_url}")
        except TimeoutException:
            # 【双重保险】如果超时了，再检查一次当前 URL
            current_url = driver.current_url
            if "homepage" in current_url or "overview" in current_url:
                print(f">>> [登录] 判定超时但检测到 URL 已变更: {current_url}，视为成功。")
                login_success = True
            else:
                print(f">>> [错误] 登录彻底超时，当前停留: {current_url}")
                try: 
                    print(f"    提示: {driver.find_element(By.CSS_SELECTOR, '.error, [role=alert]').text}") 
                except: pass
                raise Exception("Login verification failed")

        # 只要登录成功，就强制跳转到概览页
        if login_success:
            if "overview" not in driver.current_url:
                print(f">>> [导航] 正在强制跳转至服务器列表页: {OVERVIEW_URL}")
                driver.get(OVERVIEW_URL)
                # 等待概览页加载
                wait.until(EC.url_contains("overview"))
                print(">>> [导航] 已到达概览页")

        # --- 4. 获取服务器列表 ---
        server_links = []
        try:
            print(">>> [列表] 正在扫描服务器卡片...")
            # 等待至少一个 server-card 出现，最多等15秒
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "server-card")))
            
            # 找到所有的卡片元素
            cards = driver.find_elements(By.CLASS_NAME, "server-card")
            print(f">>> [列表] 发现了 {len(cards)} 个服务器卡片。")
            
            for card in cards:
                try:
                    # 在当前卡片内查找 Manage 按钮
                    link_element = card.find_element(By.CSS_SELECTOR, "a.btn.btn-primary[href*='server?id=']")
                    href = link_element.get_attribute("href")
                    
                    # 获取服务器名字
                    server_name = card.get_attribute("data-server-name") or "Unknown"
                    
                    if href:
                        print(f"    - 发现服务器: {server_name} (ID: {card.get_attribute('data-server-id')})")
                        server_links.append(href)
                except Exception as loop_e:
                    print(f"    - [警告] 解析某张卡片时出错: {loop_e}")

        except TimeoutException:
            print(">>> [提示] 未找到 'server-card' 元素，可能该账号下没有服务器。")

        # --- 5. 逐个续费 ---
        if not server_links:
            print(">>> [结束] 没有需要处理的服务器。")
            return

        print(f">>> [处理] 开始处理 {len(server_links)} 个服务器的续费任务...")

        for index, link in enumerate(server_links):
            print(f"\n--- 正在处理第 {index + 1} 个服务器 ---")
            print(f">>> [跳转] 进入详情页: {link}")
            driver.get(link)
            
            try:
                # -------------------------------------------------------
                # 【步骤 1】: 获取操作前的“上次续费时间”，用于判断是否变化
                # -------------------------------------------------------
                time_before = ""
                has_time_element = False
                try:
                    # 等待一下元素加载
                    wait.until(EC.presence_of_element_located((By.ID, "lastRenewalTime")))
                    time_element = driver.find_element(By.ID, "lastRenewalTime")
                    time_before = time_element.text.strip()
                    has_time_element = True
                    # 这里不再打印当前时间，以免干扰视线
                except Exception as e:
                    print(f">>> [注意] 未找到 lastRenewalTime 元素，将仅依赖弹窗检查。")

                # -------------------------------------------------------
                # 【步骤 2】: 查找并点击续费按钮
                # -------------------------------------------------------
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[onclick*='handleServerRenewal'], a.action-button.action-purple")
                ))
                
                # 滚动到按钮位置
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                
                print(">>> [操作] 点击 'Renew Server' 按钮...")
                renew_btn.click()
                
                # -------------------------------------------------------
                # 【步骤 3】: 处理可能出现的弹窗 (Alert)
                # -------------------------------------------------------
                try:
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 捕捉到信息: {alert.text}")
                    alert.accept() # 点击确定
                    print(">>> [弹窗] 已点击确认")
                except TimeoutException:
                    pass # 没有弹窗则继续
                
                # -------------------------------------------------------
                # 【步骤 4】: 验证结果并获取【剩余时长】
                # -------------------------------------------------------
                if has_time_element:
                    print(">>> [验证] 正在等待数据更新...")
                    try:
                        # 循环检查，直到 lastRenewalTime 的文字发生变化，代表操作生效了
                        WebDriverWait(driver, 10).until(
                            lambda d: d.find_element(By.ID, "lastRenewalTime").text.strip() != time_before
                        )
                        
                        # === 核心修改：这里获取 nextRenewalTime (剩余时长) ===
                        # 找到 ID 为 nextRenewalTime 的元素，它的内容例如 "1 day 23h 54m"
                        expiry_element = driver.find_element(By.ID, "nextRenewalTime")
                        expiry_duration = expiry_element.text.strip()

                        print("------------------------------------------------")
                        print(f"✅ [成功] 续费成功！")
                        print(f"   [结果] 续费后有效期: {expiry_duration}")
                        print("------------------------------------------------")
                        
                    except TimeoutException:
                        print("------------------------------------------------")
                        print(f"⚠️ [警告] 10秒内数据未发生变化。")
                        print(f"   可能原因: 1. 续费失败 2. 已达续费上限 3. 网页响应慢")
                        print("------------------------------------------------")
                else:
                    # 如果找不到时间元素，只能盲等
                    print(">>> [完成] 操作已执行 (因无法读取时间元素，无法确认最终结果)。")
                    time.sleep(2)
                
            except TimeoutException:
                print(">>> [跳过] 未在页面上找到续费按钮 (可能已经续费过了)。")
            except Exception as e:
                print(f">>> [出错] 处理该服务器时发生未知错误: {e}")

    except Exception as e:
        print(f">>> [失败] 账号 {username} 发生全局错误: {e}")
        if driver:
             try:
                print(f">>> [调试] 当前 URL: {driver.current_url}")
             except: pass

    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")

def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未检测到环境变量 'ZAMPTO_ACCOUNTS'。")
        sys.exit(1)
    
    account_list = ACCOUNTS_ENV.split(',')
    print(f">>> [系统] 共检测到 {len(account_list)} 个待处理账号。")

    for account_str in account_list:
        if ':' not in account_str:
            continue
        username, password = account_str.strip().split(':', 1)
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()
