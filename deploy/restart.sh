#!/bin/bash

LOG_DIR="/home/logs"
PROJECT_DIR="/home/tools/deploy/anipick-backend"
PID_FILE="/home/tools/deploy/anipick.pid"
BUILD_LOG_FILE="/home/tools/deploy/build.log"

echo "애플리케이션 재시작을 시도합니다..." >> $BUILD_LOG_FILE

# 기존 프로세스 종료
if [ -f "$PID_FILE" ] && kill -0 $(cat $PID_FILE) 2>/dev/null; then
  echo "기존 애플리케이션을 종료합니다." >> $BUILD_LOG_FILE
  kill -9 $(cat $PID_FILE)
fi

# 마지막으로 빌드된 JAR 파일 찾기
JAR_FILE=$(find "$PROJECT_DIR/build/libs/" -name "*.jar" | head -n 1)

if [ -z "$JAR_FILE" ]; then
    echo "재시작할 JAR 파일을 찾을 수 없습니다. 먼저 배포를 진행해주세요." >> $BUILD_LOG_FILE
    exit 1
fi

# 애플리케이션 시작
echo "마지막으로 빌드된 파일로 애플리케이션을 시작합니다: $JAR_FILE" >> $BUILD_LOG_FILE

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

echo "재시작 완료." >> $BUILD_LOG_FILE
