import nbformat
from nbformat import NotebookNode
import re
from pathlib import Path
from base64 import b64decode
from dataclasses import dataclass
from typing import Iterator
from itertools import islice

def is_markdown_cell(cell):
    return cell['cell_type'] == 'markdown'

def source_first_line(cell):
    return cell['source'].split('\n')[0]

def has_header1(markdown_cell):
    return bool(re.match(r'#\s+(.+)', source_first_line(markdown_cell)))

def has_header2(markdown_cell):
    return bool(re.match(r'##\s+(.+)', source_first_line(markdown_cell)))

def has_outputs(cell):
    return 'outputs' in cell

def has_screenshots(output):
    return 'data' in output and 'image/png' in output['data']

def is_step_sequence_header(markdown_cell):
    m = re.match(r'#\s+(.+)', source_first_line(markdown_cell))
    return bool(m) and m.group(1) != '報告書出力'

def iter_step_sequences(notebook_file):
    notebook = nbformat.read(notebook_file, as_version=nbformat.NO_CONVERT)
    cells = notebook['cells']
    current_header = None
    for i, cell in enumerate(cells):
        if not is_markdown_cell(cell):
            continue
        if has_header1(cell):
            if is_step_sequence_header(cell):
                if current_header:
                    yield islice(cells, current_header, i)
                current_header = i
            else:
                if current_header:
                    yield islice(cells, current_header, i)
                return
    if current_header is not None:
        yield islice(cells, current_header, None)

# As long as the test notebooks are executed sequentially, this
# implementation must be enough.
def collect_all_notebooks(result_dir):
    return sorted(
        (
            p for p in Path(result_dir).rglob("*.ipynb")
            if ".ipynb_checkpoints" not in p.parts
        ),
        key=lambda p: p.stat().st_mtime
    )

def iter_step_result(cells: Iterator[NotebookNode]) -> Iterator[tuple[NotebookNode, list[NotebookNode]]]:
    current_header = None
    buffer: list[Record] = []
    #for cell in iter(cells):
    for cell in cells:
        # TODO: what if, a markdown cell with header1 appears?
        if is_markdown_cell(cell) and has_header2(cell):
            if current_header is not None:
                yield current_header, buffer
            current_header = cell
            buffer = []
        else:
            buffer.append(cell)
    if current_header is not None:
        yield current_header, buffer

def save_screenshot_from_cell(suffix, screenshot_base64, save_dir):
    filename = save_dir.joinpath(f'screenshot-{suffix}.png')
    with open(filename, 'wb') as f:
        f.write(b64decode(screenshot_base64))
    return filename

# The existance of `cell['outputs']` is assumed.
def extract_images_from_cell(step_index, cell, work_dir):
    return [
        save_screenshot_from_cell(f'{step_index}-{i}', img, work_dir)
        for i, img in enumerate([
            out['data']['image/png'] for out in cell['outputs'] if has_screenshots(out)
        ])
    ]
