#!/bin/bash

# 선택된 브랜치 가져오기 (없으면 main)
BRANCH=${1:-main}

# 로그 및 프로젝트 디렉토리 설정
LOG_DIR="/home/logs"
BUILD_LOG_FILE="/home/tools/deploy/build.log"
PROJECT_DIR="/home/tools/deploy/anipick-backend"
PID_FILE="/home/tools/deploy/anipick.pid"

# 로그 디렉토리 및 파일 생성
mkdir -p $LOG_DIR
touch $BUILD_LOG_FILE
touch $PID_FILE

# 이전 빌드 로그 초기화
> $BUILD_LOG_FILE

echo "=======================test==========================" >> $BUILD_LOG_FILE
echo " 배포 시작: $(date)" >> $BUILD_LOG_FILE
echo " 브랜치: $BRANCH" >> $BUILD_LOG_FILE
echo "=================================================" >> $BUILD_LOG_FILE

# 프로젝트 소스 코드 처리
if [ -d "$PROJECT_DIR" ]; then
  echo "기존 프로젝트 디렉토리($PROJECT_DIR)를 업데이트합니다." >> $BUILD_LOG_FILE
  cd "$PROJECT_DIR" || exit
  git reset --hard
  git fetch origin
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  echo "새로운 프로젝트를 클론합니다." >> $BUILD_LOG_FILE
  git clone https://github.com/Anipick-Team/anipick-backend.git "$PROJECT_DIR"
  cd "$PROJECT_DIR" || exit
  git checkout "$BRANCH"
fi

# 빌드
echo "Gradle 빌드를 시작합니다..." >> $BUILD_LOG_FILE
chmod +x gradlew
./gradlew clean build -x test >> $BUILD_LOG_FILE 2>&1

# 빌드 성공 여부 확인
if [ $? -ne 0 ]; then
  echo "Gradle 빌드에 실패했습니다. 로그를 확인하세요." >> $BUILD_LOG_FILE
  exit 1
fi

echo "빌드 성공!" >> $BUILD_LOG_FILE

# 기존 프로세스 종료
if [ -f "$PID_FILE" ] && kill -0 $(cat $PID_FILE) 2>/dev/null; then
  echo "기존 애플리케이션을 종료합니다." >> $BUILD_LOG_FILE
  kill -9 $(cat $PID_FILE)
fi

# 애플리케이션 시작
JAR_FILE=$(find build/libs/ -name "*.jar" | head -n 1)
if [ -z "$JAR_FILE" ]; then
    echo "빌드된 JAR 파일을 찾을 수 없습니다." >> $BUILD_LOG_FILE
    exit 1
fi

echo "애플리케이션을 시작합니다: $JAR_FILE" >> $BUILD_LOG_FILE

# 환경변수 파일 로드
if [ -f "/home/deploy/env" ]; then
    echo "환경변수 파일을 로드합니다." >> $BUILD_LOG_FILE
    export $(grep -v '^#' /home/deploy/env | xargs)
else
    echo "경고: /home/deploy/env 파일이 없습니다." >> $BUILD_LOG_FILE
fi

nohup java -Xmx1g -Xms1g -jar "$JAR_FILE" --spring.profiles.active=prod &

# PID 저장
echo $! > $PID_FILE

echo "=================================================" >> $BUILD_LOG_FILE
echo " 배포 완료: $(date)" >> $BUILD_LOG_FILE
echo "=================================================" >> $BUILD_LOG_FILE
