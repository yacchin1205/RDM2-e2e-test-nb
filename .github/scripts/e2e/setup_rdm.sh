#!/bin/bash
set -xe

# RDM setup utility functions
# Note: These functions expect to be called from the appropriate working directory

# Function to start RDM services
start_rdm_services() {
    local include_admin="${INCLUDE_ADMIN:-false}"
    
    # Define services based on admin flag
    if [ "$include_admin" = "true" ]; then
        export SERVICES="mfr wb fakecas sharejs wb_worker worker web api ember_osf_web assets admin_assets admin"
    else
        export SERVICES="mfr wb fakecas sharejs wb_worker worker web api ember_osf_web assets"
    fi
    
    echo "Starting services: $SERVICES"
    
    # Source docker utilities and use start_services function
    source $(dirname "$0")/docker_utils.sh
    start_services
    
    # Wait for ember build to complete
    echo "Waiting for Ember build to complete..."
    local timeout="${TIMEOUT:-600}"  # Default 10 minutes
    SERVICE="ember_osf_web" PATTERN="Build successful.*Serving on http://0.0.0.0:4200/" TIMEOUT="$timeout" check_service_logs
}

# Function to test RDM endpoints
test_rdm_endpoints() {
    local include_admin="${INCLUDE_ADMIN:-false}"
    
    # Source docker utilities for test_endpoint function
    source $(dirname "$0")/docker_utils.sh
    
    # Test main endpoints
    ENDPOINT_NAME="OSF Web (port 5000)" ENDPOINT_URL="http://localhost:5000/" test_endpoint
    ENDPOINT_NAME="OSF API (port 8000)" ENDPOINT_URL="http://localhost:8000/v2/" test_endpoint
    ENDPOINT_NAME="Ember OSF Web (port 4200)" ENDPOINT_URL="http://localhost:4200/" test_endpoint
    ENDPOINT_NAME="WaterButler (port 7777)" ENDPOINT_URL="http://localhost:7777/status" test_endpoint
    ENDPOINT_NAME="MFR (port 7778)" ENDPOINT_URL="http://localhost:7778/status" test_endpoint
    ENDPOINT_NAME="FakeCAS (port 8080)" ENDPOINT_URL="http://localhost:8080/login" test_endpoint
    
    # Test admin endpoint if admin is enabled
    if [ "$include_admin" = "true" ]; then
        ENDPOINT_NAME="Admin Web (port 8001)" ENDPOINT_URL="http://localhost:8001/" test_endpoint
    fi
}

# Function to copy configuration files
setup_config_files() {
    local include_admin="${INCLUDE_ADMIN:-false}"  # Use environment variable or default
    
    echo "Setting up configuration files..."
    
    # Copy base configuration files
    cp ./website/settings/local-dist.py ./website/settings/local.py
    cp ./api/base/settings/local-dist.py ./api/base/settings/local.py
    cp ./docker-compose-dist.override.yml ./docker-compose.override.yml
    cp ./tasks/local-dist.py ./tasks/local.py
    
    # Create admin settings if requested
    if [ "$include_admin" = "true" ]; then
        cp ./admin/base/settings/local-dist.py ./admin/base/settings/local.py
        echo "ALLOWED_HOSTS = ['localhost']" >> ./admin/base/settings/local.py
        echo "Admin configuration files created"
    fi
    
    echo "Configuration files setup completed"
}

