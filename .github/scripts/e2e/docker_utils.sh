#!/bin/bash
set -xe

# Docker utility functions for e2e tests
# Note: These functions expect to be called from the appropriate working directory

# Function to wait for a service to be ready
wait_for_service() {
    local service_name="${SERVICE_NAME}"
    local check_command="${CHECK_COMMAND}"
    local timeout="${TIMEOUT:-300}"  # Default 5 minutes
    local interval="${INTERVAL:-10}"   # Default 10 seconds
    
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

# Function to start docker services with health check
start_services() {
    local services="${SERVICES}"
    
    echo "Starting services: $services"
    docker-compose up -d $services
    
    # Basic wait for containers to initialize
    sleep 20
    
    # Show status
    docker-compose ps
}

# Function to check service logs for specific pattern
check_service_logs() {
    local service="${SERVICE}"
    local pattern="${PATTERN}"
    local timeout="${TIMEOUT:-600}"  # Default 10 minutes
    
    echo "Checking $service logs for pattern: $pattern"
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker-compose logs "$service" 2>&1 | grep -q "$pattern"; then
            echo "$service: Pattern found!"
            return 0
        fi
        sleep 10
        elapsed=$((elapsed + 10))
    done
    
    echo "$service: Pattern not found within timeout"
    return 1
}

# Function to test HTTP endpoint
test_endpoint() {
    local name="${ENDPOINT_NAME}"
    local url="${ENDPOINT_URL}"
    local expected_codes="${EXPECTED_CODES:-200,302}"  # Default acceptable codes
    
    echo "Testing $name..."
    local response=$(curl -s -o /dev/null -w "%{http_code}" --retry 5 --retry-delay 10 --retry-connrefused "$url" || echo "000")
    echo "$name response code: $response"
    
    # Check for errors
    if [[ "$response" == "400" || "$response" == "500" ]]; then
        echo "$name returned HTTP $response - failing" >&2
        return 1
    elif [[ "$response" == "000" ]]; then
        echo "$name connection failed - failing" >&2
        return 1
    fi
    
    # Check if response is in expected codes
    if echo "$expected_codes" | grep -q "$response"; then
        echo "$name is accessible"
        return 0
    else
        echo "$name not accessible (HTTP $response)" >&2
        return 2  # Non-fatal error
    fi
}

# Main execution if called directly with arguments
if [ $# -gt 0 ]; then
    command="$1"
    shift
    
    case "$command" in
        wait_for_service)
            wait_for_service
            ;;
        start_services)
            start_services
            ;;
        check_service_logs)
            check_service_logs
            ;;
        test_endpoint)
            test_endpoint
            ;;
        *)
            echo "Unknown command: $command"
            exit 1
            ;;
    esac
fi