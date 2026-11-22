"""Compare CPU features visible inside the container and the VM, and repeat
the pure-CPU microbenchmark in the VM after it has settled for 60 s.
Output: results/cpu_features.txt and extra rows in results/cpu_microbench_settled.csv
"""
import time

import run_benchmarks as rb
from run_cpu_microbench import CODE

FLAGS = "grep -m1 -o -w -E 'sha_ni|avx2|avx512f|aes' /proc/cpuinfo | sort -u | tr '\\n' ' '"
INFO = FLAGS + "; echo; python3 -c 'import ssl;print(ssl.OPENSSL_VERSION)'; grep -m1 'model name' /proc/cpuinfo"


def main():
    lines = ["== container =="]
    lines.append(rb.sh(["docker", "run", "--rm", rb.IMAGE, "sh", "-c", INFO]))
    if rb.vm_state() != "running":
        rb.measure_startup("vm", 1)
    time.sleep(60)
    lines += ["== vm ==", rb.vm_ssh(INFO)]
    rows = []
    for i in range(1, 4):
        out = rb.vm_ssh(f'python3 -c "{CODE}"')
        rows.append({"alternative": "vm", "run": i, "seconds": float(out), "note": "after 60 s settle"})
    rb.vm_stop()
    for i in range(1, 4):
        out = rb.sh(["docker", "run", "--rm", "--cpus", "2", rb.IMAGE, "python", "-c", CODE])
        rows.append({"alternative": "container", "run": i, "seconds": float(out), "note": "after 60 s settle"})
    text = "\n".join(lines)
    (rb.RESULTS / "cpu_features.txt").write_text(text + "\n")
    print(text)
    rb.write_csv("cpu_microbench_settled.csv", rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