# Function to create docker-compose override with NII Cloud Operation images
create_docker_override() {
    # Use environment variables for images
    local osf_image="${OSF_IMAGE:-niicloudoperation/rdm-osf.io:latest}"
    local ember_image="${EMBER_IMAGE:-niicloudoperation/rdm-ember-osf-web:latest}"
    local cas_image="${CAS_IMAGE:-niicloudoperation/rdm-cas-overlay:latest}"
    local mfr_image="${MFR_IMAGE:-niicloudoperation/rdm-modular-file-renderer:latest}"
    local wb_image="${WB_IMAGE:-niicloudoperation/rdm-waterbutler:latest}"
    
    echo "Creating docker-compose override with:"
    echo "  OSF: $osf_image"
    echo "  Ember: $ember_image"
    echo "  CAS: $cas_image"
    echo "  MFR: $mfr_image"
    echo "  WaterButler: $wb_image"
    
    cat > docker-compose.override.yml << EOL
# NII Cloud Operation images override
services:
  fakecas:
    image: niicloudoperation/rdm-fakecas:latest
  admin:
    image: ${osf_image}
    environment:
      AWS_EC2_METADATA_DISABLED: "true"
  admin_assets:
    image: ${osf_image}
  api:
    image: ${osf_image}
  assets:
    image: ${osf_image}
  requirements:
    image: ${osf_image}
    command:
      - /bin/bash
      - -c
      - apk add --no-cache --virtual .build-deps build-base linux-headers python3-dev musl-dev libxml2-dev libxslt-dev postgresql-dev libffi-dev libpng-dev freetype-dev jpeg-dev &&
        invoke requirements --all &&
        (python3 -m compileall /usr/lib/python3.6 || true) &&
        rm -Rf /python3.6/* &&
        cp -Rf -p /usr/lib/python3.6 /
  web:
    image: ${osf_image}
    environment:
      OAUTHLIB_INSECURE_TRANSPORT: '1'
  worker:
    image: ${osf_image}
  ember_osf_web:
    image: ${ember_image}
  cas:
    image: ${cas_image}
  mfr:
    image: ${mfr_image}
  mfr_requirements:
    image: ${mfr_image}
  wb:
    image: ${wb_image}
  wb_worker:
    image: ${wb_image}
  wb_requirements:
    image: ${wb_image}
EOL
    
    echo "Docker compose override created"
}

# Function to run Django migrations
run_migrations() {
    echo "Running Django migrations..."
    docker-compose run --rm web python3 manage.py migrate
    echo "Migrations completed"
}

# Function to enable feature flags
enable_feature_flags() {
    local flags="${FEATURE_FLAGS:-}"  # Use environment variable
    
    if [ -z "$flags" ]; then
        echo "No feature flags to enable"
        return 0
    fi
    
    for flag in $flags; do
        echo "Enabling feature flag: $flag"
        docker-compose run --rm web python3 manage.py waffle_flag "$flag" --everyone
    done
    
    echo "Feature flags enabled"
}

# Function to compile translations
compile_translations() {
    local include_admin="${INCLUDE_ADMIN:-false}"
    
    echo "Compiling translation files..."
    docker-compose run --rm web pybabel compile -d ./website/translations
    
    if [ "$include_admin" = "true" ]; then
        echo "Compiling admin translation files..."
        docker-compose run --rm web pybabel compile -D django -d ./admin/translations
    fi
    
    echo "Translation compilation completed"
}

# Function to install requirements
install_requirements() {
    echo "Installing requirements..."
    docker-compose run --rm requirements
    docker-compose run --rm mfr_requirements
    docker-compose run --rm wb_requirements
    echo "Requirements installation completed"
}

# Main execution if called directly with arguments
if [ $# -gt 0 ]; then
    command="$1"
    shift
    
    case "$command" in
        setup_config_files)
            setup_config_files "$@"
            ;;
        create_docker_override)
            create_docker_override "$@"
            ;;
        install_requirements)
            install_requirements "$@"
            ;;
        run_migrations)
            run_migrations "$@"
            ;;
        enable_feature_flags)
            enable_feature_flags "$@"
            ;;
        compile_translations)
            compile_translations "$@"
            ;;
        start_rdm_services)
            start_rdm_services "$@"
            ;;
        test_rdm_endpoints)
            test_rdm_endpoints "$@"
            ;;
        *)
            echo "Unknown command: $command"
            exit 1
            ;;
    esac
fi