"""Shared assertions for the file-preview procedure notebook."""

from playwright.async_api import expect

from scripts import grdm


FRAME = 'iframe[src*="/render"]'


def viewer(page):
    return page.frame_locator(FRAME)


async def open_file(page, filename, timeout):
    await grdm.get_select_file_title_locator(page, filename).click()
    await expect(page.locator(FRAME)).to_be_visible(timeout=timeout)


async def file_list(page, storage_name, timeout):
    await page.locator('#projectNavFiles a').click()
    await expect(page.locator(FRAME)).to_have_count(0, timeout=timeout)
    await expect(grdm.get_select_expanded_storage_title_locator(
        page, storage_name
    )).to_be_visible(timeout=timeout)


async def expect_image(page, timeout):
    image = viewer(page).locator('#base-image')
    await expect(image).to_be_visible(timeout=timeout)
    await expect(image).to_have_js_property('complete', True, timeout=timeout)
    await expect(image).to_have_js_property('naturalWidth', 640, timeout=timeout)
    await expect(image).to_have_js_property('naturalHeight', 480, timeout=timeout)


async def expect_pdf_page(page, number, text, timeout):
    frame = viewer(page)
    await expect(frame.locator('#viewer .page')).to_have_count(2, timeout=timeout)
    await expect(frame.locator('#pageNumber')).to_have_value(str(number), timeout=timeout)
    pdf_page = frame.locator(f'#pageContainer{number}')
    await expect(pdf_page.locator('.textLayer')).to_contain_text(text, timeout=timeout)
    await expect(pdf_page.locator('canvas')).to_be_visible(timeout=timeout)


async def expect_table(page, rows, timeout):
    frame = viewer(page)
    await expect(frame.locator('.slick-header-column')).to_have_text(
        ['名称', '数量', '日付'], timeout=timeout
    )
    grid_rows = frame.locator('#mfrGrid .slick-row')
    await expect(grid_rows).to_have_count(len(rows), timeout=timeout)
    for index, cells in enumerate(rows):
        await expect(grid_rows.nth(index).locator('.slick-cell')).to_have_text(
            cells, timeout=timeout
        )


async def wait_video(page, condition, timeout):
    video = await viewer(page).locator('video').element_handle(timeout=timeout)
    frame = await video.owner_frame()
    await frame.wait_for_function(condition, arg=video, timeout=timeout)


async def observe_pdf_print(page):
    sandbox = await page.locator(FRAME).get_attribute('sandbox')
    assert sandbox is None or 'allow-modals' in sandbox.split(), 'The preview iframe blocks printing'
    # Observe the viewer's real print path without replacing window.print.
    await viewer(page).locator('body').evaluate('''body => {
        body.dataset.printPages = '0';
        body.dataset.printComplete = 'false';
        window.addEventListener('beforeprint', () => {
            body.dataset.printPages = String(
                document.querySelectorAll('#printContainer canvas').length);
        }, {once: true});
        window.addEventListener('afterprint', () => {
            body.dataset.printComplete = 'true';
        }, {once: true});
    }''')


async def expect_pdf_print(page, timeout):
    frame = viewer(page)
    await expect(frame.locator('body')).to_have_attribute('data-print-pages', '2', timeout=timeout)
    await expect(frame.locator('body')).to_have_attribute('data-print-complete', 'true', timeout=timeout)


async def wait_image_width(page, original, larger, timeout):
    image = await viewer(page).locator('.zoomImage').element_handle(timeout=timeout)
    frame = await image.owner_frame()
    comparison = 'image.width > original' if larger else 'Math.abs(image.width - original) <= 1'
    await frame.wait_for_function(
        f'([image, original]) => {comparison}',
        arg=[image, original], timeout=timeout,
    )
