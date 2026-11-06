import time
from playwright.async_api import expect
from scripts import grdm

async def login(page, username, password, transition_timeout=30000):
    # Login to JupyterHub
    jupyterhub_signin_button = page.locator('//*[@id = "login_submit"]')
    await expect(jupyterhub_signin_button).to_be_visible(timeout=transition_timeout)
    await page.locator('//*[@id = "username_input"]').fill(username)
    await page.locator('//*[@id = "password_input"]').fill(password)
    await jupyterhub_signin_button.click()

async def authorize(page, transition_timeout=30000):
    # JupyterHub authorizes a service (e.g. BinderHub addon of RDM OSF Integration)
    authorize_button = page.get_by_role('button', name='Authorize', exact=True)
    await expect(authorize_button).to_be_visible(timeout=transition_timeout)
    await authorize_button.click()


async def complete_authentication(page, ready, mode, username, password,
                                  idp_name, idp_username, idp_password,
                                  transition_timeout=30000, require_hub_user=False):
    """Handle login, consent-only, or already-authorized transitions."""
    if mode not in ('auto', 'sso', 'jupyterhub'):
        raise ValueError('Invalid binderhub_auth_mode')
    deadline = time.monotonic() + transition_timeout / 1000
    login_button = page.locator('#login_submit')
    consent = page.get_by_role('button', name='Authorize', exact=True)
    discovery = page.locator('#dropdown_img')
    hub_user = page.locator('[data-test-jupyterhub-user]')
    while time.monotonic() < deadline:
        if await ready.is_visible():
            if not require_hub_user:
                return
            # RDM renders the editor before its asynchronous OAuth redirect.
            # A populated Hub identity proves that both OAuth callbacks completed.
            if await hub_user.is_visible() and (await hub_user.inner_text()).strip() == username:
                return
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        if await login_button.is_visible():
            if mode == 'sso':
                raise AssertionError('SSO mode: unexpected JupyterHub login form')
            await login(page, username, password, remaining)
        elif await consent.is_visible():
            await authorize(page, remaining)
        elif await discovery.is_visible():
            if mode == 'jupyterhub':
                raise AssertionError('JupyterHub mode: unexpected SSO Discovery Service')
            await grdm.login(page, idp_name, idp_username, idp_password,
                             transition_timeout=remaining)
        else:
            await page.wait_for_timeout(min(100, remaining))
    if require_hub_user:
        await expect(hub_user).to_have_text(username, timeout=1)
    await expect(ready).to_be_visible(timeout=1)
