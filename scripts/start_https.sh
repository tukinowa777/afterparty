#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="$PROJECT_DIR/certs"
CERT_FILE="$CERT_DIR/afterparty-selfsigned.crt"
KEY_FILE="$CERT_DIR/afterparty-selfsigned.key"

mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=161.33.151.114"
fi

cd "$PROJECT_DIR"
exec python3 server.py --host 0.0.0.0 --port 8443 --certfile "$CERT_FILE" --keyfile "$KEY_FILE"
