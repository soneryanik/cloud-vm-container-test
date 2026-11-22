"""Supplementary test: pure CPU work without HTTP or networking.

Times 200,000 SHA-256 rounds in a single Python process, 3 runs inside the
container and 3 runs inside the VM. Isolates CPU virtualization overhead
from the network path. Output: results/cpu_microbench.csv
"""
import run_benchmarks as rb

CODE = ("import hashlib,time;d=b's';t=time.perf_counter();"
        "[d:=hashlib.sha256(d).digest() for _ in range(200000)];"
        "print(round(time.perf_counter()-t,4))")


def main():
    rows = []
    rb.vm_stop()
    for i in range(1, 4):
        out = rb.sh(["docker", "run", "--rm", "--cpus", "2", "--memory", "2g",
                     rb.IMAGE, "python", "-c", CODE])
        rows.append({"alternative": "container", "run": i, "seconds": float(out)})
        rb.log(f"container run {i}: {out} s")
    rb.measure_startup("vm", 1)
    for i in range(1, 4):
        out = rb.vm_ssh(f'python3 -c "{CODE}"')
        rows.append({"alternative": "vm", "run": i, "seconds": float(out)})
        rb.log(f"vm run {i}: {out} s")
    rb.vm_stop()
    rb.write_csv("cpu_microbench.csv", rows)


if __name__ == "__main__":
    main()
