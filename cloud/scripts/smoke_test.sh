#!/usr/bin/env bash
# End-to-end smoke test for the cloud stack (also run by .github/workflows/cloud.yml).
# Starts the stack, simulates a board that walks for 6 s then runs for 6 s, and
# checks that predictions flow broker → classifier → database → API.
# Leaves the stack running.
set -euo pipefail

cloud_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_dir="$(dirname "$cloud_dir")"
compose=(docker compose -f "$cloud_dir/docker-compose.yml")

step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
json() { python3 -c "import json, sys; d = json.load(sys.stdin); print($1)"; }

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
messages=12
# The classifier needs window/5 one-second messages before its first prediction.
window=$(json 'd["window"]' < "$repo_dir/ml/models/model_meta.json")
expected=$((messages - window / 5 + 1))

step "Starting the stack"
"${compose[@]}" up -d --build --wait --wait-timeout 180
since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

step "API health (includes the database)"
curl -fsS "$api/api/health" | grep -q '"ok"' || fail "API health check"

step "No data yet for $device → 404"
status=$(curl -s -o /dev/null -w '%{http_code}' "$api/api/latest?device_id=$device")
[ "$status" = 404 ] || fail "expected 404 for a new device, got $status"

step "Broker rejects anonymous clients"
if "${compose[@]}" exec -T mosquitto mosquitto_pub -h localhost -t test -m x 2>/dev/null; then
  fail "anonymous publish was accepted"
fi

step "Simulated board: 6 s walking, then 6 s running"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/pip" install -q --disable-pip-version-check -r "$repo_dir/tools/requirements.txt"
# Listen for the predictions the classifier publishes back to the device. The single
# quotes are deliberate: the credentials expand inside the broker container.
# shellcheck disable=SC2016
"${compose[@]}" exec -T mosquitto sh -c \
  'mosquitto_sub -h localhost -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -t "$0" -C 3 -W 60' \
  "activity/$device/prediction" > "$tmp_dir/predictions.txt" &
sub_pid=$!
sleep 1
"$tmp_dir/venv/bin/python" "$repo_dir/tools/fake_publisher.py" \
  --host localhost --port "${MQTT_PORT:-1883}" --device-id "$device" \
  --activity alternate --switch-every 6 --count "$messages"

step "Predictions stored (expect $expected: the first needs $((window / 5)) messages to fill the $window-sample window)"
count=0
for _ in $(seq 1 20); do
  count=$(curl -fsS "$api/api/history?device_id=$device&limit=50" | json 'len(d)')
  [ "$count" -ge "$expected" ] && break
  sleep 0.5
done
[ "$count" -ge "$expected" ] || fail "only $count predictions stored"

step "Latest prediction is 'run', and the history contains both activities"
latest=$(curl -fsS "$api/api/latest?device_id=$device" | json 'd["activity"], round(d["confidence"], 2)')
echo "latest: $latest"
case "$latest" in run*) ;; *) fail "expected run, got $latest" ;; esac
activities=$(curl -fsS "$api/api/history?device_id=$device&limit=50" | json '" ".join(sorted({r["activity"] for r in d}))')
[ "$activities" = "run walk" ] || fail "history has: $activities"

step "Predictions were published back on activity/$device/prediction"
wait "$sub_pid" || fail "no prediction messages received"
python3 - "$tmp_dir/predictions.txt" <<'PY' || fail "bad prediction message"
import json, sys
lines = open(sys.argv[1]).read().split()
assert len(lines) == 3, lines
for line in lines:
    msg = json.loads(line)
    assert set(msg) == {"activity", "confidence", "ts"} and msg["activity"] in ("walk", "run", "idle"), msg
print("ok:", lines[-1])
PY

step "Today's summary counts those seconds"
total=$(curl -fsS "$api/api/summary?device_id=$device" | json 'sum(d["seconds"].values())')
[ "$total" -ge "$expected" ] || fail "summary total is $total"

step "Web page"
curl -fsS "$api/" | grep -q '<title>Live Activity</title>' || fail "index page"

step "Classifier log is clean"
logs=$("${compose[@]}" logs --no-color --since "$since" classifier)
if grep -qE "invalid message|NOT STORED|Traceback" <<<"$logs"; then
  grep -E "invalid message|NOT STORED|Traceback" <<<"$logs" | head -5
  fail "classifier reported problems"
fi

printf '\nSmoke test passed: %s predictions, latest %s, summary %s s.\n' "$count" "$latest" "$total"
