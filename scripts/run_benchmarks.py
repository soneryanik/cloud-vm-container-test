"""Run every measurement of the SEN421 VM vs. container experiment.

Alternatives
  container : Docker container (python:3.10-slim + gunicorn), --cpus 2 --memory 2g
  vm        : VirtualBox VM (Ubuntu 22.04 cloud image), 2 vCPU, 2 GB RAM

Metrics (each repeated, raw values written to results/*.csv)
  1. image size   - Docker image size vs. VM disk image size
  2. startup time - start command -> first HTTP 200 on /health
  3. memory       - idle and under load
  4. throughput   - k6, 50 VUs, 30 s, /hello and /compute

Only one alternative runs at a time, so they never compete for the host.
Usage: python run_benchmarks.py [--startup-runs 5] [--load-runs 3]
"""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import platform
import statistics
import subprocess
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"

VBOX = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
K6 = r"C:\Program Files\k6\k6.exe"
VM_NAME = "sen421-vm"
VM_DISK = pathlib.Path(r"D:\vbox\vms\sen421-vm\ubuntu-jammy-22.04-cloudimg.vmdk")
VM_OVA = pathlib.Path(r"D:\vbox\jammy.ova")
SSH_KEY = r"D:\vbox\sen421_key"
IMAGE = "sen421-api:1.0"
CONTAINER = "sen421-c"

TARGETS = {
    "container": "http://127.0.0.1:8000",
    "vm": "http://127.0.0.1:8080",
}
ENDPOINTS = ["/hello", "/compute"]
VUS, DURATION = 50, "30s"


