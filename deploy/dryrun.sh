#!/usr/bin/env bash
# End-to-end dry run, executed on K6_SERVER as the `bench` user: one stack on the SUT, conformance,
# preflight, a short VU search with both samplers, analysis. Short durations: a validation of the
# toolchain and the two VMs, NOT a benchmark result.
#   env: STACK (go-gin) RUN_NAME (dry) START (20) CAP (320)
set -euo pipefail
cd /opt/bench
# shellcheck disable=SC1091
. /etc/bench/sut.env
STACK="${STACK:-go-gin}"
RUN="${RUN_NAME:-dry}"
OUT="/opt/bench/results/${RUN}"
export SAMPLER=1 BASE_URL
rm -rf "${OUT}"; mkdir -p "${OUT}"

echo "== SUT: bring up ${STACK}"
trap 'ssh sut "/opt/bench/deploy/stack.sh down" >/dev/null 2>&1 || true' EXIT
ssh sut "/opt/bench/deploy/stack.sh up ${STACK}"

echo "== conformance suite over the private network"
k6 run --quiet --no-color -e BASE_URL="${BASE_URL}" contract/conformance.js

echo "== preflight"
python3 loadtest/runner/preflight.py --out "${OUT}/preflight.json" --with-service > "${OUT}/preflight.stdout" || echo "preflight reported problems (see ${OUT}/preflight.json)"
python3 - <<PY
import json
r = json.load(open("${OUT}/preflight.json"))
print("k6:", r["k6"]); print("LG memory:", r["lg"]["memory"], "| steal:", r["lg"]["steal"], "| nofile:", r["lg"]["nofile_soft"])
print("network:", json.dumps(r.get("network")))
print("SUT:", r["sut"], "| latency floor:", r.get("latency_floor"), "| max_vus_estimate:", r.get("max_vus_estimate"))
print("problems:", r["problems"], "| warnings:", r["warnings"])
PY

echo "== VU search (short): ${STACK} s1 T0"
python3 loadtest/runner/search.py --stack "${STACK}" --scenario s1 --think T0 --out "${OUT}/${STACK}/s1-T0" \
  --start "${START:-20}" --cap "${CAP:-320}" --warmup 10 --search-measure 20 --confirm-measure 30 --reps 1 --cooldown 5

echo "== summary"
python3 analysis/summarize.py "${OUT}" --out "${OUT}/summary"
for d in "${OUT}/${STACK}/s1-T0/levels"/*/; do
  [[ -f "${d}attribution.json" ]] && python3 -c "
import json,sys; a=json.load(open('${d}attribution.json')); print('${d##*/levels/}'.rstrip('/'), '->', a['verdict'], '|', '; '.join(a['reasons']))"
done
tar -C /opt/bench/results -czf "/tmp/${RUN}.tgz" "${RUN}"
chmod 644 "/tmp/${RUN}.tgz"
echo "== done: /tmp/${RUN}.tgz"
