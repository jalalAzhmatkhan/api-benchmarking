#!/usr/bin/env bash
# Idempotent provisioning for the API benchmarking VMs. Runs ON the VM as root.
#
#   provision.sh dev      [b64:"<k6 bench pubkey>"]                 system under test (Docker host)
#   provision.sh k6                                                  load generator (k6)
#   provision.sh link     b64:"<sut_public_ip> <sut_private_ip> <hostkey type> <hostkey>"   (on k6)
#   provision.sh finalize                                            report + reboot if a kernel update needs it
#
# Machine-readable lines for the caller are prefixed with "OUT|" (key=value) and "REPORT|" (key|value).
set -euo pipefail
exec </dev/null

ROLE="${1:?usage: provision.sh <dev|k6|link|finalize> [base64-arg]}"
ARG="$(printf '%s' "${2:-}" | base64 -d 2>/dev/null || true)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$HERE")"
K6_VERSION="${K6_VERSION:-2.3.0}"
BENCH_USER=bench
BENCH_HOME="/home/${BENCH_USER}"
ADMIN_USER="${SUDO_USER:-ubuntu}"

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1
APT_OPTS=(-y -q -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

log() { printf '\n==> %s\n' "$*"; }
out() { printf 'OUT|%s=%s\n' "$1" "$2"; }
report() { printf 'REPORT|%s|%s\n' "$1" "$2"; }

[[ ${EUID} -eq 0 ]] || { echo "provision.sh must run as root" >&2; exit 1; }
# shellcheck source=/dev/null
. /etc/os-release
ARCH="$(dpkg --print-architecture)"

# ─── shared ──────────────────────────────────────────────────────────────────
base_packages() {
  log "Base packages (${PRETTY_NAME}, ${ARCH})"
  echo "iperf3 iperf3/start_daemon boolean false" | debconf-set-selections
  apt-get -o DPkg::Lock::Timeout=600 update -q
  apt-get upgrade "${APT_OPTS[@]}"
  apt-get install "${APT_OPTS[@]}" \
    ca-certificates curl gnupg git jq tmux htop sysstat iperf3 chrony rsync unzip gzip \
    python3 python3-venv fail2ban
  systemctl enable --now chrony
  # fail2ban's default sshd jail protects the password-SSH login used by the provisioning workflow.
  systemctl enable --now fail2ban || echo "WARN: fail2ban did not start; continuing"
}

tune_kernel() {
  log "Kernel / limits / swap"
  # Ubuntu's 99-sysctl.conf (→ /etc/sysctl.conf) sorts after "99-bench" and cloud images set some of
  # the same keys there, so: install under a name that sorts last and neutralize managed keys elsewhere.
  rm -f /etc/sysctl.d/99-bench.conf
  install -m 0644 "${DEPLOY_DIR}/sysctl/99-bench.conf" /etc/sysctl.d/zz-bench.conf
  local key
  for key in $(awk -F= '/^[a-z]/{gsub(/[ \t]/,"",$1); print $1}' /etc/sysctl.d/zz-bench.conf); do
    sed -ri "s@^[[:space:]]*(${key//./\\.}[[:space:]]*=.*)@# overridden by zz-bench.conf: \1@" \
      /etc/sysctl.conf $(find /etc/sysctl.d -maxdepth 1 -type f -name '*.conf' ! -name zz-bench.conf) 2>/dev/null || true
  done
  sysctl --system >/dev/null
  # Fail loudly if any managed value did not take effect.
  local want have bad=0
  while IFS='=' read -r key want; do
    key="$(echo "${key}" | xargs)"; want="$(echo "${want}" | xargs)"
    [[ -z "${key}" || "${key}" == \#* ]] && continue
    have="$(sysctl -n "${key}" | xargs)"
    if [[ "${have}" != "${want}" ]]; then echo "sysctl mismatch: ${key}=${have} (want ${want})" >&2; bad=1; fi
  done < /etc/sysctl.d/zz-bench.conf
  [[ ${bad} -eq 0 ]] || exit 1
  cat > /etc/security/limits.d/99-bench.conf <<'EOF'
*     soft nofile 1048576
*     hard nofile 1048576
root  soft nofile 1048576
root  hard nofile 1048576
EOF
  install -d /etc/systemd/system.conf.d
  printf '[Manager]\nDefaultLimitNOFILE=1048576\n' > /etc/systemd/system.conf.d/99-bench.conf
  systemctl daemon-reexec
  # Swap off: memory pressure must surface as OOM, not as noisy latency.
  swapoff -a
  sed -ri 's@^([^#].*[[:space:]]swap[[:space:]].*)$@# disabled by bench provisioning: \1@' /etc/fstab
}

ensure_bench_user() {
  log "Service user '${BENCH_USER}' (key-only, no password)"
  id "${BENCH_USER}" &>/dev/null || useradd -m -s /bin/bash "${BENCH_USER}"
  install -d -m 700 -o "${BENCH_USER}" -g "${BENCH_USER}" "${BENCH_HOME}/.ssh"
  install -d -m 755 -o "${BENCH_USER}" -g "${BENCH_USER}" /var/lib/bench /var/lib/bench/runs
}

host_report() {
  report "os" "${PRETTY_NAME}"
  report "kernel" "$(uname -r)"
  report "arch" "${ARCH}"
  report "vcpu" "$(nproc)"
  report "cpu_model" "$(lscpu | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
  report "memory" "$(free -h | awk '/^Mem:/{print $2}')"
  report "swap" "$(free -h | awk '/^Swap:/{print $2}')"
  report "disk_root" "$(df -h / | awk 'NR==2{print $2" total, "$4" free"}')"
  report "cgroup_fs" "$(stat -fc %T /sys/fs/cgroup)"
  report "psi" "$([[ -r /proc/pressure/cpu ]] && echo enabled || echo MISSING)"
  report "nofile_limit" "$(su - "${BENCH_USER}" -c 'ulimit -n' 2>/dev/null || echo n/a)"
  report "somaxconn" "$(sysctl -n net.core.somaxconn)"
  report "ip_local_port_range" "$(sysctl -n net.ipv4.ip_local_port_range | xargs)"
  report "steal_pct_avg_5s" "$(vmstat 1 6 | awk 'NR>3{s+=$NF; n++} END{printf "%.1f", s/n}')"
  report "reboot_required" "$([[ -f /var/run/reboot-required ]] && echo yes || echo no)"
}

# ─── DEV_SERVER (system under test) ─────────────────────────────────────────
install_docker() {
  log "Docker Engine + Compose"
  if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    local codename="${UBUNTU_CODENAME:-${VERSION_CODENAME}}"
    if ! curl -fsSL "https://download.docker.com/linux/ubuntu/dists/${codename}/Release" >/dev/null 2>&1; then
      echo "Docker repo has no '${codename}' suite yet; falling back to 'noble'"
      codename=noble
    fi
    echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get -o DPkg::Lock::Timeout=600 update -q
    apt-get install "${APT_OPTS[@]}" docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi
  install -d /etc/docker
  install -m 0644 "${DEPLOY_DIR}/docker/daemon.json" /etc/docker/daemon.json
  systemctl enable docker >/dev/null
  systemctl restart docker
  usermod -aG docker "${BENCH_USER}"
  id "${ADMIN_USER}" &>/dev/null && usermod -aG docker "${ADMIN_USER}"
}

authorize_k6_key() {
  local pubkey="$1"
  [[ -n "${pubkey}" ]] || { echo "No k6 bench key supplied; skipping authorization"; return; }
  log "Authorize K6_SERVER bench key for ${BENCH_USER}@dev"
  local ak="${BENCH_HOME}/.ssh/authorized_keys"
  touch "${ak}"
  grep -qxF "${pubkey}" "${ak}" || echo "${pubkey}" >> "${ak}"
  chown "${BENCH_USER}:${BENCH_USER}" "${ak}"
  chmod 600 "${ak}"
}

role_dev() {
  base_packages
  tune_kernel
  ensure_bench_user
  install_docker
  authorize_k6_key "${ARG}"
  local private_ip
  private_ip="$(ip -4 route get 1.1.1.1 | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
  out "sut_private_ip" "${private_ip}"
  out "sut_hostkey" "$(awk '{print $1" "$2}' /etc/ssh/ssh_host_ed25519_key.pub)"
  report "docker" "$(docker version --format '{{.Server.Version}}')"
  report "compose" "$(docker compose version --short)"
  report "cgroup_driver" "$(docker info --format '{{.CgroupDriver}} / cgroup v{{.CgroupVersion}}')"
  host_report
}

# ─── K6_SERVER (load generator) ─────────────────────────────────────────────
install_k6() {
  log "k6 v${K6_VERSION}"
  if command -v k6 >/dev/null && k6 version 2>/dev/null | grep -q "v${K6_VERSION}"; then
    echo "k6 v${K6_VERSION} already installed"; return
  fi
  local tmp tarball base bin
  tmp="$(mktemp -d)"
  base="https://github.com/grafana/k6/releases/download/v${K6_VERSION}"
  tarball="k6-v${K6_VERSION}-linux-${ARCH}.tar.gz"
  curl -fsSL -o "${tmp}/${tarball}" "${base}/${tarball}"
  curl -fsSL -o "${tmp}/checksums.txt" "${base}/k6-v${K6_VERSION}-checksums.txt"
  (cd "${tmp}" && grep " ${tarball}\$" checksums.txt | sha256sum -c -)
  tar -xzf "${tmp}/${tarball}" -C "${tmp}"
  bin="$(find "${tmp}" -type f -name k6 | head -n1)"
  install -m 0755 "${bin}" /usr/local/bin/k6
  rm -rf "${tmp}"
}

ensure_bench_keypair() {
  log "SSH key pair for ${BENCH_USER}@k6 (used to orchestrate DEV_SERVER)"
  if [[ ! -f "${BENCH_HOME}/.ssh/id_ed25519" ]]; then
    sudo -u "${BENCH_USER}" ssh-keygen -q -t ed25519 -N "" -C "bench@k6-server" -f "${BENCH_HOME}/.ssh/id_ed25519"
  fi
  out "bench_pubkey" "$(cat "${BENCH_HOME}/.ssh/id_ed25519.pub")"
}

role_k6() {
  base_packages
  tune_kernel
  ensure_bench_user
  install_k6
  ensure_bench_keypair
  report "k6" "$(k6 version | head -n1)"
  host_report
}

role_link() {
  # ARG = "<public ip|-> <private ip|-> <hostkey type> <hostkey>"  ("-" marks an unknown address)
  local pub priv ktype kdata target
  read -r pub priv ktype kdata <<<"${ARG}"
  [[ "${pub}" == "-" ]] && pub=""
  [[ "${priv}" == "-" ]] && priv=""
  [[ -n "${ktype}" && -n "${kdata}" ]] || { echo "link: missing SUT host key" >&2; exit 1; }
  log "Link ${BENCH_USER}@k6 → ${BENCH_USER}@dev"
  # Prefer the provider's private network when it is reachable (lower, steadier RTT).
  if [[ -n "${priv}" ]] && timeout 3 bash -c "</dev/tcp/${priv}/22" 2>/dev/null; then
    target="${priv}"; report "lg_to_sut_path" "private network"
  elif [[ -n "${pub}" ]]; then
    target="${pub}"; report "lg_to_sut_path" "public IP (no private route)"
  else
    echo "link: no reachable SUT address" >&2; exit 1
  fi
  local kh="${BENCH_HOME}/.ssh/known_hosts"
  touch "${kh}"
  for h in ${priv} ${pub}; do
    ssh-keygen -R "${h}" -f "${kh}" >/dev/null 2>&1 || true
    echo "${h} ${ktype} ${kdata}" >> "${kh}"
  done
  cat > "${BENCH_HOME}/.ssh/config" <<EOF
Host sut
  HostName ${target}
  User ${BENCH_USER}
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  ServerAliveInterval 30
EOF
  chown -R "${BENCH_USER}:${BENCH_USER}" "${BENCH_HOME}/.ssh"
  chmod 600 "${BENCH_HOME}/.ssh/config" "${kh}"
  install -d /etc/bench
  printf 'SUT_HOST=%s\nBASE_URL=http://%s:8080\n' "${target}" "${target}" > /etc/bench/sut.env
  chmod 644 /etc/bench/sut.env
  report "lg_to_sut_ssh" "$(sudo -u "${BENCH_USER}" ssh -o BatchMode=yes sut \
    'echo ok: docker $(docker version --format "{{.Server.Version}}")' 2>&1 | tail -n1)"
  local rtt
  rtt="$(ping -c 20 -i 0.2 -q "${target}" 2>/dev/null | awk -F/ '/rtt|round-trip/{print $5" ms avg, "$7" ms mdev"}' || true)"
  report "lg_to_sut_rtt" "${rtt:-n/a (ICMP blocked)}"
}

role_finalize() {
  host_report
  if [[ -f /var/run/reboot-required ]]; then
    log "Kernel/libc update installed: rebooting in 1 minute"
    systemd-run --on-active=60 --unit=bench-reboot systemctl reboot >/dev/null
    report "reboot" "scheduled in 60 s"
  else
    report "reboot" "not needed"
  fi
}

case "${ROLE}" in
  dev)      role_dev ;;
  k6)       role_k6 ;;
  link)     role_link ;;
  finalize) role_finalize ;;
  *) echo "unknown role: ${ROLE}" >&2; exit 2 ;;
esac
log "Done: ${ROLE}"
