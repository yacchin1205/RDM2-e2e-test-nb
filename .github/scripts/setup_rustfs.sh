#!/bin/bash
set -xeuo pipefail

# Usage:
#   ./setup_rustfs.sh apply <rdm_root_dir>
#
# Generates docker-compose override entries and s3compat settings
# required for RustFS usage within the E2E environment.

COMMAND=${1:-}
RDM_ROOT=${2:-}

if [[ -z "${COMMAND}" || -z "${RDM_ROOT}" ]]; then
  echo "Usage: $0 apply <rdm_root_dir>" >&2
  exit 1
fi

case "${COMMAND}" in
  apply)
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    exit 1
    ;;
esac

if [[ ! -d "${RDM_ROOT}" ]]; then
  echo "RDM root directory not found: ${RDM_ROOT}" >&2
  exit 1
fi

RUSTFS_IMAGE_DEFAULT=${RUSTFS_IMAGE:-rustfs/rustfs:latest}
RUSTFS_RC_IMAGE_DEFAULT=${RUSTFS_RC_IMAGE:-rustfs/rc:latest}

RUSTFS_DOCKER_SNIPPET=$(cat <<YAML
  rustfs:
    image: ${RUSTFS_IMAGE_DEFAULT}
    environment:
      RUSTFS_ACCESS_KEY: ${RUSTFS_ACCESS_KEY:-rustfsadmin}
      RUSTFS_SECRET_KEY: ${RUSTFS_SECRET_KEY:-rustfsadmin}
      RUSTFS_OBS_LOG_STDOUT_ENABLED: "true"
      RUSTFS_OBS_LOGGER_LEVEL: info
    expose:
      - "9000"

  rustfs-rc:
    image: ${RUSTFS_RC_IMAGE_DEFAULT}
    entrypoint: ["rc"]
    depends_on:
      - rustfs
YAML
)

compose_override="${RDM_ROOT}/docker-compose.override.yml"

if ! grep -q '^services:' "${compose_override}"; then
  echo "services:" > "${compose_override}"
fi

if ! grep -q '^  rustfs:' "${compose_override}"; then
  printf '\n%s\n' "${RUSTFS_DOCKER_SNIPPET}" >> "${compose_override}"
fi

settings_json="${RDM_ROOT}/addons/s3compat/static/settings.json"

if [[ ! -f "${settings_json}" ]]; then
  echo "s3compat settings.json not found: ${settings_json}" >&2
  exit 1
fi

tmp_json=$(mktemp)

python - "$settings_json" "$tmp_json" <<'PY'
import json
import sys

src, dst = sys.argv[1:3]
with open(src) as f:
    data = json.load(f)

service_name = "RustFS (CI)"
host = "rustfs:9000"

available_services = data.setdefault("availableServices", [])

if not any(s.get("name") == service_name for s in available_services):
    available_services.append({
        "name": service_name,
        "host": host,
        "bucketLocations": {
            "us-east-1": {
                "name": "us-east-1",
                "host": host,
            },
            "": {
                "name": "us-east-1",
            },
        },
        "serverSideEncryption": False,
    })

with open(dst, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
    f.write("\n")
PY

mv "${tmp_json}" "${settings_json}"

# Also register RustFS service for s3compatsigv4 addon if available
sigv4_settings_json="${RDM_ROOT}/addons/s3compatsigv4/static/settings.json"

if [[ -f "${sigv4_settings_json}" ]]; then
  tmp_json_sigv4=$(mktemp)

  python - "$sigv4_settings_json" "$tmp_json_sigv4" <<'PY'
import json
import sys

src, dst = sys.argv[1:3]
with open(src) as f:
    data = json.load(f)

service_name = "RustFS (CI)"
host = "rustfs:9000"

available_services = data.setdefault("availableServices", [])

if not any(s.get("name") == service_name for s in available_services):
    available_services.append({
        "name": service_name,
        "host": host,
        "bucketLocations": {
            "us-east-1": {
                "name": "us-east-1",
                "host": host,
            },
            "": {
                "name": "us-east-1",
            },
        },
        "serverSideEncryption": False,
    })

with open(dst, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
    f.write("\n")
PY

  mv "${tmp_json_sigv4}" "${sigv4_settings_json}"
  echo "RustFS configuration applied for s3compatsigv4"
else
  echo "WARNING: s3compatsigv4 settings.json not found: ${sigv4_settings_json} (skipping)"
fi

echo "RustFS configuration applied"
