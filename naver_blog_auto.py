import sys
import time
import json
import os.path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QCheckBox, QMessageBox, QTabWidget, QGroupBox,
                            QFormLayout, QTextEdit, QProgressBar, QFileDialog,
                            QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

class NaverLoginThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, username, password, save_credentials=False):
        super().__init__()
        self.username = username
        self.password = password
        self.save_credentials = save_credentials
        self.driver = None
        
    def run(self):
        try:
            self.update_signal.emit("크롬 브라우저를 시작하는 중...")
            
            # 크롬 옵션 설정
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 크롬 드라이버 설치 및 시작
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 네이버 로그인 페이지 열기
            self.update_signal.emit("네이버 로그인 페이지로 이동 중...")
            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)
            
            # 자바스크립트를 통한 로그인 (봇 감지 우회)
            self.update_signal.emit("로그인 중...")
            
            # ID 입력
            self.driver.execute_script(
                f"document.getElementsByName('id')[0].value='{self.username}'")
            time.sleep(0.5)
            
            # 비밀번호 입력
            self.driver.execute_script(
                f"document.getElementsByName('pw')[0].value='{self.password}'")
            time.sleep(0.5)
            
            # 로그인 버튼 클릭
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "log.login"))
            )
            login_button.click()
            
            # 로그인 결과 확인
            time.sleep(3)
            
            # 자동입력 방지 문자가 나타났는지 확인
            if "자동입력 방지" in self.driver.page_source or "보안 문자" in self.driver.page_source:
                self.update_signal.emit("보안 문자 인증이 필요합니다. 직접 입력해주세요.")
                
                # 사용자가 보안 문자를 입력할 시간을 줌
                for i in range(30, 0, -1):
                    self.update_signal.emit(f"보안 문자를 입력해주세요... {i}초 남음")
                    time.sleep(1)
                    
                    # 로그인 성공했는지 확인
                    if "naver.com" in self.driver.current_url and "nidlogin" not in self.driver.current_url:
                        break
            
            # 로그인 성공 여부 확인
            if "naver.com" in self.driver.current_url and "nidlogin" not in self.driver.current_url:
                self.update_signal.emit("로그인 성공! 블로그로 이동합니다...")
                
                # 자격 증명 저장
                if self.save_credentials:
                    self.save_credentials_to_file()
                
                # 블로그로 이동
                self.driver.get("https://blog.naver.com/rxd0119")
                time.sleep(3)
                
                # 성공 신호 전송
                self.finished_signal.emit(True, "로그인 및 블로그 접속 성공")
            else:
                self.update_signal.emit("로그인 실패. 아이디와 비밀번호를 확인해주세요.")
                self.finished_signal.emit(False, "로그인 실패")
                self.driver.quit()
                self.driver = None
                
        except Exception as e:
            error_msg = f"오류 발생: {str(e)}"
            self.update_signal.emit(error_msg)
            self.finished_signal.emit(False, error_msg)
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def save_credentials_to_file(self):
        """자격 증명을 파일에 저장"""
        credentials = {
            "username": self.username,
            "password": self.password
        }
        try:
            with open("credentials.json", "w") as f:
                json.dump(credentials, f)
        except Exception as e:
            self.update_signal.emit(f"자격 증명 저장 실패: {str(e)}")
    
    def stop(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None

class BlogPostThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, driver, title, content, category=None):
        super().__init__()
        self.driver = driver
        self.title = title
        self.content = content
        self.category = category
    
    def run(self):
        try:
            if not self.driver:
                self.update_signal.emit("브라우저가 실행되지 않았습니다. 먼저 로그인해주세요.")
                self.finished_signal.emit(False, "브라우저 오류")
                return
                
            self.update_signal.emit("글쓰기 페이지로 이동 중...")
            
            # 네이버 블로그 글쓰기 페이지로 이동
            self.driver.get("https://blog.naver.com/rxd0119")
            time.sleep(3)
            
            # 글쓰기 버튼 클릭
            try:
                # 먼저 헤더에서 글쓰기 버튼 찾기
                write_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_write, .link_write"))
                )
                write_button.click()
                self.update_signal.emit("글쓰기 버튼 클릭 완료")
            except Exception as e:
                self.update_signal.emit(f"글쓰기 버튼을 찾을 수 없습니다: {str(e)}")
                
                # 대체 방법: 직접 글쓰기 URL로 이동
                self.driver.get("https://blog.naver.com/PostWrite.naver?blogId=rxd0119")
                self.update_signal.emit("글쓰기 페이지로 직접 이동합니다.")
            
            time.sleep(5)  # 글쓰기 페이지 로딩 대기
            
            # iframe 전환 (에디터는 iframe 내부에 있음)
            try:
                # 현재 활성화된 iframe 찾기
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                
                # 에디터 iframe 찾기
                editor_iframe = None
                for iframe in iframes:
                    iframe_id = iframe.get_attribute("id")
                    if iframe_id and ("Editor" in iframe_id or "editor" in iframe_id):
                        editor_iframe = iframe
                        break
                
                if editor_iframe:
                    self.driver.switch_to.frame(editor_iframe)
                    self.update_signal.emit("에디터 프레임으로 전환 완료")
                else:
                    # 가장 큰 iframe으로 전환 (에디터일 가능성이 높음)
                    if iframes:
                        self.driver.switch_to.frame(iframes[0])
                        self.update_signal.emit("첫 번째 iframe으로 전환")
            except Exception as e:
                self.update_signal.emit(f"iframe 전환 실패: {str(e)}")
            
            # 제목 입력 (iframe 내부 또는 외부에 있을 수 있음)
            try:
                # iframe 내부에서 제목 필드 찾기
                title_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='제목'], .se-title-input"))
                )
                title_field.clear()
                title_field.send_keys(self.title)
                self.update_signal.emit("제목 입력 완료")
            except Exception as e:
                self.update_signal.emit(f"iframe 내부에서 제목 입력 실패: {str(e)}")
                
                # iframe 밖으로 나가서 시도
                try:
                    self.driver.switch_to.default_content()
                    title_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='제목'], .se-title-input"))
                    )
                    title_field.clear()
                    title_field.send_keys(self.title)
                    self.update_signal.emit("제목 입력 완료")
                except Exception as e2:
                    self.update_signal.emit(f"제목 입력 실패: {str(e2)}")
            
            # 본문 입력 (iframe 내부)
            try:
                # 먼저 본문 영역 클릭
                content_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".se-component-content, .se-text-paragraph, body"))
                )
                content_field.click()
                time.sleep(1)
                
                # 내용 입력 (여러 방식 시도)
                try:
                    # 1. 직접 send_keys
                    content_field.send_keys(self.content)
                except Exception:
                    try:
                        # 2. JavaScript 사용
                        self.driver.execute_script("arguments[0].textContent = arguments[1]", content_field, self.content)
                    except Exception:
                        # 3. ActionChains 사용
                        actions = ActionChains(self.driver)
                        actions.move_to_element(content_field)
                        actions.click()
                        actions.send_keys(self.content)
                        actions.perform()
                
                self.update_signal.emit("본문 입력 완료")
            except Exception as e:
                self.update_signal.emit(f"본문 입력 실패: {str(e)}")
            
            # 발행 버튼 찾기 (iframe 밖으로 나가야 함)
            self.driver.switch_to.default_content()
            time.sleep(1)
            
            # 발행 버튼 클릭
            try:
                publish_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_publish, .publish_btn, button[contains(text(), '발행')]"))
                )
                publish_button.click()
                self.update_signal.emit("발행 버튼 클릭 완료")
                
                # 발행 확인 버튼이 있을 경우 클릭
                try:
                    confirm_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_confirm, .confirm_btn, button[contains(text(), '확인')]"))
                    )
                    confirm_button.click()
                    self.update_signal.emit("발행 확인 완료")
                except Exception:
                    # 확인 버튼이 없을 수도 있음
                    pass
                
                # 발행 완료 대기
                time.sleep(5)
                self.finished_signal.emit(True, "글 발행이 완료되었습니다.")
            except Exception as e:
                self.update_signal.emit(f"발행 버튼 클릭 실패: {str(e)}")
                self.finished_signal.emit(False, f"글 발행 실패: {str(e)}")
                
        except Exception as e:
            error_msg = f"글쓰기 오류 발생: {str(e)}"
            self.update_signal.emit(error_msg)
            self.finished_signal.emit(False, error_msg)

class NaverBlogApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.login_thread = None
        self.post_thread = None
        self.driver = None
        self.initUI()
        self.load_credentials()
        
    def initUI(self):
        self.setWindowTitle("네이버 블로그 자동화")
        self.setGeometry(100, 100, 800, 600)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 로그인 탭
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)
        
        # 로그인 그룹박스
        login_group = QGroupBox("네이버 로그인")
        login_form = QFormLayout()
        
        # 아이디 입력
        self.username_input = QLineEdit()
        login_form.addRow("아이디:", self.username_input)
        
        # 비밀번호 입력
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        login_form.addRow("비밀번호:", self.password_input)
        
        # 자격 증명 저장 체크박스
        self.save_credentials_checkbox = QCheckBox("로그인 정보 저장")
        login_form.addRow("", self.save_credentials_checkbox)
        
        login_group.setLayout(login_form)
        login_layout.addWidget(login_group)
        
        # 로그인 버튼
        self.login_button = QPushButton("로그인")
        self.login_button.clicked.connect(self.start_login)
        login_layout.addWidget(self.login_button)
        
        # 상태 레이블
        self.login_status_label = QLabel("로그인하여 네이버 블로그에 접속하세요.")
        login_layout.addWidget(self.login_status_label)
        
        # 진행 상태 표시줄
        self.login_progress_bar = QProgressBar()
        self.login_progress_bar.setRange(0, 0)  # 불확정 진행 상태
        self.login_progress_bar.setVisible(False)
        login_layout.addWidget(self.login_progress_bar)
        
        # 탭 추가
        self.tab_widget.addTab(login_tab, "로그인")
        
        # 글쓰기 탭
        post_tab = QWidget()
        post_layout = QVBoxLayout(post_tab)
        
        # 글쓰기 상태 레이블
        self.post_status_label = QLabel("로그인 후 사용 가능합니다.")
        post_layout.addWidget(self.post_status_label)
        
        # 글쓰기 그룹
        post_group = QGroupBox("블로그 글쓰기")
        post_form = QFormLayout()
        
        # 제목 입력
        self.title_input = QLineEdit()
        post_form.addRow("제목:", self.title_input)
        
        # 카테고리 선택 (나중에 동적으로 불러올 수 있음)
        self.category_combo = QComboBox()
        self.category_combo.addItem("카테고리 없음")
        post_form.addRow("카테고리:", self.category_combo)
        
        # 본문 입력
        self.content_editor = QTextEdit()
        post_form.addRow("내용:", self.content_editor)
        
        post_group.setLayout(post_form)
        post_layout.addWidget(post_group)
        
        # 글쓰기 버튼 레이아웃
        post_button_layout = QHBoxLayout()
        
        # 글쓰기 버튼
        self.post_button = QPushButton("글 작성하기")
        self.post_button.clicked.connect(self.start_post)
        self.post_button.setEnabled(False)  # 로그인 전에는 비활성화
        post_button_layout.addWidget(self.post_button)
        
        # 초기화 버튼
        self.clear_button = QPushButton("내용 지우기")
        self.clear_button.clicked.connect(self.clear_post)
        post_button_layout.addWidget(self.clear_button)
        
        post_layout.addLayout(post_button_layout)
        
        # 글쓰기 진행 상태 표시줄
        self.post_progress_bar = QProgressBar()
        self.post_progress_bar.setRange(0, 0)
        self.post_progress_bar.setVisible(False)
        post_layout.addWidget(self.post_progress_bar)
        
        # 탭 추가
        self.tab_widget.addTab(post_tab, "글쓰기")
        
        # 탭 비활성화 (로그인 전)
        self.tab_widget.setTabEnabled(1, False)
        
        # 상태 표시줄
        self.statusBar().showMessage('준비됨')
    
    def load_credentials(self):
        """저장된 자격 증명 불러오기"""
        if os.path.exists("credentials.json"):
            try:
                with open("credentials.json", "r") as f:
                    credentials = json.load(f)
                    self.username_input.setText(credentials.get("username", ""))
                    self.password_input.setText(credentials.get("password", ""))
                    self.save_credentials_checkbox.setChecked(True)
            except Exception as e:
                self.statusBar().showMessage(f"자격 증명 로드 실패: {str(e)}")
    
    def start_login(self):
        """로그인 시작"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "입력 오류", "아이디와 비밀번호를 모두 입력해주세요.")
            return
        
        # UI 업데이트
        self.login_button.setEnabled(False)
        self.login_progress_bar.setVisible(True)
        self.login_status_label.setText("로그인 중...")
        
        # 로그인 스레드 시작
        self.login_thread = NaverLoginThread(
            username, 
            password,
            self.save_credentials_checkbox.isChecked()
        )
        self.login_thread.update_signal.connect(self.update_login_status)
        self.login_thread.finished_signal.connect(self.login_finished)
        self.login_thread.start()
    
    def update_login_status(self, message):
        """로그인 상태 메시지 업데이트"""
        self.login_status_label.setText(message)
        self.statusBar().showMessage(message)
    
    def login_finished(self, success, message):
        """로그인 완료 처리"""
        self.login_progress_bar.setVisible(False)
        
        if success:
            self.login_status_label.setText(message)
            self.statusBar().showMessage(message)
            self.driver = self.login_thread.driver
            
            # 로그인 성공 시 버튼 텍스트 변경
            self.login_button.setText("다시 로그인")
            self.login_button.setEnabled(True)
            
            # 글쓰기 탭 활성화
            self.tab_widget.setTabEnabled(1, True)
            self.post_button.setEnabled(True)
            self.post_status_label.setText("블로그에 글을 작성할 수 있습니다.")
            
            # 글쓰기 탭으로 전환
            self.tab_widget.setCurrentIndex(1)
        else:
            self.login_status_label.setText(message)
            self.statusBar().showMessage(message)
            QMessageBox.warning(self, "로그인 오류", message)
            self.login_button.setEnabled(True)
    
    def start_post(self):
        """글쓰기 시작"""
        if not self.driver:
            QMessageBox.warning(self, "오류", "먼저 로그인해주세요.")
            return
        
        title = self.title_input.text().strip()
        content = self.content_editor.toPlainText().strip()
        category = self.category_combo.currentText()
        
        if category == "카테고리 없음":
            category = None
        
        if not title:
            QMessageBox.warning(self, "입력 오류", "제목을 입력해주세요.")
            return
            
        if not content:
            QMessageBox.warning(self, "입력 오류", "내용을 입력해주세요.")
            return
        
        # UI 업데이트
        self.post_button.setEnabled(False)
        self.post_progress_bar.setVisible(True)
        self.post_status_label.setText("글 작성 중...")
        
        # 글쓰기 스레드 시작
        self.post_thread = BlogPostThread(
            self.driver,
            title,
            content,
            category
        )
        self.post_thread.update_signal.connect(self.update_post_status)
        self.post_thread.finished_signal.connect(self.post_finished)
        self.post_thread.start()
    
    def update_post_status(self, message):
        """글쓰기 상태 메시지 업데이트"""
        self.post_status_label.setText(message)
        self.statusBar().showMessage(message)
    
    def post_finished(self, success, message):
        """글쓰기 완료 처리"""
        self.post_progress_bar.setVisible(False)
        self.post_button.setEnabled(True)
        
        if success:
            self.post_status_label.setText(message)
            self.statusBar().showMessage(message)
            QMessageBox.information(self, "글쓰기 완료", message)
            self.clear_post()  # 내용 초기화
        else:
            self.post_status_label.setText(message)
            self.statusBar().showMessage(message)
            QMessageBox.warning(self, "글쓰기 오류", message)
    
    def clear_post(self):
        """글쓰기 내용 초기화"""
        self.title_input.clear()
        self.content_editor.clear()
        self.post_status_label.setText("내용이 초기화되었습니다.")
    
    def closeEvent(self, event):
        """앱 종료 시 드라이버 정리"""
        if self.login_thread and self.login_thread.isRunning():
            self.login_thread.stop()
        
        if self.driver:
            self.driver.quit()
            
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NaverBlogApp()
    window.show()
    sys.exit(app.exec_()) 