#!/usr/bin/env bash
# Copy repository folders to /opt/bench on a VM (owned by the `bench` user) from GitHub Actions.
#   env: VM_HOST, VM_USER, SSHPASS (password never echoed), REVISION
#   usage: sync.sh <path>...      e.g. sync.sh deploy db monitoring
# Each listed path is replaced entirely; /opt/bench/results and other paths are left alone.
set -euo pipefail

: "${VM_HOST:?VM_IP_ADDRESS secret is missing}" "${VM_USER:?}" "${SSHPASS:?}"
echo "::add-mask::${VM_HOST}"
export SSHPASS
[[ $# -gt 0 ]] || { echo "usage: sync.sh <path>..." >&2; exit 2; }
for p in "$@"; do [[ "$p" =~ ^[a-z][a-z0-9_-]*$ ]] || { echo "bad path: $p" >&2; exit 2; }; done

TMP="${RUNNER_TEMP:-/tmp}"
OPTS=(-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="${TMP}/known_hosts" -o PubkeyAuthentication=no
      -o PreferredAuthentications=password,keyboard-interactive -o ConnectTimeout=20 -o ServerAliveInterval=30 -o LogLevel=ERROR)
SSH=(sshpass -e ssh "${OPTS[@]}" "${VM_USER}@${VM_HOST}")

tar -czf "${TMP}/bench-sync.tgz" "$@"
sshpass -e scp "${OPTS[@]}" "${TMP}/bench-sync.tgz" "${VM_USER}@${VM_HOST}:/tmp/bench-sync.tgz"

REMOTE='set -e
install -d -o bench -g bench /opt/bench /opt/bench/results
for p in '"$*"'; do rm -rf "/opt/bench/$p"; done
tar -xzf /tmp/bench-sync.tgz -C /opt/bench
echo "'"${REVISION:-unknown}"'" > /opt/bench/REVISION
chown -R bench:bench /opt/bench
find /opt/bench -name "*.sh" -exec chmod +x {} +
rm -f /tmp/bench-sync.tgz
echo "synced: '"$*"' @ $(cat /opt/bench/REVISION)"'
printf '%s\n' "${SSHPASS}" | "${SSH[@]}" "sudo -S -p '' bash -c $(printf '%q' "${REMOTE}")"
