#!/bin/bash
set -xeuo pipefail

COMMAND=${1:-}

if [[ -z "${COMMAND}" ]]; then
  echo "Usage: $0 <install|start-logs|collect-logs|down> [output-directory]" >&2
  exit 1
fi

LOG_OUTPUT_DIR=${2:-tljh-logs}
DOCKER_EVENTS_RAW=/tmp/tljh-repo2docker-events.jsonl

redact_log() {
  sed -E \
    -e 's/(repo_token=)[^&"[:space:]]+/\1[redacted]/g' \
    -e 's/(repo_token%3D)[^%&"[:space:]]+/\1[redacted]/g' \
    -e 's/(GIT_CREDENTIAL_ENV=)[^"[:space:]]+/\1[redacted]/g'
}

write_docker_identity() {
  local output_file="$1"

  {
    date -u +%Y-%m-%dT%H:%M:%SZ
    echo "DOCKER_HOST=${DOCKER_HOST:-}"
    echo "DOCKER_CONTEXT=${DOCKER_CONTEXT:-}"
    sudo docker context show
    sudo docker info --format 'ID={{.ID}} Name={{.Name}} ServerVersion={{.ServerVersion}} Driver={{.Driver}} DockerRootDir={{.DockerRootDir}}'
    sudo stat /var/run/docker.sock
  } > "${output_file}" 2>&1 || true
}

wait_for_url() {
  local url="$1"
  local attempts=30
  local delay=10
  for ((i=1; i<=attempts; i++)); do
    if curl -k --fail "$url"; then
      echo "${url} is reachable"
      return 0
    fi
    echo "Attempt ${i}/${attempts} failed for ${url}" >&2
    sleep "$delay"
  done
  echo "Timed out waiting for ${url}" >&2
  return 1
}

case "$COMMAND" in
  install)
    # Install Node.js
    sudo apt-get update
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    sudo chmod a+r /etc/apt/keyrings/nodesource.gpg

    NODE_MAJOR=21
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | \
      sudo tee /etc/apt/sources.list.d/nodesource.list
    sudo apt-get update
    sudo apt-get install -y nodejs
    sudo npm install -g yarn

    sudo modprobe fuse

    # Pull the repo2docker image
    sudo docker pull "${REPO2DOCKER_IMAGE}"
    sudo docker pull "${RDMFS_IMAGE}"

    # Install TLJH
    curl -L https://tljh.jupyter.org/bootstrap.py \
      | sudo python3 - \
        --version "${TLJH_VERSION}" \
        --admin admin:change-your-password \
        --plugin "git+https://github.com/${TLJH_PLUGIN%%@*}.git@${TLJH_PLUGIN#*@}"

    # Workaround: upgrade to the latest version of jupyterhub
    sudo /opt/tljh/hub/bin/pip install --upgrade jupyterhub\<5

    # Configure the plugin
    cat <<'EOF' | sudo tee /opt/tljh/config/jupyterhub_config.d/repo2docker.py
from tljh_repo2docker import TLJH_R2D_ADMIN_SCOPE
import sys


c.JupyterHub.allow_named_servers = True

c.JupyterHub.services.extend(
    [
        {
            "name": "tljh_repo2docker",
            "url": "http://127.0.0.1:6789",
            "command": [
                "env",
                'REPO2DOCKER_RDM_PROVIDER_HOSTS=[{"hostname":["http://192.168.168.167:5000"],"api":"http://192.168.168.167:8000/v2/"}]',
                sys.executable,
                "-m",
                "tljh_repo2docker",
                "--ip",
                "127.0.0.1",
                "--port",
                "6789"
            ],
            "oauth_no_confirm": True,
            "oauth_client_allowed_scopes": [
                TLJH_R2D_ADMIN_SCOPE,
            ],
        }
    ]
)

c.JupyterHub.custom_scopes = {
    TLJH_R2D_ADMIN_SCOPE: {
        "description": "Admin access to tljh_repo2docker",
    },
}

c.JupyterHub.load_roles = [
    {
        "description": "Role for tljh_repo2docker service",
        "name": "tljh-repo2docker-service",
        "scopes": [
            "read:users",
            "read:roles:users",
            "admin:servers",
            "access:services!service=binder",
        ],
        "services": ["tljh_repo2docker"],
    },
    {
        "name": "user",
        "scopes": [
            "self",
            "access:services!service=tljh_repo2docker",
        ],
    },
    {
        "name": 'tljh-repo2docker-service-admin',
        "groups": ["repo2docker"],
        "scopes": [TLJH_R2D_ADMIN_SCOPE],
    },
]

