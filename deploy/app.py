import os
import time
import shutil
import tempfile
import subprocess
import requests

import streamlit as st
from dotenv import load_dotenv

# --- Auth imports ---
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

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
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# --- 세션 상태 초기화 ---
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "process" not in st.session_state:
    st.session_state.process = None

# =========================
# 인증 설정 로드
# =========================
def load_auth_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=SafeLoader) or {}
        # 필수 cookie 키 점검
        if "cookie" not in cfg or not isinstance(cfg["cookie"], dict):
            raise KeyError("config.yaml에 'cookie' 키가 없습니다.")
        for ck in ("name", "key", "expiry_days"):
            if ck not in cfg["cookie"]:
                raise KeyError(f"config.yaml cookie에 '{ck}' 키가 없습니다.")
        # credentials.usernames 점검
        if "credentials" not in cfg or "usernames" not in cfg["credentials"]:
            raise KeyError("config.yaml에 'credentials.usernames' 키가 없습니다.")
        return cfg
    except Exception as e:
        st.error(f"인증 설정(config.yaml) 로드 실패: {e}")
        st.stop()

auth_config = load_auth_config(CONFIG_PATH)

# streamlit-authenticator 초기화 (credentials dict 전체를 전달)
authenticator = stauth.Authenticate(
    auth_config["credentials"],                 # {'usernames': {...}} 형태여야 함
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"],
    auth_config.get("preauthorized", {})
)

# =========================
# 앱 본문 (인증 후 렌더)
# =========================
@st.cache_data(ttl=300)
def get_branches():
    """GitHub API를 사용하여 전체 브랜치 목록을 페이징 처리로 모두 가져옵니다."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/branches"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    branches = []
    page = 1
    per_page = 100
    try:
        while True:
            params = {"per_page": per_page, "page": page}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            branches.extend([branch["name"] for branch in data])
            if len(data) < per_page:
                break
            page += 1
        if "main" not in branches:
            branches.insert(0, "main")
        return branches
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"GitHub 브랜치 로딩 실패: {e}")
        return ["main"]

def run_script(script_name, branch=None):
    """쉘 스크립트를 백그라운드에서 실행합니다."""
    if st.session_state.is_running:
        st.toast("이미 다른 프로세스가 실행 중입니다.", icon="⚠️")
        return

    cmd = [os.path.join(BASE_DIR, script_name)]
    if branch:
        cmd.append(branch)

    if script_name == "deploy.sh":
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

def update_deploy_app():
    repo_url = "https://github.com/Anipick-Team/depoly_shell.git"
    target_dir = BASE_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        # 저장소 클론
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, tmpdir]
        result = subprocess.run(clone_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            st.error(f"저장소 클론 실패: {result.stderr}")
            return
        # deploy 디렉토리 내 파일 복사
        src_dir = os.path.join(tmpdir, "deploy")
        if not os.path.exists(src_dir):
            st.error("저장소 내에 'deploy' 폴더가 없습니다.")
            return
        copied_paths = []
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(target_dir, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
                copied_paths.append(d)
            else:
                shutil.copy2(s, d)
                copied_paths.append(d)

        # 복사된 모든 파일/폴더에 실행권한 부여
        def chmod_recursive(path):
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for name in dirs + files:
                        os.chmod(os.path.join(root, name), 0o755)
                os.chmod(path, 0o755)
            else:
                os.chmod(path, 0o755)

        for p in copied_paths:
            chmod_recursive(p)

        st.success("deploy_app이 최신 상태로 업데이트되었고, 실행 권한도 부여되었습니다!")

def render_app():
    # 사이드바 컨트롤
    with st.sidebar:
        st.title("애니픽 배포 관리")

        # Logout 버튼
        authenticator.logout("Logout", "sidebar")

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

    # 메인 페이지
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
    build_log_container.code(build_log_content, language="log")

    st.subheader("애플리케이션 로그 (Spring)")
    spring_log_container = st.container(height=400)
    spring_log_content = read_log_content(SPRING_LOG_FILE)
    spring_log_container.code(spring_log_content, language="log")

    # 상단 우측 버튼
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("deploy_app 업데이트", use_container_width=True):
            update_deploy_app()
            st.rerun()

    # 자동 새로고침
    time.sleep(3)
    st.rerun()

# =========================
# 로그인 흐름
# =========================
name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status:
    st.sidebar.success(f"Welcome {name}")
    render_app()
elif authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Please enter your username and password")
