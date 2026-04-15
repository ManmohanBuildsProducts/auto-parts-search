#!/usr/bin/env bash
# Starts Meilisearch + FastAPI + Cloudflare Tunnel in the background.
# Idempotent: skips services that are already healthy.
# Prints the shareable public tunnel URL at the end.

set -e
cd "$(dirname "$0")/.."
mkdir -p data/meili /tmp/cf

echo "[1/3] Meilisearch..."
if curl -sf http://127.0.0.1:7700/health >/dev/null 2>&1; then
  echo "  already running"
else
  MEILI_NO_ANALYTICS=true meilisearch \
    --db-path data/meili/data.ms \
    --env development \
    --master-key aps_local_dev_key_do_not_use_in_prod \
    --no-analytics \
    --http-addr 127.0.0.1:7700 \
    > data/meili/meili.log 2>&1 &
  for i in {1..20}; do
    sleep 0.5
    curl -sf http://127.0.0.1:7700/health >/dev/null 2>&1 && break
  done
  echo "  started"
fi

echo "[2/3] FastAPI..."
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "  already running"
else
  python3.11 -m uvicorn auto_parts_search.api:app --port 8000 --log-level warning > /tmp/api.log 2>&1 &
  for i in {1..40}; do
    sleep 0.5
    curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  done
  echo "  started (model warm)"
fi

echo "[3/3] Cloudflare tunnel..."
if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
  echo "  already running"
else
  cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/cf/tunnel.log 2>&1 &
  # wait for URL to appear
  for i in {1..30}; do
    sleep 1
    grep -q "trycloudflare.com" /tmp/cf/tunnel.log 2>/dev/null && break
  done
  echo "  started"
fi

URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf/tunnel.log | head -1)
echo ""
echo "========================================"
echo "✅ All services up"
echo "   Local API:    http://127.0.0.1:8000"
echo "   Public URL:   ${URL:-<tunnel not ready yet; grep /tmp/cf/tunnel.log>}"
echo "   Swagger:      ${URL:-http://127.0.0.1:8000}/docs"
echo "========================================"
