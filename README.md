# SEN421 Topic 2: Virtual Machines vs. Containers

SEN421 Cloud Architecture and Services, Fall 2026, Part A (hands-on), Istanbul Aydın University.

The same Flask API runs in isolated environments on one Windows laptop, with the same limits (2 vCPU, 2 GB RAM):

| Alternative | Stack |
|---|---|
| **VM** | VirtualBox 7.2.22 (NEM mode on Hyper-V) → Ubuntu 22.04 cloud image (own kernel 5.15, Python 3.10.12, OpenSSL 3.0.2) → systemd → gunicorn |
| **Container (slim)** | Docker Desktop 29.6.1 (WSL2 kernel 6.18) → `python:3.10-slim` (Python 3.10.22, OpenSSL 3.5.7) → gunicorn |
| **Container (jammy), control** | Same Docker host → `ubuntu:22.04`, exactly the VM's Python and OpenSSL versions |

The control container was added after the first results to test whether the CPU gap came from library versions (it did not).

## Key results (22 Nov 2026)

| Metric | Container | VM |
|---|---|---|
| Startup to first HTTP 200 | 0.51 ± 0.18 s (jammy 0.38 s) | 29.97 ± 1.71 s, **8 of 13 boots hung** |
| Image size | 202 MB on disk / 49 MB compressed | 2,724 MiB disk / 666 MiB download |
| Idle memory | 43 MiB (cgroup) | 234 MiB in guest, 2,133 MiB reserved on host |
| `/hello`, 10 VUs | 1,938 ± 93 req/s | 966 ± 6 req/s |
| `/compute`, 10 VUs | 208 ± 4 (jammy 237 ± 3) req/s | 79.8 ± 0.5 req/s |
| `/hello`, 50 VUs | 1,888 req/s, 0% errors | 746 req/s goodput, 48% errors (VirtualBox NAT) |
| Pure CPU, 200k SHA-256 | 0.079 s | 0.27 ± 0.11 s |

Actual experiment cost: **0 USD** (local only).

## Repository layout

```
app/                  Flask API (app.py), requirements.txt
  Dockerfile          container (slim) image, sen421-api:1.0
  Dockerfile.jammy    control image with the VM's userland, sen421-api:jammy
vm/                   cloud-init template, seed ISO builder, VirtualBox creation script
scripts/
  run_benchmarks.py       main suite: size, startup (with hang detection), memory, k6 at 50 VUs
  run_low_concurrency.py  k6 at 10 VUs (separates NAT bottleneck from app limits)
  run_cpu_microbench.py   pure CPU test without HTTP
  check_cpu_features.py   CPU flags + OpenSSL version in each guest, settled microbenchmark
  run_control.py          all container tests repeated with sen421-api:jammy
  load_test.js            k6 script
  make_figures.py         figures and results/summary.json
results/
  *.csv, summary.json     tidy results behind every table and figure
  raw/                    every k6 summary (JSON)
  *_log.txt               console logs of each run
  environment.json        software versions
  azure_prices_raw.json   Azure Retail Prices API response used in the cost model
  wsl2_vm_memory.csv      memory of Docker Desktop's WSL2 VM
  figures/                generated figures
  screenshots/            VM console screenshots (successful and hung boot)
report/               IEEE report and slides: LaTeX sources, PDFs, Word (.docx) and PowerPoint (.pptx) versions
  tools/              tex_to_docx.py and make_pptx.py, which generate the Word and PowerPoint files
```

## Reproduce

Prerequisites (Windows 11): Docker Desktop, VirtualBox 7.2, k6, Python 3.10+ with `pandas`, `matplotlib`, `pycdlib`.

```powershell
# 1. Container images
docker build -t sen421-api:1.0 app
docker build -f app/Dockerfile.jammy -t sen421-api:jammy app

# 2. VM (downloads ~670 MB Ubuntu 22.04 cloud image)
curl.exe -L -o D:\vbox\jammy.ova https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.ova
ssh-keygen -t ed25519 -N "" -f D:\vbox\sen421_key
python vm\build_seed_iso.py D:\vbox\sen421_key.pub D:\vbox\seed.iso
powershell -File vm\create_vm.ps1
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm sen421-vm --type headless   # first boot runs cloud-init

# 3. Measurements (run in this order) and figures
cd scripts
python run_benchmarks.py --startup-runs 5 --load-runs 3
python run_low_concurrency.py
python run_cpu_microbench.py
python check_cpu_features.py
python run_control.py
python make_figures.py
```

On Windows hosts where Hyper-V/WSL2 is active, VirtualBox runs in NEM mode and some VM boots hang; `run_benchmarks.py` records these as `hang` and retries until the requested number of successful boots is reached.

## Cleanup

```powershell
docker rm -f sen421-c
docker rmi sen421-api:1.0 sen421-api:jammy ubuntu:22.04
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" unregistervm sen421-vm --delete
Remove-Item D:\vbox\jammy.ova, D:\vbox\seed.iso, D:\vbox\sen421_key, D:\vbox\sen421_key.pub
```

## Security notes

No secrets are stored in this repository. The VM uses an SSH key generated locally and kept outside the repo; password login is disabled and the port forwards are bound to 127.0.0.1. Known weaknesses of this test setup (documented in the report): the container runs gunicorn as root, and `docker run -p 8000:8000` publishes on all host interfaces.

## AI use

AI assistance (Claude, Anthropic) was used for this project and is declared in the report's AI Tool Use and Originality Declaration.
