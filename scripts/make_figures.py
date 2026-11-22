"""Turn results/*.csv into report figures and a summary table.

Outputs (results/figures/): fig_architecture.pdf/png, fig_startup.pdf/png,
fig_throughput.pdf/png, fig_memory.pdf/png and results/summary.json
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = RES / "figures"
FIG.mkdir(parents=True, exist_ok=True)

C_CONT = "#2a78b5"   # container colour
C_VM = "#d9822b"     # VM colour
plt.rcParams.update({"font.size": 9, "font.family": "serif",
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def mean_sd(series):
    return float(series.mean()), float(series.std(ddof=1)) if len(series) > 1 else 0.0


# ------------------------------------------------------------ architecture
def architecture():
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 74)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec="#333", fs=7.5, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                    fc=fc, ec=ec, lw=0.9))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                weight="bold" if bold else "normal")

    # hardware + hypervisor layers
    box(2, 2, 96, 6, "Host hardware: Intel Core i7-12700H (20 threads), 16 GB RAM, NVMe SSD",
        "#e6e6e6", bold=True)
    box(2, 10, 96, 5, "Microsoft Hyper-V hypervisor (Type-1, enabled by WSL2) - owns VT-x",
        "#cfcfcf")

    # left stack: VirtualBox VM
    box(2, 17, 46, 6, "Windows 11 root partition\nVirtualBox 7.2 via Windows Hypervisor Platform (NEM)",
        "#fbe3cc", fs=7)
    box(4, 25, 42, 23, "", "#fff4ea", ec=C_VM)
    ax.text(25, 45.5, "Alternative 1: VirtualBox VM (2 vCPU, 2 GB)", ha="center",
            fontsize=7.5, weight="bold", color=C_VM)
    box(6, 27, 38, 5, "Guest kernel: Linux 5.15 (Ubuntu 22.04)", "#fde9d6", fs=7)
    box(6, 33.5, 38, 4.5, "systemd + cloud-init + sshd", "#fde9d6", fs=7)
    box(6, 39.5, 38, 4.5, "gunicorn (2 workers) + Flask API :8000", "white", fs=7)

    # right stack: container
    box(52, 17, 46, 6, "WSL2 utility VM\nshared Linux kernel 6.18 (microsoft-standard-WSL2)",
        "#d6e6f5", fs=7)
    box(54, 25, 42, 23, "", "#eef5fb", ec=C_CONT)
    ax.text(75, 45.5, "Alternative 2: Docker container (2 CPU, 2 GB)", ha="center",
            fontsize=7.5, weight="bold", color=C_CONT)
    box(56, 27, 38, 5, "Docker Engine 29.6: containerd + runc", "#dbe9f6", fs=7)
    box(56, 33.5, 38, 4.5, "namespaces + cgroups (no guest kernel)", "#dbe9f6", fs=7)
    box(56, 39.5, 38, 4.5, "python:3.10-slim: gunicorn (2) + Flask :8000", "white", fs=7)

    # clients
    box(20, 60, 60, 9, "Windows host: k6 load generator (10 / 50 VUs) +\nrun_benchmarks.py (startup, memory, size probes)",
        "#f2f2f2", fs=7.5, bold=True)
    ax.annotate("", xy=(25, 48.5), xytext=(35, 59.5),
                arrowprops=dict(arrowstyle="-|>", color=C_VM, lw=1.3))
    ax.text(19, 54, "HTTP 127.0.0.1:8080\nVirtualBox NAT\nport forward", fontsize=6.5,
            ha="center", color=C_VM)
    ax.annotate("", xy=(75, 48.5), xytext=(65, 59.5),
                arrowprops=dict(arrowstyle="-|>", color=C_CONT, lw=1.3))
    ax.text(83, 54, "HTTP 127.0.0.1:8000\nDocker Desktop\nport publish", fontsize=6.5,
            ha="center", color=C_CONT)
    save(fig, "fig_architecture")


# ------------------------------------------------------------ results
ALTS = ["container", "container-jammy", "vm"]
LABELS = {"container": "Container\n(slim)", "container-jammy": "Container\n(jammy)",
          "vm": "VirtualBox\nVM"}
COLORS = {"container": C_CONT, "container-jammy": "#7fb3dc", "vm": C_VM}


def load_all():
    """Merge main, supplementary and control CSVs into tidy frames."""
    st = pd.concat([pd.read_csv(RES / "startup.csv"), pd.read_csv(RES / "control_startup.csv")])
    tp50 = pd.read_csv(RES / "throughput.csv").assign(vus=50)
    tp10 = pd.read_csv(RES / "throughput_10vus.csv")
    ctl = pd.read_csv(RES / "control_throughput.csv")
    tp = pd.concat([tp50, tp10, ctl])
    tp["good_rps"] = tp["rps"] * (1 - tp["error_rate"])
    mem = pd.concat([pd.read_csv(RES / "memory.csv"), pd.read_csv(RES / "control_memory.csv")])
    micro = pd.concat([pd.read_csv(RES / "cpu_microbench_settled.csv"),
                       pd.read_csv(RES / "control_cpu_microbench.csv")])
    return st, tp, mem, micro


def results():
    st_all, tp, mem, micro = load_all()
    summary = {"size_mb": dict(zip(*[pd.read_csv(RES / "image_size.csv")[c]
                                     for c in ("artifact", "size_mb")]))}

    summary["startup_attempts"] = {a: {"total": int(len(g)), "hang": int((g["status"] == "hang").sum())}
                                   for a, g in st_all.groupby("alternative")}
    st = st_all[st_all["status"] == "ok"].copy()
    st["ready_s"] = st["ready_s"].astype(float)
    summary["startup_s"] = {a: mean_sd(g["ready_s"]) for a, g in st.groupby("alternative")}
    summary["startup_runs"] = {a: g["ready_s"].tolist() for a, g in st.groupby("alternative")}

    summary["memory_mb"] = {}
    for (alt, phase), g in mem.groupby(["alternative", "phase"]):
        e = {"used": mean_sd(g["guest_or_cgroup_used_mb"])}
        if alt == "vm":
            for k in ("app_rss_mb", "host_ws_mb", "host_private_mb"):
                e[k] = mean_sd(g[k].astype(float))
        summary["memory_mb"][f"{alt} | {phase}"] = e

    summary["throughput"] = {}
    for (alt, vus, ep), g in tp.groupby(["alternative", "vus", "endpoint"]):
        summary["throughput"][f"{alt} | {vus} VUs | {ep}"] = {
            "rps": mean_sd(g["rps"]), "good_rps": mean_sd(g["good_rps"]),
            "med_ms": mean_sd(g["lat_med_ms"]), "p95_ms": mean_sd(g["lat_p95_ms"]),
            "err_mean": float(g["error_rate"].mean()), "err_max": float(g["error_rate"].max())}
    summary["microbench_s"] = {a: mean_sd(g["seconds"]) for a, g in micro.groupby("alternative")}
    (RES / "summary.json").write_text(json.dumps(summary, indent=2))

    # Fig: startup (log scale, individual runs as dots)
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for i, a in enumerate(ALTS):
        m, s = summary["startup_s"][a]
        runs = summary["startup_runs"][a]
        ax.bar(i, m, color=COLORS[a], width=0.6)
        ax.errorbar(i, m, yerr=s, color="black", capsize=4, lw=0.8)
        ax.scatter([i] * len(runs), runs, color="black", s=7, zorder=3)
        ax.text(i, max(runs) * 1.45, f"{m:.2f} s" if m < 5 else f"{m:.1f} s", ha="center", fontsize=8)
    ax.set_xticks(range(len(ALTS)), [LABELS[a] for a in ALTS])
    ax.set_yscale("log")
    ax.set_ylim(0.1, 150)
    ax.set_ylabel("Time to first HTTP 200 (s)")
    save(fig, "fig_startup")

    # Fig: throughput at 10 VUs (no errors on any alternative)
    fig, axes = plt.subplots(1, 2, figsize=(3.4, 2.4))
    for k, ep in enumerate(["/hello", "/compute"]):
        ax = axes[k]
        for i, a in enumerate(ALTS):
            m, s = summary["throughput"][f"{a} | 10 VUs | {ep}"]["rps"]
            ax.bar(i, m, color=COLORS[a], width=0.65)
            ax.errorbar(i, m, yerr=s, color="black", capsize=3, lw=0.8)
            ax.text(i, m + s, f"{m:.0f}", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(3), ["slim", "jammy", "VM"], fontsize=7)
        ax.set_title(f"GET {ep}", fontsize=8)
        ax.margins(y=0.15)
        if k == 0:
            ax.set_ylabel("Throughput (requests/s)")
    save(fig, "fig_throughput")

    # Fig: memory footprint
    m = summary["memory_mb"]
    vals = [("Container\n(cgroup)", m["container | idle"]["used"][0], C_CONT),
            ("VM guest\n(free used)", m["vm | idle"]["used"][0], C_VM),
            ("VM app\nonly (RSS)", m["vm | idle"]["app_rss_mb"][0], "#f0b27a"),
            ("VM process\non host", m["vm | idle"]["host_private_mb"][0], "#8c4a10")]
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for i, (lab, v, c) in enumerate(vals):
        ax.bar(i, v, color=c, width=0.6)
        ax.text(i, v * 1.15, f"{v:.0f}", ha="center", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylim(10, 6000)
    ax.set_xticks(range(len(vals)), [v[0] for v in vals], fontsize=7)
    ax.set_ylabel("Idle memory (MiB)")
    save(fig, "fig_memory")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    architecture()
    if (RES / "throughput.csv").exists():
        results()
