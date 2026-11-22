# SEN421 Topic 2: Virtual Machines vs. Containers

The same Flask API runs in two isolated environments on one laptop:

| Alternative | Stack | Resources |
|---|---|---|
| **VM** | VirtualBox 7.2 → Ubuntu 22.04 cloud image (own kernel 5.15) → systemd → gunicorn | 2 vCPU, 2 GB RAM |
| **Container** | Docker Desktop 29.6 (WSL2 kernel 6.18) → `python:3.10-slim` → gunicorn | `--cpus 2 --memory 2g` |

Measured: image size, startup time (start command → first HTTP 200), memory (idle and under load), and throughput/latency with k6 (50 VUs, 30 s, 3 runs, `/hello` and `/compute`).

## Repository layout

```
app/        Flask API (app.py), requirements.txt, Dockerfile
vm/         cloud-init template, seed ISO builder, VirtualBox creation script
scripts/    run_benchmarks.py (all measurements), load_test.js (k6), make_figures.py
results/    raw CSV/JSON results, environment.json, figures/
```

## Reproduce

Prerequisites (Windows 11): Docker Desktop, VirtualBox 7.2, k6, Python 3.10+ with `pandas`, `matplotlib`, `pycdlib`.

```powershell
# 1. Container image
docker build -t sen421-api:1.0 app

# 2. VM (downloads ~670 MB Ubuntu 22.04 cloud image)
curl.exe -L -o D:\vbox\jammy.ova https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.ova
ssh-keygen -t ed25519 -N "" -f D:\vbox\sen421_key
python vm\build_seed_iso.py D:\vbox\sen421_key.pub D:\vbox\seed.iso
powershell -File vm\create_vm.ps1
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm sen421-vm --type headless   # first boot runs cloud-init

# 3. Measurements and figures
python scripts\run_benchmarks.py --startup-runs 5 --load-runs 3
python scripts\make_figures.py
```

## Cleanup

```powershell
docker rm -f sen421-c; docker rmi sen421-api:1.0
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" unregistervm sen421-vm --delete
```

No secrets are stored in this repository: the VM uses an SSH key that is generated locally and kept outside the repo; password login is disabled.
