# shellcheck shell=bash

wait_for_service() {
    local service_name="${SERVICE_NAME}"
    local check_command="${CHECK_COMMAND}"
    local timeout="${TIMEOUT:-300}"
    local interval="${INTERVAL:-10}"

    echo "Waiting for $service_name to be ready (timeout: ${timeout}s)..."
    local elapsed=0

    while [ $elapsed -lt $timeout ]; do
        if eval "$check_command" > /dev/null 2>&1; then
            echo "$service_name is ready!"
            return 0
        fi
        echo "Waiting for $service_name... (${elapsed}s elapsed)"
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    echo "Timeout waiting for $service_name"
    return 1
}
