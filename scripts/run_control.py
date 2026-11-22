"""Control experiment: repeat container measurements with sen421-api:jammy,
an Ubuntu 22.04 image whose userland (Python 3.10.12, OpenSSL 3.0.2) matches
the VM exactly. Results are labelled alternative=container-jammy.
Outputs: results/control_*.csv
"""
import time

import run_benchmarks as rb
from run_cpu_microbench import CODE

rb.IMAGE = "sen421-api:jammy"
ALT = "container"  # reuse container helpers/targets
LABEL = "container-jammy"


def relabel(rows):
    for r in rows:
        r["alternative"] = LABEL
    return rows


def main():
    rb.vm_stop()
    rb.container_stop()
    startup = relabel(rb.measure_startup(ALT, 5))
    mem = []
    for i in range(1, 4):
        time.sleep(10)
        s = rb.memory_snapshot(ALT, "idle")
        s["run"] = i
        mem.append(s)
    load = []
    for vus in (50, 10):
        rb.VUS = vus
        for ep in rb.ENDPOINTS:
            rb.log(f"{LABEL} {vus} VUs {ep} (warm-up)")
            rb.run_k6(ALT, ep, 0, record=False)
            for i in range(1, 4):
                snap = {}
                row = rb.run_k6(ALT, ep, f"{i}_jammy_{vus}vus")
                row["run"], row["vus"] = i, vus
                load.append(row)
                rb.log(f"   run {i}: {row['rps']} req/s, p95 {row['lat_p95_ms']} ms, err {row['error_rate']:.3f}")
                time.sleep(10)
        if vus == 50:
            s = rb.memory_snapshot(ALT, "after load")
            s["run"] = 1
            mem.append(s)
    rb.container_stop()
    micro = []
    for i in range(1, 4):
        out = rb.sh(["docker", "run", "--rm", "--cpus", "2", rb.IMAGE, "venv/bin/python", "-c", CODE])
        micro.append({"alternative": LABEL, "run": i, "seconds": float(out)})
        rb.log(f"microbench run {i}: {out} s")
    rb.write_csv("control_startup.csv", startup)
    rb.write_csv("control_memory.csv", relabel(mem))
    rb.write_csv("control_throughput.csv", relabel(load))
    rb.write_csv("control_cpu_microbench.csv", micro)


if __name__ == "__main__":
    main()
