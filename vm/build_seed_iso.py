"""Build the cloud-init NoCloud seed ISO (volume label 'cidata').

Usage: python build_seed_iso.py <ssh_pubkey_file> <output_iso>
Requires: pip install pycdlib
"""
import base64
import io
import pathlib
import sys

import pycdlib

HERE = pathlib.Path(__file__).resolve().parent
APP = HERE.parent / "app"


def b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def main(pubkey_file: str, out_iso: str) -> None:
    pubkey = pathlib.Path(pubkey_file).read_text().strip()
    user_data = (HERE / "user-data.template.yaml").read_text()
    user_data = (
        user_data.replace("__SSH_PUBKEY__", pubkey)
        .replace("__APP_PY_B64__", b64(APP / "app.py"))
        .replace("__REQ_B64__", b64(APP / "requirements.txt"))
    )
    meta_data = "instance-id: sen421-vm-001\nlocal-hostname: sen421-vm\n"

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident="cidata")
    for name, text in (("user-data", user_data), ("meta-data", meta_data)):
        data = text.encode()
        iso.add_fp(
            io.BytesIO(data), len(data), f"/{name.upper().replace('-', '')}.;1",
            rr_name=name, joliet_path=f"/{name}",
        )
    iso.write(out_iso)
    iso.close()
    print(f"seed ISO written: {out_iso}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
