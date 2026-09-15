#!/bin/bash
set -xeuo pipefail

# Usage:
#   ./setup_rustfs_buckets.sh <rdm_root_dir> <alias> <endpoint> <root_user> <root_password> \
#     <access_key_1> <secret_key_1> <bucket_name_1> <access_key_2> <secret_key_2> <bucket_name_2>

if [[ $# -ne 11 ]]; then
  cat >&2 <<'EOF'
Usage: setup_rustfs_buckets.sh <rdm_root_dir> <alias> <endpoint> <root_user> <root_password> \
  <access_key_1> <secret_key_1> <bucket_name_1> <access_key_2> <secret_key_2> <bucket_name_2>
EOF
  exit 1
fi

RDM_ROOT=$1
ALIAS=$2
ENDPOINT=$3
ROOT_USER=$4
ROOT_PASSWORD=$5
ACCESS_KEY_1=$6
SECRET_KEY_1=$7
BUCKET_NAME_1=$8
ACCESS_KEY_2=$9
SECRET_KEY_2=${10}
BUCKET_NAME_2=${11}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUSTFS_VERIFY_LARGE_UPLOAD=${RUSTFS_VERIFY_LARGE_UPLOAD:-false}
RUSTFS_VERIFY_LARGE_UPLOAD_SIZE_MB=${RUSTFS_VERIFY_LARGE_UPLOAD_SIZE_MB:-130}
RUSTFS_VERIFY_LARGE_UPLOAD_KEY=${RUSTFS_VERIFY_LARGE_UPLOAD_KEY:-diagnostics/rustfs-large-upload.bin}

if [[ ! -d "${RDM_ROOT}" ]]; then
  echo "RDM root directory not found: ${RDM_ROOT}" >&2
  exit 1
fi

pushd "${RDM_ROOT}" >/dev/null
source "${SCRIPT_DIR}/lib/wait_for_service.sh"

SERVICE_NAME="RustFS"
CHECK_COMMAND="docker-compose exec -T rustfs /bin/sh -c 'curl -fs http://localhost:9000/health/ready'"
TIMEOUT=180
INTERVAL=5
wait_for_service

docker-compose run --rm --entrypoint /bin/sh rustfs-rc <<EOF
set -xeu
rc alias set "${ALIAS}" "${ENDPOINT}" "${ROOT_USER}" "${ROOT_PASSWORD}"
rc bucket remove --force "${ALIAS}/${BUCKET_NAME_1}" || true
rc bucket remove --force "${ALIAS}/${BUCKET_NAME_2}" || true
rc bucket create "${ALIAS}/${BUCKET_NAME_1}"
rc bucket create "${ALIAS}/${BUCKET_NAME_2}"
rc admin user rm "${ALIAS}" "${ACCESS_KEY_1}" || true
rc admin user rm "${ALIAS}" "${ACCESS_KEY_2}" || true
rc admin user add "${ALIAS}" "${ACCESS_KEY_1}" "${SECRET_KEY_1}"
rc admin policy attach "${ALIAS}" readwrite --user "${ACCESS_KEY_1}"
rc admin user add "${ALIAS}" "${ACCESS_KEY_2}" "${SECRET_KEY_2}"
rc admin policy attach "${ALIAS}" readwrite --user "${ACCESS_KEY_2}"

if [ "${RUSTFS_VERIFY_LARGE_UPLOAD}" = "true" ]; then
  echo "[diagnostic] Uploading ${RUSTFS_VERIFY_LARGE_UPLOAD_SIZE_MB}MiB test object to ${ALIAS}/${BUCKET_NAME_1}/${RUSTFS_VERIFY_LARGE_UPLOAD_KEY}" >&2
  dd if=/dev/zero of=/tmp/rustfs-large-upload-test.bin bs=1M count=${RUSTFS_VERIFY_LARGE_UPLOAD_SIZE_MB}
  rc object copy /tmp/rustfs-large-upload-test.bin "${ALIAS}/${BUCKET_NAME_1}/${RUSTFS_VERIFY_LARGE_UPLOAD_KEY}"
  rc object stat "${ALIAS}/${BUCKET_NAME_1}/${RUSTFS_VERIFY_LARGE_UPLOAD_KEY}"
  rm -f /tmp/rustfs-large-upload-test.bin
fi
EOF

popd >/dev/null

echo "RustFS buckets and users have been initialized"
