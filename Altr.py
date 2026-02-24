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
# 读取多账号变量
# 格式要求: 账号1:密码1,账号2:密码2 (用英文逗号分隔账号，冒号分隔账密)
ACCOUNTS_CONFIG = os.environ.get("ALTR_ACCOUNTS", "")
LOGIN_URL = "https://altare.sh/login" 
# ===========================================

def parse_credits(text):
    """
    【保持原样】提取文本中的数字
    """
    try:
        clean_text = text.lower().replace('credits', '').replace(',', '').strip()
        return float(clean_text)
    except:
        return 0.0

def run_account_task(user_email, user_password, index, total_accounts):
    """
    执行单个账号的任务，逻辑严格照搬原脚本
    """
    print(f"\n{'='*50}")
    print(f">>> [进度] 正在处理第 {index}/{total_accounts} 个账号: {user_email}")
    print(f"{'='*50}")

    # --- 浏览器配置 ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # 注入防检测 JS
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """
    })

    try:
        # --- 1. 登录 (保持原逻辑) ---
        print(f">>> [访问] 打开登录页: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(5)

        print(">>> [登录] 定位输入框...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        if len(inputs) < 2:
            print(">>> [错误] 输入框数量不足，登录页面加载异常。")
            return

        # 填入账号密码
        inputs[0].clear()
        inputs[0].send_keys(user_email)
        time.sleep(0.5)
        inputs[1].clear()
        inputs[1].send_keys(user_password)
        time.sleep(0.5)

        # 提交
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        
        driver.execute_script("arguments[0].click();", submit_btn)
        print(">>> [登录] 提交中...")

        # --- 2. 获取初始积分 (保持原逻辑) ---
        print(">>> [验证] 等待登录并获取初始积分...")
        initial_balance = 0.0
        try:
            credits_element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
            )
            raw_text = credits_element.text
            initial_balance = parse_credits(raw_text)
            print(f">>> [记录] 初始积分: {initial_balance}")
        except:
            print(">>> [警告] 登录可能失败或未找到积分，无法计算增量。")
        
        # --- 3. 执行签到 (严格保持原逻辑) ---
        print(">>> [导航] 前往 Rewards 页面...")
        driver.get("https://altare.sh/billing/rewards/daily")
        time.sleep(5)

        try:
            # 因为 "Claimed" 包含 "Claim"，所以如果已签到，这里也会找到按钮
            claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Claim')]")
            
            target_button = None
            for btn in claim_buttons:
                if btn.is_displayed():
                    target_button = btn
                    break
            
            if not target_button:
                # 备用方案：如果按钮叫 "Reward"
                claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Reward')]")
                for btn in claim_buttons:
                    if btn.is_displayed():
                        target_button = btn
                        break

            # --- 判断逻辑开始 ---
            if target_button:
                btn_text = target_button.text
                

                # 这里是你提到的核心逻辑：如果包含 Claimed，则判定为已签到
                if "Claimed" in btn_text or target_button.get_attribute("disabled"):
                    print(f">>> [结果] ⚪ 今天已经签到过了。")
                    print(f">>> [统计] 当前总积分: {initial_balance}")
                else:
                    # 否则点击签到
                    print(">>> [动作] 发现未签到，正在点击...")
                    driver.execute_script("arguments[0].click();", target_button)
                    
                    print(">>> [等待] 正在提交签到请求 (5s)...")
                    time.sleep(5)
                    
                    # --- 4. 核对结果 ---
                    print(">>> [核对] 刷新页面获取最新积分...")
                    driver.refresh()
                    time.sleep(5)
                    
                    try:
                        new_credits_element = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
                        )
                        final_balance = parse_credits(new_credits_element.text)
                        
                        diff = final_balance - initial_balance
                        
                        print("-" * 30)
                        if diff > 0:
                            print(f">>> [成功] 🎉 签到成功！")
                            print(f">>> [收益] 获得积分: +{diff:.1f}")
                            print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        elif diff == 0:
                             print(f">>> [结果] ⚠️ 按钮已点击但积分未增加 (可能需要更长时间到账)。")
                             print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        else:
                            print(f">>> [疑惑] 积分发生变动: {diff:.1f}")
                        print("-" * 30)
                        
                    except Exception as e:
                        print(f">>> [警告] 无法读取最新积分，无法验证是否到账。错误: {e}")

            else:
                # 只有当既没有 Claim 也没有 Claimed 也没有 Reward 时，才会走到这里
                print(">>> [错误] 页面上没找到任何包含 'Claim' 字样的按钮。")
                print(">>> [调试] 页面包含的按钮文字: ", [b.text for b in driver.find_elements(By.TAG_NAME, "button") if b.text])

        except Exception as e:
            print(f">>> [错误] 签到流程异常: {e}")

    except Exception as e:
        print(f">>> [崩溃] 全局异常: {e}")

    finally:
        print(f">>> [结束] 关闭账号 {user_email} 的浏览器实例")
        driver.quit()

def main():
    print(">>> [系统] 启动多账号签到程序")
    
    # 1. 检查环境变量
    if not ACCOUNTS_CONFIG:
        print(">>> [错误] 环境变量 ALTR_ACCOUNTS 未设置！")
        return

    # 2. 解析账号字符串
    # 逻辑：先按逗号分割账号，再按冒号分割邮箱和密码
    raw_accounts = ACCOUNTS_CONFIG.split(',')
    account_list = []
    
    for item in raw_accounts:
        item = item.strip()
        if not item: continue
        
        # 使用 split(':', 1) 确保只分割第一个冒号，防止密码里也有冒号
        if ":" in item:
            parts = item.split(':', 1)
            if len(parts) == 2:
                account_list.append((parts[0].strip(), parts[1].strip()))
            else:
                print(f">>> [跳过] 格式错误的账号项: {item}")
        else:
            print(f">>> [跳过] 缺少冒号的账号项: {item}")

    total_count = len(account_list)
    print(f">>> [系统] 成功解析到 {total_count} 个账号，准备开始任务...")

    # 3. 循环执行
    for i, (email, pwd) in enumerate(account_list):
        # 这里的 i+1 是为了显示 第1个、第2个...
        run_account_task(email, pwd, i + 1, total_count)
        
        # 两个账号之间增加冷却时间，避免被封 IP
        if i < total_count - 1:
            print(">>> [冷却] 等待 5 秒切换下一个账号...")
            time.sleep(5)

    print("\n>>> [系统] 所有账号处理完毕。")

if __name__ == "__main__":
    main()
