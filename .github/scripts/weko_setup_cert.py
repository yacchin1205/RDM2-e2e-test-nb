#!/usr/bin/env python3
"""Add WEKO certificate configuration to RDM docker-compose.override.yml."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


CONTAINER_CERT_PATH = "/etc/ssl/certs/weko-ca.crt"

SERVICE_CONFIG = {
    "web": {
        "command": "invoke server -h 0.0.0.0",
        "ca_bundle": "/usr/lib/python3.6/site-packages/certifi/cacert.pem",
    },
    "worker": {
        "command": "invoke celery_worker",
        "ca_bundle": "/usr/lib/python3.6/site-packages/certifi/cacert.pem",
    },
    "wb": {
        "command": "invoke server",
        "ca_bundle": "/usr/local/lib/python3.6/site-packages/certifi/cacert.pem",
    },
    "wb_worker": {
        "command": "invoke celery",
        "ca_bundle": "/usr/local/lib/python3.6/site-packages/certifi/cacert.pem",
    },
}


def add_weko_cert_config(data: dict, cert_path: Path) -> None:
    """Add volume mount and command to append WEKO cert to system CA bundle."""
    mount = f"{cert_path}:{CONTAINER_CERT_PATH}:ro"

    for service_name, config in SERVICE_CONFIG.items():
        service = data["services"][service_name]

        volumes = service.setdefault("volumes", [])
        volumes.append(mount)

        ca_bundle = config["ca_bundle"]
        orig_command = config["command"]
        service["command"] = [
            "/bin/sh",
            "-c",
            f"cat {CONTAINER_CERT_PATH} >> {ca_bundle} && {orig_command}",
        ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add WEKO certificate to RDM docker-compose.override.yml"
    )
    parser.add_argument(
        "compose_file",
        type=Path,
        help="Path to docker-compose.override.yml",
    )
    parser.add_argument(
        "cert_path",
        type=Path,
        help="Path to WEKO certificate file",
    )
    args = parser.parse_args()

    cert_abs = args.cert_path.resolve()

    with args.compose_file.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    add_weko_cert_config(data, cert_abs)

    with args.compose_file.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)

    print(f"Added WEKO certificate configuration to {args.compose_file}")


if __name__ == "__main__":
    main()
