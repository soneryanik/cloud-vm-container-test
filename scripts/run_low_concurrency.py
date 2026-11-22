"""Supplementary test: repeat the throughput test at 10 VUs.

At 50 VUs the VirtualBox NAT port-forward dropped many /hello connections.
Running at 10 VUs separates the NAT bottleneck from application/CPU limits.
Output: results/throughput_10vus.csv
"""
import time

import run_benchmarks as rb

rb.VUS = 10


def main():
    rows = []
    for alt in ("vm", "container"):
        if alt == "vm":
            rb.container_stop()
            if rb.vm_state() != "running":
                rb.measure_startup("vm", 1)
        else:
            rb.vm_stop()
            rb.container_start()
            rb.wait_http(rb.TARGETS[alt] + "/health", 60, 0.05)
        for ep in rb.ENDPOINTS:
            rb.log(f"10 VUs: {alt} {ep} (warm-up 10 s)")
            rb.run_k6(alt, ep, 0, record=False)
            for i in range(1, 4):
                row = rb.run_k6(alt, ep, f"{i}_10vus")
                row["run"], row["vus"] = i, 10
                rows.append(row)
                rb.log(f"   run {i}: {row['rps']} req/s, p95 {row['lat_p95_ms']} ms, "
                       f"errors {row['error_rate']:.3f}")
                time.sleep(10)
    rb.container_stop()
    rb.write_csv("throughput_10vus.csv", rows)


if __name__ == "__main__":
    main()
