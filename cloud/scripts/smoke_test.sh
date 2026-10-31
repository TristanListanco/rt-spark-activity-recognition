#!/usr/bin/env bash
# End-to-end smoke test for the cloud stack (also run by .github/workflows/cloud.yml).
# Starts the stack, checks the API and broker auth, publishes fake IMU messages,
# and checks that the classifier received them. Leaves the stack running.
set -euo pipefail

cloud_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_dir="$(dirname "$cloud_dir")"
compose=(docker compose -f "$cloud_dir/docker-compose.yml")

step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

if [ ! -f "$cloud_dir/.env" ]; then
  echo "cloud/.env not found; creating it from .env.example"
  cp "$cloud_dir/.env.example" "$cloud_dir/.env"
fi
set -a
# shellcheck source=/dev/null
. "$cloud_dir/.env"
set +a
api="http://localhost:${API_PORT:-8000}"
device="smoke-test-$$"

step "Starting the stack"
"${compose[@]}" up -d --build --wait --wait-timeout 180

step "API health"
curl -fsS "$api/api/health" | grep -q '"ok"' || fail "API health check"

step "API latest"
curl -fsS "$api/api/latest?device_id=$device" \
  | python3 -c 'import json, sys; assert json.load(sys.stdin)["activity"] in ("walk", "run")' \
  || fail "/api/latest did not return a prediction"

step "Broker rejects anonymous clients"
if "${compose[@]}" exec -T mosquitto mosquitto_pub -h localhost -t test -m x 2>/dev/null; then
  fail "anonymous publish was accepted"
fi

step "Publishing 5 fake IMU messages as $device"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
venv="$tmp_dir/venv"
python3 -m venv "$venv"
"$venv/bin/pip" install -q --disable-pip-version-check -r "$repo_dir/tools/requirements.txt"
since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"$venv/bin/python" "$repo_dir/tools/fake_publisher.py" \
  --host localhost --port "${MQTT_PORT:-1883}" --device-id "$device" --activity run --count 5

step "Classifier received them"
received=0
for _ in $(seq 1 20); do
  received=$("${compose[@]}" logs --no-color --since "$since" classifier | grep -c "received device=$device" || true)
  [ "$received" -ge 5 ] && break
  sleep 0.5
done
[ "$received" -ge 5 ] || fail "classifier logged $received of 5 messages"
if "${compose[@]}" logs --no-color --since "$since" classifier | grep -q "invalid message"; then
  fail "classifier rejected a message"
fi

printf '\nSmoke test passed: API up, broker auth on, classifier received %s messages.\n' "$received"
