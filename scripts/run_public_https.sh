#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/tmp"
PID_FILE="$LOG_DIR/afterparty-https.pid"
LOG_FILE="$LOG_DIR/afterparty-https.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "already running: $PID"
    exit 0
  fi
fi

cd "$PROJECT_DIR"
nohup bash "$PROJECT_DIR/scripts/start_https.sh" >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
echo "started: $(cat "$PID_FILE")"