c.JupyterHub.tornado_settings = {
    "slow_spawn_timeout": 30
}
EOF

    sudo systemctl restart jupyterhub
    wait_for_url "http://localhost"
    ;;
  start-logs)
    mkdir -p "${LOG_OUTPUT_DIR}"
    date -u +%Y-%m-%dT%H:%M:%SZ > "${LOG_OUTPUT_DIR}/docker-events-started-at.txt"
    write_docker_identity "${LOG_OUTPUT_DIR}/docker-daemon-start.txt"

    # Keep the raw event stream outside the artifact directory because Docker
    # event attributes may contain the dynamically issued RDM repository token.
    nohup sudo docker events \
      --since "$(cat "${LOG_OUTPUT_DIR}/docker-events-started-at.txt")" \
      --filter type=container \
      --filter label=repo2docker.build \
      --format '{{json .}}' \
      > "${DOCKER_EVENTS_RAW}" 2>&1 &
    event_pid=$!
    echo "${event_pid}" > "${LOG_OUTPUT_DIR}/docker-events.pid"

    sleep 1
    if ! kill -0 "${event_pid}" 2>/dev/null; then
      echo "Docker event collector exited during startup" >&2
      redact_log < "${DOCKER_EVENTS_RAW}" >&2 || true
      exit 1
    fi
    ;;
  collect-logs)
    mkdir -p "${LOG_OUTPUT_DIR}/build-containers"
    date -u +%Y-%m-%dT%H:%M:%SZ > "${LOG_OUTPUT_DIR}/collected-at.txt"
    write_docker_identity "${LOG_OUTPUT_DIR}/docker-daemon-end.txt"

    raw_jupyterhub_log=/tmp/tljh-jupyterhub.log
    sudo journalctl -u jupyterhub > "${raw_jupyterhub_log}" 2>&1 || true
    redact_log < "${raw_jupyterhub_log}" \
      > "${LOG_OUTPUT_DIR}/jupyterhub.log" || true
    rm -f "${raw_jupyterhub_log}"

    raw_docker_log=/tmp/tljh-docker-daemon.log
    sudo journalctl -u docker \
      --since "$(cat "${LOG_OUTPUT_DIR}/docker-events-started-at.txt")" \
      > "${raw_docker_log}" 2>&1 || true
    redact_log < "${raw_docker_log}" \
      > "${LOG_OUTPUT_DIR}/docker-daemon.log" || true
    rm -f "${raw_docker_log}"

    {
      event_pid=$(cat "${LOG_OUTPUT_DIR}/docker-events.pid" 2>/dev/null || true)
      echo "PID=${event_pid}"
      if [[ "${event_pid}" =~ ^[0-9]+$ ]] && sudo kill -0 "${event_pid}" 2>/dev/null; then
        echo "STATUS=running"
        sudo ps -p "${event_pid}" -o pid=,ppid=,etime=,args=
      else
        echo "STATUS=not-running"
      fi
    } > "${LOG_OUTPUT_DIR}/docker-events-collector.txt" 2>&1 || true

    {
      printf 'ID\tIMAGE\tSTATUS\tNAME\n'
      sudo docker ps -a --no-trunc \
        --format '{{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}'
    } > "${LOG_OUTPUT_DIR}/all-containers.tsv" 2>&1 || true

    {
      printf 'ID\tIMAGE\tSTATUS\tNAME\tBUILD_IMAGE\tREF\n'
      sudo docker ps -a --no-trunc \
        --filter label=repo2docker.build \
        --format '{{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}\t{{.Label "repo2docker.build"}}\t{{.Label "repo2docker.ref"}}'
    } > "${LOG_OUTPUT_DIR}/build-containers.tsv" 2>&1 || true

    sudo docker ps -aq --no-trunc \
      --filter label=repo2docker.build \
      > "${LOG_OUTPUT_DIR}/build-container-ids.txt" 2>/dev/null || true

    while IFS= read -r container_id; do
      if [[ -z "${container_id}" ]]; then
        continue
      fi
      short_id=${container_id:0:12}
      sudo docker inspect --format '{{json .State}}' "${container_id}" \
        > "${LOG_OUTPUT_DIR}/build-containers/${short_id}.state.json" 2>&1 || true
      sudo docker inspect --format $'ID={{.Id}}\nName={{.Name}}\nImage={{.Config.Image}}\nBuildImage={{index .Config.Labels "repo2docker.build"}}\nRef={{index .Config.Labels "repo2docker.ref"}}' "${container_id}" \
        > "${LOG_OUTPUT_DIR}/build-containers/${short_id}.metadata.txt" 2>&1 || true

      raw_container_log="/tmp/tljh-repo2docker-${short_id}.log"
      sudo docker logs --timestamps "${container_id}" \
        > "${raw_container_log}" 2>&1 || true
      redact_log < "${raw_container_log}" \
        > "${LOG_OUTPUT_DIR}/build-containers/${short_id}.log" || true
      rm -f "${raw_container_log}"
    done < "${LOG_OUTPUT_DIR}/build-container-ids.txt"

    {
      printf 'ID\tREPOSITORY\tTAG\tSIZE\tCREATED_AT\n'
      sudo docker image ls --no-trunc \
        --filter label=repo2docker.ref \
        --format '{{.ID}}\t{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}'
    } > "${LOG_OUTPUT_DIR}/built-images.tsv" 2>&1 || true

    if [[ -f "${DOCKER_EVENTS_RAW}" ]]; then
      redact_log < "${DOCKER_EVENTS_RAW}" \
        > "${LOG_OUTPUT_DIR}/docker-events.jsonl" || true
    else
      echo "Docker event stream was not found: ${DOCKER_EVENTS_RAW}" \
        > "${LOG_OUTPUT_DIR}/docker-events.jsonl"
    fi
    ;;
  down)
    sudo systemctl stop jupyterhub || true
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    exit 1
    ;;
esac
