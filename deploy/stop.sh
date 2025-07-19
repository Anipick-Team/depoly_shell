#!/bin/bash

PID_FILE="/home/tools/deploy/anipick.pid"
BUILD_LOG_FILE="/home/tools/deploy/build.log"

echo "서버 중지를 시도합니다..." >> $BUILD_LOG_FILE

if [ -f "$PID_FILE" ]; then
  PID=$(cat $PID_FILE)
  if kill -0 $PID 2>/dev/null; then
    kill -9 $PID
    rm -f $PID_FILE
    echo "프로세스(PID: $PID)를 종료했습니다." >> $BUILD_LOG_FILE
  else
    echo "PID 파일은 존재하지만, 해당 프로세스가 실행 중이지 않습니다." >> $BUILD_LOG_FILE
    rm -f $PID_FILE
  fi
else
  echo "PID 파일이 존재하지 않아 종료할 프로세스가 없습니다." >> $BUILD_LOG_FILE
fi
