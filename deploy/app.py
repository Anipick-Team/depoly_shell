import streamlit as st
import subprocess
import requests
import os
import time
from dotenv import load_dotenv

# --- 초기 설정 ---
load_dotenv("/home/deploy/env")
st.set_page_config(layout="wide")

# --- GitHub 정보 ---
GITHUB_OWNER = "Anipick-Team"
GITHUB_REPO = "anipick-backend"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# --- 파일 및 디렉토리 경로 ---
BASE_DIR = "/home/tools/deploy"
LOG_DIR = "/home/logs"
BUILD_LOG_FILE = os.path.join(BASE_DIR, "build.log")
SPRING_LOG_FILE = os.path.join(LOG_DIR, "springboot.log")

# --- 세션 상태 초기화 ---
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'process' not in st.session_state:
    st.session_state.process = None

# --- 함수 정의 ---
@st.cache_data(ttl=300)
def get_branches():
    """GitHub API를 사용하여 전체 브랜치 목록을 페이징 처리로 모두 가져옵니다."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/branches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    branches = []
    page = 1
    per_page = 100
    try:
        while True:
            params = {"per_page": per_page, "page": page}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            branches.extend([branch['name'] for branch in data])
            if len(data) < per_page:
                break
            page += 1
        if 'main' not in branches:
            branches.insert(0, 'main')
        return branches
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"GitHub 브랜치 로딩 실패: {e}")
        return ['main']

def run_script(script_name, branch=None):
    """쉘 스크립트를 백그라운드에서 실행합니다."""
    if st.session_state.is_running:
        st.toast("이미 다른 프로세스가 실행 중입니다.", icon="⚠️")
        return

    cmd = [os.path.join(BASE_DIR, script_name)]
    if branch:
        cmd.append(branch)

    if script_name == 'deploy.sh':
        with open(BUILD_LOG_FILE, "w") as f:
            f.write("")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    st.session_state.process = process
    st.session_state.is_running = True
    st.rerun()

def read_log_content(file_path):
    """로그 파일을 읽어 내용을 반환합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "로그 파일이 아직 생성되지 않았습니다."

# --- UI 정의 ---

# 사이드바 컨트롤
with st.sidebar:
    st.title("애니픽 배포 관리")

    branches = get_branches()
    selected_branch = st.selectbox(
        "브랜치 선택",
        branches,
        disabled=st.session_state.is_running
    )

    st.markdown("---")

    if st.button("배포", key="deploy", disabled=st.session_state.is_running, use_container_width=True):
        st.toast(f"'{selected_branch}' 브랜치 배포 시작...", icon="⏳")
        run_script("deploy.sh", selected_branch)

    if st.button("서버 중지", key="stop", disabled=st.session_state.is_running, use_container_width=True):
        st.toast("서버 중지 시작...", icon="⏳")
        run_script("stop.sh")

    if st.button("재시작", key="restart", disabled=st.session_state.is_running, use_container_width=True):
        st.toast("서버 재시작 시작...", icon="⏳")
        run_script("restart.sh")

# 메인 페이지 로그
st.title("실시간 로그")

# 프로세스 상태 확인
if st.session_state.is_running:
    if st.session_state.process and st.session_state.process.poll() is not None:
        st.session_state.is_running = False
        st.session_state.process = None
        st.toast("스크립트 실행이 완료되었습니다!", icon="✅")

# 로그 표시 영역
st.subheader("빌드 로그")
build_log_container = st.container(height=400)
build_log_content = read_log_content(BUILD_LOG_FILE)
build_log_container.code(build_log_content, language='log')

st.subheader("애플리케이션 로그 (Spring)")
spring_log_container = st.container(height=400)
spring_log_content = read_log_content(SPRING_LOG_FILE)
spring_log_container.code(spring_log_content, language='log')

# 자동 새로고침
time.sleep(3)
st.rerun()