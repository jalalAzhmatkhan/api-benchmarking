# deploy/

Infrastructure for the benchmark VMs. Design: `Documentation/plans/deployment-plan.md`.

| Path | Purpose |
|---|---|
| `provision/provision.sh` | Idempotent VM setup, run on the VM as root. Roles: `dev`, `k6`, `link`, `finalize` |
| `provision/remote.sh` | Runs a role from GitHub Actions over password SSH (password comes from the env secret) |
| `sysctl/99-bench.conf` | Network/FD tuning, identical on both VMs |
| `docker/daemon.json` | Docker daemon config for DEV_SERVER |

## Provisioning the VMs
Run the **Provision VMs** workflow (Actions → Provision VMs → Run workflow), or:

```bash
gh workflow run provision-vms.yml -f target=both -f k6_version=2.3.0
```

What it installs:

| | DEV_SERVER (SUT) | K6_SERVER (load generator) |
|---|---|---|
| OS updates, base tools (git, jq, tmux, htop, sysstat, iperf3, chrony, rsync, python3) | ✔ | ✔ |
| sysctl tuning, `nofile` 1 048 576, swap off | ✔ | ✔ |
| fail2ban (protects password SSH) | ✔ | ✔ |
| `bench` service user (key-only), `/var/lib/bench/runs` | ✔ | ✔ |
| Docker Engine + Compose plugin, `daemon.json` | ✔ | — |
| k6 (pinned version, checksum-verified) | — | ✔ |
| `ssh sut` from `bench@k6` → `bench@dev` (private network if reachable), `/etc/bench/sut.env` | authorizes key | configures |

The job summary of each run reports OS, kernel, vCPU, memory, cgroup/PSI, CPU steal, versions and
LG↔SUT RTT. If a kernel update needs it, the VMs reboot automatically one minute after the run.

## Deferred hardening (T-5.1)
Firewall rules (`ufw`) and disabling SSH password authentication are **not** applied yet, because the
workflow logs in with the password. They will be enabled once CI uses an SSH deploy key. Until then, restrict
port 22 (and later 8080) in the cloud provider's security group.
