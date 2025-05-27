import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# 크롬 드라이버 설정 및 시작
print("브라우저를 시작합니다...")
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
driver = uc.Chrome(options=options)

# 네이버 로그인 페이지 열기
print("네이버 로그인 페이지로 이동합니다...")
driver.get("https://nid.naver.com/nidlogin.login")

# 브라우저 유지 (사용자가 직접 종료할 때까지)
print("브라우저가 열렸습니다. 종료하려면 Ctrl+C를 누르거나 이 창을 닫으세요.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("프로그램을 종료합니다.")
    driver.quit() 