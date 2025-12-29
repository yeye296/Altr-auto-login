import time
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
# 获取包含所有账号的环境变量
# 格式要求: 账号1:密码1,账号2:密码2
ACCOUNTS_CONFIG = os.environ.get("ALTR_ACCOUNTS", "")
LOGIN_URL = "https://console.altr.cc/login" 
# ===========================================

def parse_credits(text):
    """
    辅助函数：提取文本中的数字
    例如 '622.9 credits' -> 622.9
    """
    try:
        # 移除 'credits', 逗号和空格，并转为小写处理
        clean_text = text.lower().replace('credits', '').replace(',', '').strip()
        return float(clean_text)
    except:
        return 0.0

def run_one_account(email, password, account_index, total_accounts):
    """
    核心任务函数：处理单个账号的登录和签到
    参数:
    - email: 账号邮箱
    - password: 账号密码
    - account_index: 当前是第几个账号（用于日志显示）
    - total_accounts: 总共有多少个账号
    """
    # 打印当前进度分隔线
    print(f"\n{'='*50}")
    print(f">>> [进度] 正在处理第 {account_index}/{total_accounts} 个账号: {email}")
    print(f"{'='*50}")
    
    # --- 浏览器配置 (每个账号启动一个新的浏览器实例，确保环境隔离) ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") # 无头模式，不显示界面
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 模拟真实浏览器 User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 安装并启动 ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # --- 注入防检测 JS (防止被网站识别为自动化工具) ---
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """
    })

    try:
        # --- 1. 登录流程 ---
        print(f">>> [访问] 打开登录页: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(5) # 等待页面加载

        print(">>> [登录] 定位输入框...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        if len(inputs) < 2:
            print(">>> [错误] 输入框数量不足，登录页面加载异常。")
            return

        # 填入账号
        inputs[0].clear()
        inputs[0].send_keys(email)
        time.sleep(0.5)
        # 填入密码
        inputs[1].clear()
        inputs[1].send_keys(password)
        time.sleep(0.5)

        # 点击登录按钮
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            # 备用定位方式
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        
        driver.execute_script("arguments[0].click();", submit_btn)
        print(">>> [登录] 提交中...")

        # --- 2. 获取初始积分 (验证登录是否成功) ---
        print(">>> [验证] 等待登录并获取初始积分...")
        initial_balance = 0.0
        try:
            # 等待显示积分的元素出现 (最多等待20秒)
            credits_element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
            )
            raw_text = credits_element.text
            initial_balance = parse_credits(raw_text)
            print(f">>> [记录] 初始积分: {initial_balance}")
        except:
            print(">>> [警告] 登录可能失败或未找到积分，将尝试直接访问签到页。")
        
        # --- 3. 执行签到 ---
        print(">>> [导航] 前往 Rewards 页面...")
        driver.get("https://console.altr.cc/rewards")
        time.sleep(5)

        try:
            # 寻找包含 "Claim" 的按钮
            print(">>> [搜索] 正在寻找包含 'Claim' 的按钮...")
            claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Claim')]")
            
            target_button = None
            # 遍历找到可见的按钮
            for btn in claim_buttons:
                if btn.is_displayed():
                    target_button = btn
                    break
            
            # 备用方案：寻找 "Reward" 按钮
            if not target_button:
                claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Reward')]")
                for btn in claim_buttons:
                    if btn.is_displayed():
                        target_button = btn
                        break

            if target_button:
                btn_text = target_button.text
                print(f">>> [状态] 找到按钮，文字内容: [{btn_text}]")

                # 检查按钮状态 (是否已签到或禁用)
                if "Claimed" in btn_text or target_button.get_attribute("disabled"):
                    print(f">>> [结果] ⚪ 账号 {email} 今天已经签到过了。")
                    print(f">>> [统计] 当前总积分: {initial_balance}")
                else:
                    print(">>> [动作] 发现未签到，正在点击...")
                    driver.execute_script("arguments[0].click();", target_button)
                    
                    # 等待签到请求完成
                    print(">>> [等待] 正在提交签到请求 (5s)...")
                    time.sleep(5)
                    
                    # --- 4. 核对结果 ---
                    print(">>> [核对] 刷新页面获取最新积分...")
                    driver.refresh()
                    time.sleep(5) # 等待刷新加载
                    
                    try:
                        new_credits_element = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
                        )
                        final_balance = parse_credits(new_credits_element.text)
                        
                        # 计算增加的积分
                        diff = final_balance - initial_balance
                        
                        print("-" * 30)
                        if diff > 0:
                            print(f">>> [成功] 🎉 签到成功！")
                            print(f">>> [收益] 获得积分: +{diff:.1f}")
                            print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        elif diff == 0:
                             print(f">>> [结果] ⚠️ 按钮已点击但积分未变动。")
                             print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        else:
                            print(f">>> [疑惑] 积分发生异常变动: {diff:.1f}")
                        print("-" * 30)
                        
                    except Exception as e:
                        print(f">>> [警告] 无法读取最新积分，无法验证是否到账。错误: {e}")

            else:
                print(">>> [错误] 页面上没找到任何签到按钮。")

        except Exception as e:
            print(f">>> [错误] 签到流程异常: {e}")

    except Exception as e:
        print(f">>> [崩溃] 账号 {email} 运行异常: {e}")

    finally:
        # 无论成功失败，处理完一个账号后必须关闭浏览器，清理内存
        print(f">>> [结束] 关闭账号 {email} 的浏览器实例")
        driver.quit()

def main():
    """
    主程序入口：解析环境变量并循环处理账号
    """
    print(">>> [系统] 启动多账号签到程序")
    
    # 1. 检查环境变量是否存在
    if not ACCOUNTS_CONFIG:
        print(">>> [错误] 未检测到 ALTR_ACCOUNTS 环境变量！")
        print(">>> [提示] 请设置环境变量，格式: email1:pass1,email2:pass2")
        return

    # 2. 解析账号字符串
    # 先用 ',' 分割成 ["账号1:密码1", "账号2:密码2"]
    account_list_raw = ACCOUNTS_CONFIG.split(',')
    account_list = []

    for item in account_list_raw:
        item = item.strip() # 去除可能存在的空格
        if not item: 
            continue
        
        # 再用 ':' 分割成 [邮箱, 密码]
        if ":" in item:
            parts = item.split(':')
            # 考虑到密码中可能也包含冒号，我们只分割第一个冒号
            # email 是 parts[0], 剩下的部分重新组合成 password (防止密码里有冒号被截断)
            email = parts[0].strip()
            password = item[len(email)+1:].strip()
            
            if email and password:
                account_list.append((email, password))
            else:
                print(f">>> [跳过] 格式错误的账号项: {item}")
        else:
            print(f">>> [跳过] 无法解析的账号项 (缺少冒号): {item}")

    total_count = len(account_list)
    print(f">>> [系统] 成功解析到 {total_count} 个账号，准备开始任务...")

    # 3. 循环执行任务
    for index, (email, pwd) in enumerate(account_list):
        # index 从 0 开始，我们显示时加 1 比较友好
        run_one_account(email, pwd, index + 1, total_count)
        
        # 两个账号之间休息一下，防止被系统判定为并发攻击
        if index + 1 < total_count:
            print(">>> [冷却] 等待 5 秒后切换下一个账号...")
            time.sleep(5)

    print("\n>>> [系统] 所有账号处理完毕。")

if __name__ == "__main__":
    main()
