"""Small benchmark API used for the SEN421 VM vs. container experiment.

Endpoints
  GET /hello    - light, I/O-style response (tests per-request overhead)
  GET /compute  - CPU-bound work (tests raw compute under virtualization)
  GET /health   - readiness probe used to measure startup time
"""
import hashlib
import os
import platform
import socket

from flask import Flask, jsonify

app = Flask(__name__)

# Fixed amount of CPU work per /compute request (SHA-256 rounds).
COMPUTE_ROUNDS = int(os.environ.get("COMPUTE_ROUNDS", "20000"))


@app.get("/health")
def health():
    return "ok", 200


@app.get("/hello")
def hello():
    return jsonify(message="hello", host=socket.gethostname())


@app.get("/compute")
def compute():
    digest = b"sen421"
    for _ in range(COMPUTE_ROUNDS):
        digest = hashlib.sha256(digest).digest()
    return jsonify(rounds=COMPUTE_ROUNDS, digest=digest.hex()[:16])


@app.get("/info")
def info():
    return jsonify(
        host=socket.gethostname(),
        kernel=platform.release(),
        python=platform.python_version(),
        cpus=os.cpu_count(),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
