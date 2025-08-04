# APIアクセスのためのユーティリティ関数群
import asyncio
import re
from urllib.parse import urlparse

async def execute_rdmclient(rdm_api_url_v2, rdm_token, project_url, args):
    project_id = urlparse(project_url).path.lstrip('/').split('/')[0]
    assert re.match(r'^[0-9a-z]+$', project_id), project_id

    osf_command = f'osf --base-url {rdm_api_url_v2} -p {project_id} {args}'
    proc = await asyncio.create_subprocess_shell(
        f'bash -c "time env OSF_TOKEN={rdm_token} {osf_command}"',
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    print(f'[実行] {osf_command}')
    if stdout:
        print(f'[標準出力]\n{stdout.decode()}')
    if stderr:
        print(f'[標準エラー出力]\n{stderr.decode()}')
    if proc.returncode != 0:
        raise Exception(f'rdmclientの実行に失敗しました。 exitcode={proc.returncode}')
    return stdout, stderr
