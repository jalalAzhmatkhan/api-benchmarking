#!/usr/bin/env bash
# Runs a provision.sh role on a VM from a GitHub Actions runner over password SSH.
# The password only ever comes from the environment secret (SSHPASS); it is never echoed.
#
#   env: VM_HOST, VM_USER, SSHPASS, [K6_VERSION]
#   usage: remote.sh <role> [plain-text arg]
# Writes the full log to $RUNNER_TEMP/<role>.log, "OUT|" lines to $GITHUB_OUTPUT and
# "REPORT|" lines as a table to $GITHUB_STEP_SUMMARY.
set -euo pipefail

ROLE="${1:?role required}"
ARG_B64="$(printf '%s' "${2:-}" | base64 -w0)"
: "${VM_HOST:?VM_IP_ADDRESS secret is missing for this environment}" "${VM_USER:?}" "${SSHPASS:?}"
# Defence in depth: never let the address reach a public log, even if it came from a plain variable.
echo "::add-mask::${VM_HOST}"
export SSHPASS
TMP="${RUNNER_TEMP:-/tmp}"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR=/tmp/bench-provision
LOG="${TMP}/${ROLE}.log"

SSH=(sshpass -e ssh
  -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="${TMP}/known_hosts"
  -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive
  -o ConnectTimeout=20 -o ServerAliveInterval=30 -o LogLevel=ERROR
  "${VM_USER}@${VM_HOST}")

# Ship the provisioning bundle (scripts + config files) to the VM.
tar -C "${DEPLOY_DIR}" -czf - provision sysctl docker \
  | "${SSH[@]}" "rm -rf ${REMOTE_DIR} && mkdir -p ${REMOTE_DIR} && tar -xzf - -C ${REMOTE_DIR}"

# sudo reads the password from stdin (-S); provision.sh closes its own stdin first.
printf '%s\n' "${SSHPASS}" \
  | "${SSH[@]}" "sudo -S -p '' env K6_VERSION='${K6_VERSION:-2.3.0}' bash ${REMOTE_DIR}/provision/provision.sh ${ROLE} '${ARG_B64}'" \
  | tee "${LOG}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  grep '^OUT|' "${LOG}" | cut -d'|' -f2- >> "${GITHUB_OUTPUT}" || true
fi
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && grep -q '^REPORT|' "${LOG}"; then
  {
    echo "### ${ROLE} — ${SUMMARY_TITLE:-VM}"
    echo
    echo "| Item | Value |"
    echo "|---|---|"
    grep '^REPORT|' "${LOG}" | awk -F'|' '{print "| "$2" | "$3" |"}'
    echo
  } >> "${GITHUB_STEP_SUMMARY}"
fi
