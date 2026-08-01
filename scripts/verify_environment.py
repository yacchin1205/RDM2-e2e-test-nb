import os
import time
from datetime import datetime, timezone

import requests


ENDPOINTS = (
    ('RDM Web', 'RDM_WEB_URL'),
    ('RDM API', 'RDM_API_URL'),
    ('RDM Admin', 'RDM_ADMIN_URL'),
)


def verify_environment(timeout=10):
    print(f'Environment verification at {datetime.now(timezone.utc).isoformat()}')
    for name, environment_variable in ENDPOINTS:
        url = os.environ.get(environment_variable)
        if url is None:
            print(f'{name}: SKIPPED ({environment_variable} is not set)')
            continue

        started_at = time.monotonic()
        try:
            response = requests.get(url, allow_redirects=False, timeout=timeout)
        except requests.RequestException as error:
            elapsed = time.monotonic() - started_at
            print(
                f'{name}: ERROR after {elapsed:.3f}s '
                f'({environment_variable}={url}): {error}'
            )
            continue

        elapsed = time.monotonic() - started_at
        print(
            f'{name}: HTTP {response.status_code} in {elapsed:.3f}s '
            f'({environment_variable}={url})'
        )