# ---------------------------------------------------------------- helpers
def sh(cmd, check=True, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def http_ok(url, timeout=1.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_http(url, limit_s, interval):
    """Poll url until HTTP 200; return seconds since call (perf_counter)."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit_s:
        if http_ok(url, timeout=0.5):
            return time.perf_counter() - t0
        time.sleep(interval)
    raise TimeoutError(url)


def write_csv(name, rows):
    path = RESULTS / name
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {path.relative_to(ROOT)} ({len(rows)} rows)")


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- container
def container_stop():
    sh(["docker", "rm", "-f", CONTAINER], check=False)


def container_start():
    sh(["docker", "run", "-d", "--name", CONTAINER, "-p", "8000:8000",
        "--cpus", "2", "--memory", "2g", IMAGE])


def container_mem_mb():
    out = sh(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", CONTAINER])
    used = out.split("/")[0].strip()
    num = float("".join(c for c in used if c.isdigit() or c == "."))
    if "GiB" in used:
        return num * 1024
    if "KiB" in used:
        return num / 1024
    return num  # MiB


# ---------------------------------------------------------------- vm
def vm_state():
    # showvminfo can fail transiently while a VM is shutting down
    out = sh([VBOX, "showvminfo", VM_NAME, "--machinereadable"], check=False)
    for line in out.splitlines():
        if line.startswith("VMState="):
            return line.split("=", 1)[1].strip('"')
    return "unknown"


def vm_stop():
    if vm_state() == "poweroff":
        return
    sh([VBOX, "controlvm", VM_NAME, "acpipowerbutton"], check=False)
    t0 = time.time()
    while time.time() - t0 < 90:
        if vm_state() == "poweroff":
            break
        time.sleep(1)
    else:
        sh([VBOX, "controlvm", VM_NAME, "poweroff"], check=False)
    time.sleep(3)  # let VirtualBox release the session lock


def vm_start():
    sh([VBOX, "startvm", VM_NAME, "--type", "headless"])


def vm_ssh(cmd):
    return sh(["ssh", "-i", SSH_KEY, "-p", "2222", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=NUL", "-o", "LogLevel=ERROR",
               "sen421@127.0.0.1", cmd])


def vm_guest_used_mb():
    # "used" column of free -m (excludes page cache), comparable to cgroup usage
    line = [l for l in vm_ssh("free -m").splitlines() if l.startswith("Mem:")][0]
    return float(line.split()[2])


def vm_app_rss_mb():
    out = vm_ssh("ps -o rss= -C gunicorn")
    return sum(int(x) for x in out.split()) / 1024


def vm_host_process_mb():
    """Working set and private bytes of the VBoxHeadless process on Windows."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='VBoxHeadless.exe'\" | "
          "Sort-Object WorkingSetSize -Descending | Select-Object -First 1 | "
          "ForEach-Object { '{0} {1}' -f $_.WorkingSetSize, $_.PrivatePageCount }")
    ws, priv = sh(["powershell", "-NoProfile", "-Command", ps]).split()
    return int(ws) / 2**20, int(priv) / 2**20


# ---------------------------------------------------------------- metrics
def measure_sizes():
    log("1) image sizes")
    img_bytes = int(sh(["docker", "image", "inspect", IMAGE, "--format", "{{.Size}}"]))
    base_bytes = int(sh(["docker", "image", "inspect", "python:3.10-slim", "--format", "{{.Size}}"]))
    rows = [
        {"alternative": "container", "artifact": f"Docker image {IMAGE}",
         "size_mb": round(img_bytes / 2**20, 1)},
        {"alternative": "container", "artifact": "base image python:3.10-slim",
         "size_mb": round(base_bytes / 2**20, 1)},
        {"alternative": "vm", "artifact": "VM disk (vmdk, after setup)",
         "size_mb": round(VM_DISK.stat().st_size / 2**20, 1)},
        {"alternative": "vm", "artifact": "Ubuntu cloud image download (ova)",
         "size_mb": round(VM_OVA.stat().st_size / 2**20, 1)},
    ]
    write_csv("image_size.csv", rows)


VM_BOOT_TIMEOUT_S = 120  # a healthy boot takes ~30 s; longer means a hang


def vm_hard_off():
    sh([VBOX, "controlvm", VM_NAME, "poweroff"], check=False)
    t0 = time.time()
    while vm_state() != "poweroff" and time.time() - t0 < 30:
        time.sleep(1)
    time.sleep(3)


def measure_startup(alt, runs, max_attempts=15):
    """Repeat until `runs` successful starts. Failed (hung) VM boots are kept
    in the CSV with status=hang so the failure rate can be reported."""
    log(f"2) startup time: {alt} x{runs}")
    rows, ok, attempt = [], 0, 0
    while ok < runs and attempt < max_attempts:
        attempt += 1
        if alt == "container":
            container_stop()
            time.sleep(2)
            t0 = time.perf_counter()
            container_start()
            t_cmd = time.perf_counter() - t0
            t_ready = t_cmd + wait_http(TARGETS[alt] + "/health", 60, 0.02)
            status = "ok"
        else:
            vm_stop()
            time.sleep(5)
            t0 = time.perf_counter()
            vm_start()
            t_cmd = time.perf_counter() - t0
            try:
                t_ready = t_cmd + wait_http(TARGETS[alt] + "/health", VM_BOOT_TIMEOUT_S, 0.1)
                status = "ok"
            except TimeoutError:
                t_ready, status = "", "hang"
                vm_hard_off()
        if status == "ok":
            ok += 1
        rows.append({"alternative": alt, "attempt": attempt, "status": status,
                     "start_cmd_s": round(t_cmd, 3),
                     "ready_s": round(t_ready, 3) if t_ready != "" else ""})
        log(f"   attempt {attempt}: {status}" + (f", ready after {t_ready:.2f} s" if status == "ok" else ""))
    if ok < runs:
        raise RuntimeError(f"{alt}: only {ok} successful starts in {attempt} attempts")
    if alt == "vm":
        time.sleep(30)  # let background boot jobs (snapd, cloud-init) settle before load tests
    return rows


def memory_snapshot(alt, phase):
    if alt == "container":
        return {"alternative": alt, "phase": phase,
                "guest_or_cgroup_used_mb": round(container_mem_mb(), 1),
                "app_rss_mb": "", "host_ws_mb": "", "host_private_mb": ""}
    ws, priv = vm_host_process_mb()
    return {"alternative": alt, "phase": phase,
            "guest_or_cgroup_used_mb": round(vm_guest_used_mb(), 1),
            "app_rss_mb": round(vm_app_rss_mb(), 1),
            "host_ws_mb": round(ws, 1), "host_private_mb": round(priv, 1)}


def run_k6(alt, endpoint, run, record=True):
    tag = f"{alt}_{endpoint.strip('/')}_run{run}"
    summary = RAW / f"k6_{tag}.json"
    env = dict(os.environ, BASE_URL=TARGETS[alt], ENDPOINT=endpoint,
               VUS=str(VUS), DURATION=DURATION if record else "10s")
    cmd = [K6, "run", "--quiet", str(ROOT / "scripts" / "load_test.js")]
    if record:
        cmd += ["--summary-export", str(summary)]
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    if not record:
        return None
    m = json.loads(summary.read_text())["metrics"]
    d = m["http_req_duration"]
    return {"alternative": alt, "endpoint": endpoint, "run": run,
            "rps": round(m["http_reqs"]["rate"], 1),
            "requests": m["http_reqs"]["count"],
            "lat_avg_ms": round(d["avg"], 2), "lat_med_ms": round(d["med"], 2),
            "lat_p95_ms": round(d["p(95)"], 2), "lat_p99_ms": round(d["p(99)"], 2),
            "error_rate": m["http_req_failed"]["value"]}


def measure_load(alt, runs, mem_rows):
    rows = []
    for ep in ENDPOINTS:
        log(f"4) throughput: {alt} {ep} (warm-up 10 s)")
        run_k6(alt, ep, 0, record=False)
        for i in range(1, runs + 1):
            snap = {}
            # sample memory 15 s into the 30 s run
            t = threading.Timer(15, lambda: snap.update(memory_snapshot(alt, f"load{ep}")))
            t.start()
            row = run_k6(alt, ep, i)
            t.join()
            if snap:
                snap["run"] = i
                mem_rows.append(snap)
            rows.append(row)
            log(f"   run {i}: {row['rps']} req/s, p95 {row['lat_p95_ms']} ms")
            time.sleep(10)
    return rows


def environment():
    info = {
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "host_os": platform.platform(),
        "host_cpu": sh(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Processor).Name"]),
        "host_logical_cpus": os.cpu_count(),
        "docker": sh(["docker", "version", "--format", "{{.Server.Version}}"]),
        "virtualbox": sh([VBOX, "--version"]),
        "k6": sh([K6, "version"]).splitlines()[0],
        "load": f"{VUS} VUs, {DURATION} per run, 10 s warm-up",
    }
    (RESULTS / "environment.json").write_text(json.dumps(info, indent=2))
    return info


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--startup-runs", type=int, default=5)
    ap.add_argument("--load-runs", type=int, default=3)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    log(json.dumps(environment(), indent=2))
    measure_sizes()

    startup, load, mem = [], [], []
    for alt in ("container", "vm"):
        # isolate: stop the other alternative first
        (vm_stop if alt == "container" else container_stop)()
        startup += measure_startup(alt, args.startup_runs)
        log(f"3) idle memory: {alt} (after 30 s idle)")
        for i in range(1, 4):
            time.sleep(10)
            snap = memory_snapshot(alt, "idle")
            snap["run"] = i
            mem.append(snap)
        load += measure_load(alt, args.load_runs, mem)
        # write after each alternative so a later failure keeps finished data
        write_csv("startup.csv", startup)
        write_csv("memory.csv", mem)
        write_csv("throughput.csv", load)

    container_stop()
    log("summary")
    for alt in ("container", "vm"):
        r = [x["ready_s"] for x in startup if x["alternative"] == alt and x["status"] == "ok"]
        print(f"  {alt:9s} startup {statistics.mean(r):7.2f} s +- {statistics.stdev(r):.2f}")
    log("done")


if __name__ == "__main__":
    main()
