#!/usr/bin/env bash
# Self-test of conformance.js against the reference mock:
#   1. the correct mock must pass 100 %
#   2. every injected contract violation (MOCK_BUG) must make the suite FAIL
# So a green run proves the suite is both runnable and able to catch defects.
#   env: K6 (default k6), PYTHON (default python3), PORT (default 18080)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K6="${K6:-k6}"
PYTHON="${PYTHON:-python3}"
PORT="${PORT:-18080}"
BUGS=(status422 no_location put_merge delete_200 accept_float)
pid=""

start_mock() {
  MOCK_BUG="$1" PORT="${PORT}" "${PYTHON}" "${HERE}/mock/server.py" &
  pid=$!
  for _ in $(seq 1 50); do
    (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null && return 0
    sleep 0.1
  done
  echo "mock did not start" >&2; return 1
}
stop_mock() { [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null; wait "${pid}" 2>/dev/null; pid=""; }
trap stop_mock EXIT

run_suite() { "${K6}" run --quiet -e BASE_URL="http://127.0.0.1:${PORT}" "${HERE}/conformance.js"; }

fail=0
echo "== correct mock: suite must pass =="
start_mock "" || exit 1
if run_suite >/tmp/conformance-ok.log 2>&1; then echo "PASS"; else echo "FAIL (unexpected)"; tail -40 /tmp/conformance-ok.log; fail=1; fi
stop_mock

for bug in "${BUGS[@]}"; do
  echo "== MOCK_BUG=${bug}: suite must fail =="
  start_mock "${bug}" || exit 1
  if run_suite >"/tmp/conformance-${bug}.log" 2>&1; then
    echo "NOT DETECTED (suite passed against a broken mock)"; fail=1
  else
    echo "detected ($(grep -c '✗' "/tmp/conformance-${bug}.log" || true) failing checks)"
  fi
  stop_mock
done
exit "${fail}"
