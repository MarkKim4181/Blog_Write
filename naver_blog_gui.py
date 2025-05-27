import sys
import time
import random
import threading
import json
import os
import undetected_chromedriver as uc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QTextEdit, QProgressBar, QGroupBox, QFormLayout,
                           QMessageBox, QCheckBox, QSpinBox, QDoubleSpinBox,
                           QComboBox, QListWidget, QListWidgetItem, QDialog,
                           QDialogButtonBox, QInputDialog, QMenu, QAction,
                           QSystemTrayIcon, QToolButton, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize, QSettings, QPoint, QRect
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QPalette
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# 설정 파일 관리를 위한 상수
APP_NAME = "NaverBlogAutoTyper"
ORGANIZATION = "BlogAutomation"
SETTINGS_FILE = "naver_blog_settings.json"
ACCOUNTS_FILE = "naver_accounts.json"

class AccountManager:
    """네이버 계정 관리 클래스"""
    def __init__(self):
        self.accounts = []
        self.current_account = None
        self.load_accounts()
    
    def load_accounts(self):
        """저장된 계정 정보 로드"""
        try:
            if os.path.exists(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.accounts = data.get("accounts", [])
                    self.current_account = data.get("current_account", None)
        except json.JSONDecodeError as e:
            print(f"계정 정보 파일 형식 오류: {e}")
            # 파일이 손상된 경우 백업 생성 후 초기화
            if os.path.exists(ACCOUNTS_FILE):
                backup_file = f"{ACCOUNTS_FILE}.backup"
                try:
                    os.rename(ACCOUNTS_FILE, backup_file)
                    print(f"손상된 파일을 {backup_file}으로 백업했습니다.")
                except Exception:
                    pass
            self.accounts = []
            self.current_account = None
        except Exception as e:
            print(f"계정 정보 로드 실패: {e}")
            self.accounts = []
            self.current_account = None
    
    def save_accounts(self):
        """계정 정보 저장"""
        try:
            data = {
                "accounts": self.accounts,
                "current_account": self.current_account
            }
            # 임시 파일에 먼저 저장 후 이름 변경 (안전한 파일 저장)
            temp_file = f"{ACCOUNTS_FILE}.temp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 파일 시스템 동기화
            
            # 기존 파일이 있으면 백업
            if os.path.exists(ACCOUNTS_FILE):
                backup_file = f"{ACCOUNTS_FILE}.bak"
                try:
                    os.replace(ACCOUNTS_FILE, backup_file)
                except Exception:
                    pass
            
            # 임시 파일을 실제 파일로 이름 변경
            os.replace(temp_file, ACCOUNTS_FILE)
            return True
        except Exception as e:
            print(f"계정 정보 저장 실패: {e}")
            return False
    
    def add_account(self, username, password, nickname=""):
        """계정 추가"""
        if not username or not password:
            print("아이디와 비밀번호는 필수입니다.")
            return False
            
        try:
            # 이미 있는 계정인지 확인
            for account in self.accounts:
                if account["username"] == username:
                    account["password"] = password
                    if nickname:
                        account["nickname"] = nickname
                    self.save_accounts()
                    return True
            
            # 새 계정 추가
            new_account = {
                "username": username,
                "password": password,
                "nickname": nickname or username,
                "blogs": []
            }
            self.accounts.append(new_account)
            
            # 현재 계정이 없으면 이 계정을 현재 계정으로 설정
            if self.current_account is None:
                self.current_account = username
            
            return self.save_accounts()
        except Exception as e:
            print(f"계정 추가 실패: {e}")
            return False
    
    def remove_account(self, username):
        """계정 삭제"""
        for i, account in enumerate(self.accounts):
            if account["username"] == username:
                del self.accounts[i]
                
                # 현재 계정이 삭제된 경우 다른 계정으로 변경
                if self.current_account == username:
                    self.current_account = self.accounts[0]["username"] if self.accounts else None
                
                self.save_accounts()
                return True
        return False
    
    def set_current_account(self, username):
        """현재 계정 설정"""
        for account in self.accounts:
            if account["username"] == username:
                self.current_account = username
                self.save_accounts()
                return True
        return False
    
    def get_current_account(self):
        """현재 계정 정보 반환"""
        if not self.current_account:
            return None
            
        for account in self.accounts:
            if account["username"] == self.current_account:
                return account
        return None
    
    def add_blog_to_account(self, username, blog_id):
        """계정에 블로그 추가"""
        for account in self.accounts:
            if account["username"] == username:
                if "blogs" not in account:
                    account["blogs"] = []
                
                # 이미 있는 블로그인지 확인
                for blog in account["blogs"]:
                    if blog["id"] == blog_id:
                        return True
                
                # 새 블로그 추가
                account["blogs"].append({
                    "id": blog_id,
                    "name": blog_id
                })
                self.save_accounts()
                return True
        return False

class WorkerSignals(QObject):
    """브라우저 스레드의 신호를 정의하는 클래스"""
    update_status = pyqtSignal(str)
    browser_ready = pyqtSignal(bool)
    typing_completed = pyqtSignal(bool, str)

class BrowserThread(threading.Thread):
    """백그라운드에서 브라우저를 실행하는 스레드"""
    def __init__(self, username, password, screen_size=None):
        super().__init__()
        self.username = username
        self.password = password
        self.driver = None
        self.signals = WorkerSignals()
        self.daemon = True  # 메인 프로그램 종료 시 같이 종료
        self.typing_speed = (0.05, 0.15)  # 기본 타이핑 속도 (최소, 최대 초)
        self.should_stop = False
        self.screen_size = screen_size  # 화면 크기
        
    def run(self):
        """스레드 실행"""
        try:
            # 브라우저 시작
            self.signals.update_status.emit("브라우저를 시작합니다...")
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            
            # 브라우저 초기 위치 및 크기 설정 (화면 오른쪽 상단)
            if self.screen_size:
                screen_width, screen_height = self.screen_size
                window_width = int(screen_width * 0.6)  # 화면 너비의 60%
                window_height = int(screen_height * 0.9)  # 화면 높이의 90%
                
                # 오른쪽 상단에 위치
                pos_x = screen_width - window_width - 10  # 오른쪽에서 10px 간격
                pos_y = 10  # 상단에서 10px 간격
                
                # 위치 및 크기 설정
                options.add_argument(f"--window-size={window_width},{window_height}")
                options.add_argument(f"--window-position={pos_x},{pos_y}")
            
            # 추가 옵션 설정
            options.add_argument("--disable-gpu")  # GPU 가속 비활성화 (안정성 향상)
            options.add_argument("--no-sandbox")  # 샌드박스 모드 비활성화
            options.add_argument("--disable-dev-shm-usage")  # 공유 메모리 사용 비활성화
            
            try:
                # 현재 설치된 크롬 버전과 호환되도록 version_main 파라미터 설정
                # 136은 현재 설치된 크롬 버전 (136.0.7105.114)
                self.driver = uc.Chrome(options=options, version_main=136)
                self.signals.update_status.emit("브라우저가 성공적으로 시작되었습니다.")
            except Exception as browser_error:
                self.signals.update_status.emit(f"브라우저 초기화 오류: {browser_error}")
                self.signals.browser_ready.emit(False)
                return
            
            # 네이버 로그인 페이지 열기
            self.signals.update_status.emit("네이버 로그인 페이지로 이동합니다...")
            self.driver.get("https://nid.naver.com/nidlogin.login")
            
            # 자동 로그인 시도
            if self.username and self.password:
                self.signals.update_status.emit("로그인 시도 중...")
                
                # 자바스크립트로 로그인 정보 입력 (봇 감지 우회)
                self.driver.execute_script(f"document.getElementsByName('id')[0].value='{self.username}'")
                time.sleep(0.5)
                self.driver.execute_script(f"document.getElementsByName('pw')[0].value='{self.password}'")
                time.sleep(0.5)
                
                # 로그인 버튼 클릭
                try:
                    login_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "log.login"))
                    )
                    login_button.click()
                    self.signals.update_status.emit("로그인 버튼을 클릭했습니다.")
                    
                    # 자동입력 방지 확인
                    time.sleep(2)
                    if "자동입력 방지" in self.driver.page_source or "보안 문자" in self.driver.page_source:
                        self.signals.update_status.emit("보안 문자가 감지되었습니다. 직접 입력해주세요.")
                except Exception as e:
                    self.signals.update_status.emit(f"로그인 버튼 클릭 실패: {e}")
            else:
                self.signals.update_status.emit("아이디와 비밀번호가 비어있습니다. 직접 로그인해주세요.")
            
            # 로그인 완료 대기
            self.wait_for_login()
            
            # 브라우저 준비 완료 신호 전송
            self.signals.browser_ready.emit(True)
            
            # 스레드 종료 전까지 대기
            while not self.should_stop:
                time.sleep(0.5)
                
        except Exception as e:
            error_msg = f"브라우저 스레드 오류: {e}"
            print(error_msg)  # 콘솔에 오류 출력
            self.signals.update_status.emit(error_msg)
            self.signals.browser_ready.emit(False)
        finally:
            if self.should_stop and self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass  # 브라우저 종료 실패 무시
    
    def wait_for_login(self):
        """로그인 완료 대기"""
        self.signals.update_status.emit("로그인 대기 중... 로그인 완료 후 '블로그 이동' 버튼을 클릭하세요.")
        
        # 로그인 성공 여부는 GUI에서 사용자가 직접 확인하도록 함
        return True
    
    def navigate_to_blog(self, blog_id):
        """블로그로 이동"""
        try:
            if not self.driver:
                self.signals.update_status.emit("브라우저가 실행되지 않았습니다.")
                return False
                
            self.signals.update_status.emit(f"블로그 {blog_id}로 이동합니다...")
            self.driver.get(f"https://blog.naver.com/{blog_id}")
            time.sleep(2)
            return True
        except Exception as e:
            self.signals.update_status.emit(f"블로그 이동 실패: {e}")
            return False
    
    def navigate_to_write_page(self, blog_id):
        """글쓰기 페이지로 이동"""
        try:
            if not self.driver:
                self.signals.update_status.emit("브라우저가 실행되지 않았습니다.")
                return False
                
            # 방법 1: 글쓰기 버튼 클릭
            try:
                self.signals.update_status.emit("글쓰기 버튼을 찾는 중...")
                # 사용자가 제공한 정확한 선택자 추가
                write_button_selectors = [
                    "a.col._checkBlock._rosRestrict[href*='postwrite']",
                    "a[href*='postwrite']",
                    "a[onclick*='prf.write']",
                    ".btn_write, .link_write",
                    "a[href*='PostWrite.naver']"
                ]
                
                for selector in write_button_selectors:
                    try:
                        write_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        self.signals.update_status.emit(f"글쓰기 버튼을 찾았습니다: {selector}")
                        write_button.click()
                        self.signals.update_status.emit("글쓰기 버튼을 클릭했습니다.")
                        break
                    except Exception:
                        continue
                else:
                    raise Exception("모든 선택자로 글쓰기 버튼을 찾을 수 없습니다")
                    
            except Exception as e:
                # 방법 2: 직접 URL로 이동
                self.signals.update_status.emit(f"글쓰기 버튼을 찾을 수 없어 직접 URL로 이동합니다: {e}")
                # 사용자가 제공한 정확한 URL 형식 사용
                try:
                    # 새 URL 형식 시도
                    self.driver.get(f"https://blog.naver.com/{blog_id}/postwrite")
                    self.signals.update_status.emit("새 URL 형식으로 이동했습니다.")
                except Exception:
                    # 기존 URL 형식 시도
                    self.driver.get(f"https://blog.naver.com/PostWrite.naver?blogId={blog_id}")
                    self.signals.update_status.emit("기존 URL 형식으로 이동했습니다.")
            
            # 페이지 로딩 대기
            time.sleep(3)
            return True
        except Exception as e:
            self.signals.update_status.emit(f"글쓰기 페이지 이동 실패: {e}")
            return False
    
    def type_text(self, text):
        """에디터에 텍스트 입력"""
        if not self.driver:
            self.signals.update_status.emit("브라우저가 실행되지 않았습니다.")
            self.signals.typing_completed.emit(False, "브라우저가 실행되지 않았습니다.")
            return
            
        try:
            self.signals.update_status.emit("에디터를 찾는 중...")
            
            # iframe 전환 시도
            self.find_and_switch_to_editor_iframe()
            
            # 에디터 요소 찾기
            editor_element = self.find_editor_element()
            
            if editor_element:
                self.signals.update_status.emit("에디터를 찾았습니다. 텍스트 입력을 시작합니다...")
                
                # 방법 1: 직접 입력 방식
                try:
                    # 요소 클릭
                    editor_element.click()
                    time.sleep(0.5)
                    
                    # 타이핑하듯이 텍스트 입력
                    self.type_like_human(editor_element, text)
                    
                    self.signals.update_status.emit("텍스트 입력이 완료되었습니다.")
                    self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                    return
                except Exception as e:
                    self.signals.update_status.emit(f"직접 입력 방식 실패: {e}. 다른 방식을 시도합니다.")
                
                # 방법 2: 자바스크립트 실행
                try:
                    self.signals.update_status.emit("JavaScript로 텍스트 입력을 시도합니다...")
                    # 글자별로 입력 (타이핑 효과)
                    for i, char in enumerate(text):
                        script = f"""
                            var el = arguments[0];
                            if (el.isContentEditable) {{
                                el.textContent = el.textContent + '{char}';
                            }} else if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                                el.value = el.value + '{char}';
                            }}
                        """
                        self.driver.execute_script(script, editor_element)
                        time.sleep(random.uniform(*self.typing_speed))
                        
                        # 진행 상황 업데이트 (10% 단위)
                        if i % max(1, len(text) // 10) == 0:
                            progress = (i / len(text)) * 100
                            self.signals.update_status.emit(f"텍스트 입력 중... {progress:.0f}%")
                    
                    self.signals.update_status.emit("JavaScript로 텍스트 입력이 완료되었습니다.")
                    self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                    return
                except Exception as e:
                    self.signals.update_status.emit(f"JavaScript 입력 실패: {e}. 다른 방식을 시도합니다.")
                
                # 방법 3: ActionChains 사용
                try:
                    self.signals.update_status.emit("ActionChains로 입력을 시도합니다...")
                    actions = ActionChains(self.driver)
                    actions.move_to_element(editor_element).click().perform()
                    time.sleep(0.5)
                    
                    # 텍스트를 한 글자씩 입력
                    for char in text:
                        actions.send_keys(char).perform()
                        time.sleep(random.uniform(*self.typing_speed))
                    
                    self.signals.update_status.emit("ActionChains로 텍스트 입력 완료")
                    self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                    return
                except Exception as e:
                    self.signals.update_status.emit(f"ActionChains 실패: {e}. 다른 방식을 시도합니다.")
                
                # 방법 4: 클립보드 방식 (최후의 수단)
                try:
                    self.signals.update_status.emit("클립보드를 사용한 입력을 시도합니다...")
                    # 클립보드에 텍스트 복사 (JavaScript)
                    self.driver.execute_script(f"""
                        var textarea = document.createElement('textarea');
                        textarea.value = `{text.replace('`', '\\`')}`;
                        document.body.appendChild(textarea);
                        textarea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textarea);
                    """)
                    time.sleep(0.5)
                    
                    # 요소 클릭
                    editor_element.click()
                    time.sleep(0.5)
                    
                    # 붙여넣기 단축키 사용
                    actions = ActionChains(self.driver)
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    
                    self.signals.update_status.emit("클립보드를 사용한 텍스트 입력 완료")
                    self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                    return
                except Exception as e:
                    self.signals.update_status.emit(f"클립보드 입력 실패: {e}")
            else:
                # 다른 방법 시도
                self.signals.update_status.emit("에디터를 찾지 못했습니다. 다른 방법을 시도합니다...")
                self.driver.switch_to.default_content()
                
                # 전체 페이지에서 편집 가능한 요소 찾기
                try:
                    editable_elements = self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true'], textarea, iframe[id*='editor']")
                    if editable_elements:
                        self.signals.update_status.emit(f"{len(editable_elements)}개의 편집 가능한 요소를 찾았습니다.")
                        for element in editable_elements:
                            try:
                                # iframe인 경우 먼저 전환
                                if element.tag_name.lower() == 'iframe':
                                    self.driver.switch_to.frame(element)
                                    editable = self.find_editor_element()
                                    if editable:
                                        element = editable
                                    else:
                                        self.driver.switch_to.default_content()
                                        continue
                                
                                element.click()
                                time.sleep(0.5)
                                self.type_like_human(element, text)
                                self.signals.update_status.emit("텍스트 입력이 완료되었습니다.")
                                self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                                return
                            except Exception:
                                # iframe으로 전환했다면 다시 기본 프레임으로 복귀
                                if element.tag_name.lower() == 'iframe':
                                    self.driver.switch_to.default_content()
                                continue
                except Exception:
                    pass
                
                # ActionChains 사용 시도 (전체 페이지에 대해)
                try:
                    self.signals.update_status.emit("전체 페이지에 ActionChains로 입력을 시도합니다...")
                    actions = ActionChains(self.driver)
                    actions.send_keys(text).perform()
                    self.signals.update_status.emit("ActionChains로 텍스트 입력이 완료되었습니다.")
                    self.signals.typing_completed.emit(True, "텍스트 입력이 완료되었습니다.")
                    return
                except Exception as e:
                    self.signals.update_status.emit(f"모든 입력 방법이 실패했습니다: {e}")
                    self.signals.typing_completed.emit(False, f"텍스트 입력 실패: {e}")
        except Exception as e:
            self.signals.update_status.emit(f"텍스트 입력 중 오류 발생: {e}")
            self.signals.typing_completed.emit(False, f"텍스트 입력 실패: {e}")
    
    def find_and_switch_to_editor_iframe(self):
        """에디터 iframe 찾고 전환"""
        # 먼저 기본 프레임으로 전환
        self.driver.switch_to.default_content()
        
        # iframe 찾기
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        self.signals.update_status.emit(f"{len(iframes)}개의 iframe을 찾았습니다.")
        
        # 에디터 iframe 찾기
        for iframe in iframes:
            try:
                iframe_id = iframe.get_attribute("id") or ""
                iframe_class = iframe.get_attribute("class") or ""
                
                if "Editor" in iframe_id or "editor" in iframe_id.lower() or "se_" in iframe_class:
                    self.signals.update_status.emit(f"에디터 iframe을 찾았습니다: {iframe_id}")
                    self.driver.switch_to.frame(iframe)
                    return True
            except Exception:
                continue
        
        # 첫 번째 iframe 시도
        if iframes:
            try:
                self.driver.switch_to.frame(iframes[0])
                self.signals.update_status.emit("첫 번째 iframe으로 전환했습니다.")
                return True
            except Exception:
                pass
        
        return False
    
    def find_editor_element(self):
        """에디터 요소 찾기"""
        selectors = [
            "#SE-f9f7dd4d-8ed8-4a59-ab50-5951f7d4bf71 > span.se-placeholder.__se_placeholder.se-ff-nanumgothic.se-fs15.se-placeholder-focused",
            ".se-component.se-text",
            ".se-text-paragraph",
            ".se-editable",
            ".se-main-container",
            ".se-container",
            "[contenteditable='true']",
            ".se-editor",
            ".editor_area",
            ".naverEditor",
            "span[role='textbox']",
            "[placeholder*='내용']",
            "div.textarea_input",
            "div.se-placeholder"
        ]
        
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                self.signals.update_status.emit(f"에디터 요소를 찾았습니다: {selector}")
                return element
            except Exception:
                continue
        
        # 특별한 경우: 요소를 ID로 찾을 수 없는 경우 JavaScript로 찾기 시도
        try:
            self.signals.update_status.emit("JavaScript로 에디터 요소 찾기 시도...")
            # 편집 가능한 모든 요소 찾기
            editable_elements = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('*')).filter(el => {
                    const style = window.getComputedStyle(el);
                    return (el.isContentEditable || 
                            el.getAttribute('contenteditable') === 'true' || 
                            el.tagName === 'TEXTAREA' ||
                            el.tagName === 'IFRAME' && el.id.includes('editor')) && 
                           style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           el.offsetWidth > 0 && 
                           el.offsetHeight > 0;
                });
            """)
            
            if editable_elements and len(editable_elements) > 0:
                self.signals.update_status.emit(f"JavaScript로 {len(editable_elements)}개의 편집 가능한 요소를 찾았습니다.")
                return editable_elements[0]
        except Exception as e:
            self.signals.update_status.emit(f"JavaScript로 요소 찾기 실패: {str(e)}")
        
        return None
    
    def type_like_human(self, element, text):
        """사람처럼 타이핑하는 함수"""
        min_delay, max_delay = self.typing_speed
        
        # 진행상황 추적
        total_chars = len(text)
        
        # 텍스트를 한 글자씩 입력
        for i, char in enumerate(text):
            try:
                element.send_keys(char)
                # 글자마다 랜덤한 지연 시간 추가
                delay = random.uniform(min_delay, max_delay)
                time.sleep(delay)
                
                # 진행 상황 업데이트 (10% 단위)
                if i % max(1, total_chars // 10) == 0:
                    progress = (i / total_chars) * 100
                    self.signals.update_status.emit(f"텍스트 입력 중... {progress:.0f}%")
                    
            except Exception:
                # 기본 입력 방식이 실패하면 ActionChains 시도
                try:
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element)
                    actions.send_keys(char)
                    actions.perform()
                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    # 모든 방법 실패 시 나머지 텍스트 한 번에 입력 시도
                    remaining_text = text[i:]
                    try:
                        element.send_keys(remaining_text)
                    except Exception:
                        # 마지막 시도: JavaScript로 텍스트 추가
                        try:
                            self.driver.execute_script(f"""
                                var el = arguments[0];
                                if (el.isContentEditable) {{
                                    el.textContent = el.textContent + `{remaining_text.replace('`', '\\`')}`;
                                }} else if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                                    el.value = el.value + `{remaining_text.replace('`', '\\`')}`;
                                }}
                            """, element)
                        except Exception:
                            pass
                    break
        
        # 입력 완료
        self.signals.update_status.emit("타이핑 완료")
    
    def set_typing_speed(self, min_delay, max_delay):
        """타이핑 속도 설정"""
        self.typing_speed = (min_delay, max_delay)
    
    def stop(self):
        """스레드 종료"""
        self.should_stop = True
        if self.driver:
            self.driver.quit()

class NaverBlogTypingApp(QMainWindow):
    """네이버 블로그 타이핑 앱"""
    def __init__(self):
        super().__init__()
        self.browser_thread = None
        self.account_manager = AccountManager()
        self.settings = QSettings(ORGANIZATION, APP_NAME)
        self.initUI()
        self.apply_style()
    
    def initUI(self):
        """UI 초기화"""
        # 기본 윈도우 설정
        self.setWindowTitle("네이버 블로그 자동 타이핑")
        self.setGeometry(100, 100, 800, 600)
        
        # 화면 크기 가져오기
        screen_rect = QApplication.desktop().screenGeometry()
        self.screen_size = (screen_rect.width(), screen_rect.height())
        
        # 저장된 위치가 있으면 적용
        saved_geometry = self.settings.value("geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        
        # 상단 헤더
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # 로고 라벨
        logo_label = QLabel("네이버 블로그 자동화")
        logo_label.setFont(QFont("맑은 고딕", 14, QFont.Bold))
        header_layout.addWidget(logo_label)
        
        # 버전 및 헤더 정보
        header_layout.addStretch()
        
        # 개발자 정보 추가
        dev_label = QLabel("Dev By Uniscrew")
        dev_label.setStyleSheet("color: #03C75A; font-weight: bold;")
        header_layout.addWidget(dev_label)
        
        version_label = QLabel("v1.0")
        version_label.setStyleSheet("color: #888888;")
        header_layout.addWidget(version_label)
        
        main_layout.addWidget(header_widget)
        
        # 분할 영역 (로그인/설정 영역과 입력 영역)
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter, 1)
        
        # 상단 영역 (로그인 및 설정)
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 10, 0, 0)  # 상단 여백 추가
        top_layout.setSpacing(15)  # 그룹박스 간 간격 추가
        
        # 계정 그룹
        account_group = QGroupBox()
        account_group.setTitle("계정 관리")  # 명시적으로 타이틀 설정
        account_group.setMinimumHeight(250)  # 최소 높이 설정
        account_layout = QVBoxLayout()
        account_layout.setContentsMargins(15, 15, 15, 15)  # 내부 여백 추가
        
        # 계정 콤보박스
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(150)
        self.account_combo.setMinimumHeight(30)  # 높이 증가
        self.account_combo.setFont(QFont("맑은 고딕", 10))  # 폰트 설정
        self.account_combo.setToolTip("계정을 선택하세요")  # 기본 툴팁 추가
        self.account_combo.currentIndexChanged.connect(self.on_account_changed)
        account_layout.addWidget(self.account_combo)
        
        # 계정 관리 버튼 레이아웃
        account_buttons_layout = QHBoxLayout()
        
        # 계정 추가 버튼
        self.add_account_button = QPushButton("계정 추가")
        self.add_account_button.clicked.connect(self.add_account_dialog)
        account_buttons_layout.addWidget(self.add_account_button)
        
        # 계정 삭제 버튼
        self.remove_account_button = QPushButton("계정 삭제")
        self.remove_account_button.clicked.connect(self.remove_account)
        account_buttons_layout.addWidget(self.remove_account_button)
        
        account_layout.addLayout(account_buttons_layout)
        
        # 로그인 정보 폼
        login_form = QFormLayout()
        
        # 아이디 입력
        self.username_input = QLineEdit()
        login_form.addRow("아이디:", self.username_input)
        
        # 비밀번호 입력
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        login_form.addRow("비밀번호:", self.password_input)
        
        # 자동 로그인 체크박스
        self.autologin_checkbox = QCheckBox("자동 로그인 시도 (보안 문자 있을 수 있음)")
        login_form.addRow("", self.autologin_checkbox)
        
        account_layout.addLayout(login_form)
        
        # 브라우저 시작 버튼
        self.start_browser_button = QPushButton("브라우저 시작")
        self.start_browser_button.clicked.connect(self.start_browser)
        self.start_browser_button.setStyleSheet("""
            QPushButton {
                background-color: #03C75A;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #04D66A;
            }
            QPushButton:pressed {
                background-color: #02B54A;
            }
        """)
        account_layout.addWidget(self.start_browser_button)
        
        account_group.setLayout(account_layout)
        top_layout.addWidget(account_group)
        
        # 블로그 그룹
        blog_group = QGroupBox()
        blog_group.setTitle("블로그 설정")  # 명시적으로 타이틀 설정
        blog_group.setMinimumHeight(250)  # 최소 높이 설정
        blog_layout = QVBoxLayout()
        blog_layout.setContentsMargins(15, 15, 15, 15)  # 내부 여백 추가
        
        # 블로그 ID 입력
        blog_form = QFormLayout()
        self.blog_combo = QComboBox()
        self.blog_combo.setEditable(True)
        self.blog_combo.setMinimumWidth(150)
        self.blog_combo.setMinimumHeight(30)  # 높이 증가
        self.blog_combo.setFont(QFont("맑은 고딕", 10))  # 폰트 설정
        self.blog_combo.setToolTip("블로그 ID를 선택하거나 입력하세요")  # 기본 툴팁 추가
        blog_form.addRow("블로그 ID:", self.blog_combo)
        blog_layout.addLayout(blog_form)
        
        # 블로그 이동 버튼 레이아웃
        blog_buttons_layout = QHBoxLayout()
        
        # 블로그 이동 버튼
        self.goto_blog_button = QPushButton("블로그 이동")
        self.goto_blog_button.clicked.connect(self.goto_blog)
        self.goto_blog_button.setEnabled(False)
        blog_buttons_layout.addWidget(self.goto_blog_button)
        
        # 글쓰기 페이지 이동 버튼
        self.goto_write_button = QPushButton("글쓰기 페이지")
        self.goto_write_button.clicked.connect(self.goto_write_page)
        self.goto_write_button.setEnabled(False)
        blog_buttons_layout.addWidget(self.goto_write_button)
        
        blog_layout.addLayout(blog_buttons_layout)
        
        # 타이핑 속도 설정
        speed_form = QFormLayout()
        
        # 속도 조절 레이아웃
        speed_layout = QHBoxLayout()
        
        # 최소 지연 시간
        self.min_delay_input = QDoubleSpinBox()
        self.min_delay_input.setRange(0.01, 1.0)
        self.min_delay_input.setSingleStep(0.01)
        self.min_delay_input.setValue(0.05)
        speed_layout.addWidget(QLabel("최소:"))
        speed_layout.addWidget(self.min_delay_input)
        
        # 최대 지연 시간
        self.max_delay_input = QDoubleSpinBox()
        self.max_delay_input.setRange(0.01, 1.0)
        self.max_delay_input.setSingleStep(0.01)
        self.max_delay_input.setValue(0.15)
        speed_layout.addWidget(QLabel("최대:"))
        speed_layout.addWidget(self.max_delay_input)
        
        speed_form.addRow("타이핑 속도 (초):", speed_layout)
        blog_layout.addLayout(speed_form)
        
        # 속도 적용 버튼
        self.apply_speed_button = QPushButton("속도 적용")
        self.apply_speed_button.clicked.connect(self.apply_typing_speed)
        self.apply_speed_button.setEnabled(False)
        blog_layout.addWidget(self.apply_speed_button)
        
        blog_group.setLayout(blog_layout)
        top_layout.addWidget(blog_group)
        
        top_widget.setLayout(top_layout)
        splitter.addWidget(top_widget)
        
        # 입력 영역
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 10, 0, 0)  # 상단 여백 추가
        
        # 입력 그룹
        input_group = QGroupBox()
        input_group.setTitle("블로그 글 입력")  # 명시적으로 타이틀 설정
        input_group_layout = QVBoxLayout()
        input_group_layout.setContentsMargins(15, 15, 15, 15)  # 내부 여백 추가
        
        # 텍스트 입력 영역
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("여기에 입력할 내용을 작성하세요...")
        input_group_layout.addWidget(self.text_input, 1)
        
        # 타이핑 버튼
        self.type_button = QPushButton("타이핑 시작")
        self.type_button.clicked.connect(self.start_typing)
        self.type_button.setEnabled(False)
        self.type_button.setStyleSheet("""
            QPushButton {
                background-color: #03C75A;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #04D66A;
            }
            QPushButton:pressed {
                background-color: #02B54A;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """)
        input_group_layout.addWidget(self.type_button)
        
        input_group.setLayout(input_group_layout)
        input_layout.addWidget(input_group)
        
        splitter.addWidget(input_widget)
        
        # 상태 표시
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(5, 0, 5, 0)
        
        self.status_label = QLabel("준비됨")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_layout.addWidget(self.status_label, 1)
        
        # 진행 표시줄
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 불확정 진행
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(100)
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(status_widget)
        
        # 저장된 계정 정보 로드
        self.load_accounts_to_ui()
    
    def apply_style(self):
        """스타일 적용"""
        # 앱 전체 스타일 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F6F7;
            }
            QGroupBox {
                border: 1px solid #DDDDDD;
                border-radius: 6px;
                margin-top: 25px;  /* 타이틀 영역 확보를 위해 마진 더 증가 */
                font-weight: bold;
                background-color: white;
                padding-top: 15px;  /* 내부 여백 추가 */
                padding-left: 10px;
                padding-right: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                top: -15px;  /* 타이틀 위치 조정 */
                padding: 0 10px;  /* 여백 증가 */
                background-color: white;
                color: #03C75A;
                font-size: 12pt;  /* 글자 크기 키움 */
                font-weight: bold;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit, QTextEdit, QComboBox {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #03C75A;
            }
            QPushButton {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 5px 10px;
                background-color: #F5F6F7;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #EEEEEE;
            }
            QPushButton:pressed {
                background-color: #DDDDDD;
            }
            QPushButton:disabled {
                color: #888888;
                background-color: #F5F6F7;
            }
            QProgressBar {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #03C75A;
            }
            QStatusBar {
                background-color: #F5F6F7;
                color: #666666;
            }
            QCheckBox {
                color: #333333;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #DDDDDD;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #03C75A;
                border: 1px solid #03C75A;
            }
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 4px;
            }
            /* 콤보박스 스타일 개선 */
            QComboBox {
                background-color: white;
                selection-background-color: #E9F6EF;
                selection-color: #333333;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #E9F6EF;
                selection-color: #333333;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border-left: 1px solid #DDDDDD;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox::drop-down:hover {
                background-color: #F0F0F0;
            }
            /* 툴팁 스타일 개선 */
            QToolTip {
                background-color: #333333;
                color: white;
                border: 1px solid #03C75A;
                border-radius: 3px;
                padding: 5px;
                opacity: 230;
                font-weight: bold;
            }
        """)
    
    def load_accounts_to_ui(self):
        """계정 정보를 UI에 로드"""
        self.account_combo.clear()
        
        # 계정 목록 가져오기
        for account in self.account_manager.accounts:
            display_name = account.get("nickname") or account["username"]
            self.account_combo.addItem(display_name, account["username"])
            # 툴팁 추가 - 마우스를 올렸을 때 아이디 정보 표시
            last_index = self.account_combo.count() - 1
            self.account_combo.setItemData(
                last_index, 
                f"아이디: {account['username']}", 
                Qt.ToolTipRole
            )
        
        # 현재 선택된 계정 설정
        current_account = self.account_manager.get_current_account()
        if current_account:
            # 콤보박스에서 현재 계정 선택
            for i in range(self.account_combo.count()):
                if self.account_combo.itemData(i) == current_account["username"]:
                    self.account_combo.setCurrentIndex(i)
                    break
            
            # 로그인 정보 설정
            self.username_input.setText(current_account["username"])
            self.password_input.setText(current_account["password"])
            
            # 블로그 목록 업데이트
            self.update_blog_list(current_account)
    
    def update_blog_list(self, account):
        """블로그 목록 업데이트"""
        self.blog_combo.clear()
        
        # 기본 블로그 ID 추가 (계정 아이디와 동일)
        self.blog_combo.addItem(account["username"], account["username"])
        # 툴팁 추가
        self.blog_combo.setItemData(0, f"블로그 ID: {account['username']}", Qt.ToolTipRole)
        
        # 추가 블로그 목록
        if "blogs" in account and account["blogs"]:
            for blog in account["blogs"]:
                if blog["id"] != account["username"]:  # 중복 방지
                    display_name = blog.get("name") or blog["id"]
                    self.blog_combo.addItem(display_name, blog["id"])
                    # 툴팁 추가
                    last_index = self.blog_combo.count() - 1
                    self.blog_combo.setItemData(last_index, f"블로그 ID: {blog['id']}", Qt.ToolTipRole)
    
    def on_account_changed(self, index):
        """계정 선택 변경 시 처리"""
        if index < 0:
            return
            
        username = self.account_combo.itemData(index)
        if not username:
            return
            
        # 계정 정보 변경
        self.account_manager.set_current_account(username)
        
        # 선택된 계정 정보 가져오기
        account = self.account_manager.get_current_account()
        if account:
            # 로그인 정보 설정
            self.username_input.setText(account["username"])
            self.password_input.setText(account["password"])
            
            # 블로그 목록 업데이트
            self.update_blog_list(account)
    
    def add_account_dialog(self):
        """계정 추가 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("네이버 계정 추가")
        dialog.setFixedWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        # 폼 레이아웃
        form = QFormLayout()
        
        # 아이디 입력
        username_input = QLineEdit()
        form.addRow("아이디:", username_input)
        
        # 비밀번호 입력
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        form.addRow("비밀번호:", password_input)
        
        # 별명 입력 (선택)
        nickname_input = QLineEdit()
        form.addRow("별명 (선택):", nickname_input)
        
        layout.addLayout(form)
        
        # 버튼 박스
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # 다이얼로그 실행
        if dialog.exec_() == QDialog.Accepted:
            username = username_input.text().strip()
            password = password_input.text().strip()
            nickname = nickname_input.text().strip()
            
            if username and password:
                # 계정 추가
                self.account_manager.add_account(username, password, nickname)
                # UI 업데이트
                self.load_accounts_to_ui()
                self.update_status(f"계정 '{username}'이(가) 추가되었습니다.")
            else:
                QMessageBox.warning(self, "입력 오류", "아이디와 비밀번호를 모두 입력해주세요.")
    
    def remove_account(self):
        """선택된 계정 삭제"""
        index = self.account_combo.currentIndex()
        if index < 0:
            return
            
        username = self.account_combo.itemData(index)
        display_name = self.account_combo.currentText()
        
        # 확인 메시지
        reply = QMessageBox.question(
            self,
            "계정 삭제",
            f"'{display_name}' 계정을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 계정 삭제
            if self.account_manager.remove_account(username):
                # UI 업데이트
                self.load_accounts_to_ui()
                self.update_status(f"계정 '{display_name}'이(가) 삭제되었습니다.")
            else:
                QMessageBox.warning(self, "삭제 오류", "계정을 삭제할 수 없습니다.")
    
    def start_browser(self):
        """브라우저 시작"""
        try:
            # 이미 실행 중인 스레드가 있다면 종료
            if self.browser_thread and self.browser_thread.is_alive():
                self.browser_thread.stop()
                # 스레드가 완전히 종료될 때까지 잠시 대기
                time.sleep(1)
                
            # 입력 정보 가져오기
            username = self.username_input.text().strip()
            password = self.password_input.text().strip()
            
            # 자동 로그인 여부 확인
            if not self.autologin_checkbox.isChecked():
                username = ""
                password = ""
            
            # UI 업데이트
            self.start_browser_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.update_status("브라우저를 시작하는 중...")
            
            # 브라우저 스레드 시작
            self.browser_thread = BrowserThread(username, password, self.screen_size)
            self.browser_thread.signals.update_status.connect(self.update_status)
            self.browser_thread.signals.browser_ready.connect(self.on_browser_ready)
            self.browser_thread.signals.typing_completed.connect(self.on_typing_completed)
            
            self.browser_thread.start()
            
            # 계정 정보 저장 (입력한 정보가 있을 경우)
            if username and password:
                current_account = self.account_manager.get_current_account()
                if current_account and current_account["username"] == username:
                    # 기존 계정 정보 업데이트
                    self.account_manager.add_account(username, password, current_account.get("nickname", ""))
                else:
                    # 새 계정 추가
                    self.account_manager.add_account(username, password)
                    # UI 업데이트
                    self.load_accounts_to_ui()
                    
        except Exception as e:
            error_msg = f"브라우저 시작 오류: {e}"
            print(error_msg)  # 콘솔에 오류 출력
            self.update_status(error_msg)
            QMessageBox.critical(self, "오류", f"브라우저를 시작하는 중 오류가 발생했습니다.\n{e}")
            self.start_browser_button.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def goto_blog(self):
        """블로그로 이동"""
        if not self.browser_thread or not self.browser_thread.is_alive():
            self.update_status("브라우저가 실행되지 않았습니다.")
            return
            
        blog_id = self.blog_combo.currentData() or self.blog_combo.currentText().strip()
        if not blog_id:
            QMessageBox.warning(self, "입력 오류", "블로그 ID를 입력해주세요.")
            return
            
        # 블로그로 이동
        self.browser_thread.navigate_to_blog(blog_id)
        
        # 현재 계정에 블로그 추가
        current_account = self.account_manager.get_current_account()
        if current_account:
            self.account_manager.add_blog_to_account(current_account["username"], blog_id)
            # 블로그 목록 업데이트
            self.update_blog_list(current_account)
    
    def goto_write_page(self):
        """글쓰기 페이지로 이동"""
        if not self.browser_thread or not self.browser_thread.is_alive():
            self.update_status("브라우저가 실행되지 않았습니다.")
            return
            
        blog_id = self.blog_combo.currentData() or self.blog_combo.currentText().strip()
        if not blog_id:
            QMessageBox.warning(self, "입력 오류", "블로그 ID를 입력해주세요.")
            return
            
        # 글쓰기 페이지로 이동
        self.browser_thread.navigate_to_write_page(blog_id)
    
    def apply_typing_speed(self):
        """타이핑 속도 적용"""
        if not self.browser_thread or not self.browser_thread.is_alive():
            self.update_status("브라우저가 실행되지 않았습니다.")
            return
            
        min_delay = self.min_delay_input.value()
        max_delay = self.max_delay_input.value()
        
        # 최소값이 최대값보다 큰 경우 조정
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay
            self.min_delay_input.setValue(min_delay)
            self.max_delay_input.setValue(max_delay)
        
        # 타이핑 속도 설정
        self.browser_thread.set_typing_speed(min_delay, max_delay)
        self.update_status(f"타이핑 속도가 {min_delay}초 ~ {max_delay}초로 설정되었습니다.")
        
        # 설정 저장
        self.settings.setValue("typing_speed_min", min_delay)
        self.settings.setValue("typing_speed_max", max_delay)
    
    def start_typing(self):
        """타이핑 시작"""
        if not self.browser_thread or not self.browser_thread.is_alive():
            self.update_status("브라우저가 실행되지 않았습니다.")
            return
            
        text = self.text_input.toPlainText()
        if not text:
            QMessageBox.warning(self, "입력 오류", "입력할 텍스트를 입력해주세요.")
            return
            
        # UI 업데이트
        self.type_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # 타이핑 시작 (새로운 스레드에서 실행)
        threading.Thread(target=self.browser_thread.type_text, args=(text,), daemon=True).start()
    
    def on_browser_ready(self, success):
        """브라우저 준비 완료 처리"""
        self.start_browser_button.setEnabled(True)
        self.goto_blog_button.setEnabled(success)
        self.goto_write_button.setEnabled(success)
        self.apply_speed_button.setEnabled(success)
        self.type_button.setEnabled(success)
        self.progress_bar.setVisible(False)
    
    def on_typing_completed(self, success, message):
        """타이핑 완료 처리"""
        self.update_status(message)
        self.type_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            # 타이핑 완료 메시지 표시
            QMessageBox.information(self, "타이핑 완료", "블로그 글 입력이 완료되었습니다!")
            self.text_input.clear()
    
    def update_status(self, message):
        """상태 메시지 업데이트"""
        self.status_label.setText(message)
    
    def closeEvent(self, event):
        """앱 종료 시 처리"""
        # 브라우저 종료
        if self.browser_thread and self.browser_thread.is_alive():
            self.browser_thread.stop()
        
        # 윈도우 위치 저장
        self.settings.setValue("geometry", self.saveGeometry())
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 애플리케이션 정보 설정
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    
    # 스타일 설정
    app.setStyle("Fusion")
    
    # 창 생성 및 표시
    window = NaverBlogTypingApp()
    window.show()
    
    sys.exit(app.exec_()) 