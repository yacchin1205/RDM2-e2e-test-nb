"""Browser operations shared by the BinderHub procedure notebooks."""
import asyncio
from contextlib import suppress
import re
from urllib.parse import parse_qs, urlsplit


async def launch(page, timeout):
    """Wait for the launched window, or fail when RDM reports a build error."""
    async def popup():
        # Register the listener before clicking, including for existing images.
        async with page.expect_popup(timeout=timeout) as result:
            await page.locator('[data-test-binderhub-launch]').click()
        return await result.value

    async def failure():
        failed = page.locator('[class*="build_phase"]').filter(
            has_text=re.compile(r'^\s*failed\s*$'))
        alert = page.locator('[class*="BinderHub__connection_alert"].alert-danger:visible')
        await failed.or_(alert).first.wait_for(state='visible', timeout=timeout + 1000)
        raise AssertionError('BinderHub build failed; inspect the recorded RDM build log')

    popup_task = asyncio.create_task(popup())
    failure_task = asyncio.create_task(failure())
    try:
        done, _ = await asyncio.wait(
            (popup_task, failure_task), return_when=asyncio.FIRST_COMPLETED)
        if failure_task in done:
            await failure_task
        return await popup_task
    finally:
        for task in (popup_task, failure_task):
            if not task.done():
                task.cancel()
        for task in (popup_task, failure_task):
            with suppress(asyncio.CancelledError):
                await task


async def set_copy_default_storage(page, project_url, enabled, timeout):
    project_id = urlsplit(project_url).path.strip('/')
    prefix = '/v1/resources/' + project_id + '/providers/osfstorage/'

    def saved(response):
        url = urlsplit(response.url)
        if not url.path.startswith(prefix):
            return False
        if enabled:
            return response.request.method == 'DELETE'
        return response.request.method == 'PUT' and parse_qs(url.query).get('name') == ['paths.yaml']

    async with page.expect_response(saved, timeout=timeout) as result:
        await page.locator('[data-test-copy-default-storage]').set_checked(enabled)
    response = await result.value
    if not response.ok:
        raise AssertionError(f'paths.yaml update failed: HTTP {response.status}')
