import time
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def type_like_human(element, text, min_delay=0.05, max_delay=0.15):
    """사람처럼 타이핑하는 함수"""
    for char in text:
        element.send_keys(char)
        # 키 입력 사이에 랜덤한 지연 시간 추가
        time.sleep(random.uniform(min_delay, max_delay))

def login_and_type_blog_post():
    # 크롬 드라이버 설정 및 시작
    print("브라우저를 시작합니다...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    
    try:
        # 네이버 로그인 페이지 열기
        print("네이버 로그인 페이지로 이동합니다...")
        driver.get("https://nid.naver.com/nidlogin.login")
        
        # 로그인 대기 (사용자가 수동으로 로그인)
        print("네이버에 수동으로 로그인해주세요. 로그인 후 30초 동안 기다립니다...")
        
        # 30초 동안 로그인 대기 (사용자가 직접 로그인)
        for i in range(30, 0, -1):
            print(f"로그인 대기 중... {i}초 남음")
            time.sleep(1)
            
            # 로그인 완료 확인 (네이버 메인 페이지 URL로 확인)
            if "naver.com" in driver.current_url and "nidlogin" not in driver.current_url:
                print("로그인이 감지되었습니다!")
                break
        
        # 블로그 글쓰기 페이지로 이동
        print("블로그 글쓰기 페이지로 이동합니다...")
        driver.get("https://blog.naver.com/rxd0119")
        time.sleep(3)
        
        # 글쓰기 버튼 클릭
        try:
            write_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_write, .link_write, a[href*='PostWrite.naver']"))
            )
            write_button.click()
            print("글쓰기 버튼을 클릭했습니다.")
        except Exception as e:
            print(f"글쓰기 버튼을 찾을 수 없습니다: {e}")
            print("글쓰기 페이지로 직접 이동합니다.")
            driver.get("https://blog.naver.com/PostWrite.naver?blogId=rxd0119")
        
        # 글쓰기 페이지 로딩 대기
        print("글쓰기 페이지 로딩을 기다립니다...")
        time.sleep(5)
        
        # iframe으로 전환 (에디터는 iframe 내부에 있을 가능성이 높음)
        try:
            # 모든 iframe 찾기
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"총 {len(iframes)}개의 iframe을 찾았습니다.")
            
            # 에디터 iframe 찾기
            for i, iframe in enumerate(iframes):
                print(f"iframe {i+1} 검사 중...")
                iframe_id = iframe.get_attribute("id") or ""
                iframe_class = iframe.get_attribute("class") or ""
                
                if "Editor" in iframe_id or "editor" in iframe_id.lower() or "se_" in iframe_class:
                    print(f"에디터 iframe을 찾았습니다. ID: {iframe_id}, Class: {iframe_class}")
                    driver.switch_to.frame(iframe)
                    
                    # 타겟 요소 찾기 시도
                    try:
                        # 지정된 선택자로 찾기
                        target_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "#SE-f9f7dd4d-8ed8-4a59-ab50-5951f7d4bf71 > span.se-placeholder.__se_placeholder.se-ff-nanumgothic.se-fs15.se-placeholder-focused"))
                        )
                        print("지정된 선택자로 요소를 찾았습니다.")
                    except Exception:
                        print("지정된 선택자로 요소를 찾을 수 없습니다. 다른 방법을 시도합니다.")
                        
                        # 대체 선택자로 찾기 시도
                        try:
                            target_element = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".se-component.se-text, .se-text-paragraph, div[contenteditable='true']"))
                            )
                            print("대체 선택자로 요소를 찾았습니다.")
                        except Exception as e:
                            print(f"본문 입력 영역을 찾을 수 없습니다: {e}")
                            # 다음 iframe 시도
                            driver.switch_to.default_content()
                            continue
                    
                    # 텍스트 입력
                    sample_text = "안녕하세요! 네이버 블로그 자동화 테스트 중입니다. 이 텍스트는 자동으로 입력되고 있습니다. 셀레니움을 사용한 자동화 입력 테스트입니다."
                    print("텍스트를 입력합니다...")
                    
                    try:
                        # 요소 클릭 먼저 시도
                        target_element.click()
                        time.sleep(1)
                        
                        # 사람처럼 타이핑
                        type_like_human(target_element, sample_text)
                        print("텍스트 입력이 완료되었습니다.")
                        break
                    except Exception as e:
                        print(f"텍스트 입력 실패: {e}")
                        
                        # 대체 방법: ActionChains 사용
                        try:
                            print("ActionChains으로 시도합니다...")
                            actions = ActionChains(driver)
                            actions.move_to_element(target_element).click().perform()
                            time.sleep(1)
                            
                            for char in sample_text:
                                actions.send_keys(char).perform()
                                time.sleep(random.uniform(0.05, 0.15))
                            
                            print("ActionChains로 텍스트 입력 완료")
                            break
                        except Exception as e2:
                            print(f"ActionChains 실패: {e2}")
                            driver.switch_to.default_content()
                else:
                    print(f"이 iframe은 에디터가 아닙니다.")
            
            # 모든 iframe 확인 후 요소를 찾지 못한 경우
            driver.switch_to.default_content()
            print("본문 입력을 위해 다른 방법을 시도합니다...")
            
            # 페이지 전체에서 contenteditable 요소 찾기
            try:
                editable_elements = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                print(f"{len(editable_elements)}개의 편집 가능한 요소를 찾았습니다.")
                
                for element in editable_elements:
                    try:
                        element.click()
                        time.sleep(1)
                        type_like_human(element, "이 요소에 텍스트를 입력해봅니다.")
                        print("편집 가능한 요소에 텍스트를 입력했습니다.")
                    except Exception as e:
                        print(f"이 요소 입력 실패: {e}")
            except Exception as e:
                print(f"편집 가능한 요소를 찾을 수 없습니다: {e}")
                
        except Exception as e:
            print(f"iframe 처리 중 오류 발생: {e}")
        
        # 브라우저 유지 (사용자가 직접 종료할 때까지)
        print("브라우저가 열려 있습니다. 종료하려면 Ctrl+C를 누르세요.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        # 프로그램 종료 시 드라이버 정리
        driver.quit()

if __name__ == "__main__":
    login_and_type_blog_post() 