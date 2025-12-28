import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 (修改版) =================
# 从环境变量中读取账号密码
# os.environ.get 意思是从系统的环境变量里找这就叫 'ALTR_EMAIL' 的东西
# 如果找不到，就使用后面空字符串 "" 作为默认值
USER_EMAIL = os.environ.get("ALTR_EMAIL")
USER_PASSWORD = os.environ.get("ALTR_PASSWORD")

LOGIN_URL = "https://console.altr.cc/sign-in"
# ===================================================

def run_auto_claim():
    print(">>> [启动] 正在初始化 GitHub Actions 环境...")
    
    # 检查是否获取到了账号密码
    if not USER_EMAIL or not USER_PASSWORD:
        print(">>> [错误] 未检测到账号或密码，请检查 GitHub Secrets 设置！")
        return

    # 设置浏览器选项 - 服务器运行必备设置
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式：不显示界面，因为服务器没有屏幕
    options.add_argument("--disable-gpu") # 禁用 GPU 加速，服务器通常不需要
    options.add_argument("--no-sandbox") # 禁用沙盒，Linux 环境下运行 Chrome 必须项
    options.add_argument("--disable-dev-shm-usage") # 解决资源受限问题
    options.add_argument("--window-size=1920,1080") # 设置虚拟屏幕大小，防止布局错乱

    # 安装并启动浏览器驱动
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # --- 登录流程 ---
        print(f">>> [登录] 访问页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)

        # 等待邮箱输入框
        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
        )
        print(">>> [登录] 输入账号...")
        email_input.clear()
        email_input.send_keys(USER_EMAIL)

        password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        print(">>> [登录] 输入密码...")
        password_input.clear()
        password_input.send_keys(USER_PASSWORD)

        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        print(">>> [登录] 提交登录...")
        submit_btn.click()

        # --- 跳转与签到 ---
        print(">>> [导航] 等待跳转并寻找 Rewards 链接...")
        # 增加等待时间，服务器网络可能波动
        rewards_link = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[@href='/rewards']"))
        )
        print(">>> [导航] 点击进入 Rewards 页面...")
        rewards_link.click()

        print(">>> [签到] 检查按钮状态...")
        # 定位全宽按钮
        claim_button = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.w-full"))
        )

        btn_text = claim_button.text
        # 获取 disabled 属性，如果存在则返回 "true"，否则返回 None
        is_disabled = claim_button.get_attribute("disabled")

        print(f">>> [状态] 按钮文字: {btn_text}, 是否禁用: {is_disabled}")

        if "Claimed today" in btn_text or is_disabled:
            print(">>> [结果] ✅ 今天已经签到过了，无需操作。")
        else:
            print(">>> [动作] 未签到，正在点击...")
            # 有时候元素被遮挡，使用 JavaScript 强制点击更稳妥
            driver.execute_script("arguments[0].click();", claim_button)
            time.sleep(5) # 等待请求发送
            print(">>> [结果] ✅ 签到指令已发送。")

    except Exception as e:
        print(f">>> [错误] 运行中发生异常: {e}")
        # 在 GitHub Actions 页面可以查看截图（如果配置了上传构件，这里简化处理只打印日志）
        print(driver.page_source) # 打印网页源代码帮助排错

    finally:
        print(">>> [结束] 清理资源...")
        driver.quit()

if __name__ == "__main__":
    run_auto_claim()
