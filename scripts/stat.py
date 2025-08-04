import json
import pandas as pd
import re

header_pattern = re.compile(r'#+\s+(\S.*)$')

def get_notebook_stats(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    cells = notebook['cells']
    last_header = None

    start_times = []
    durations = []
    items = []
    for cell in cells:
        if cell['cell_type'] == 'markdown':
            for text in cell['source']:
                m = header_pattern.match(text.strip())
                if not m:
                    continue
                if len(durations) > 0:
                    items.append({
                        'header': last_header,
                        'start_time': start_times[0] if len(start_times) > 0 else None,
                        'duration': sum(durations, 0),
                    })
                    durations = []
                    start_times = []
                last_header = m.group(1)
            continue
        if cell['cell_type'] != 'code':
            continue
        if 'papermill' not in cell['metadata']:
            continue
        if 'start_time' in cell['metadata']['papermill'] and cell['metadata']['papermill']['start_time'] is not None:
            start_times.append(cell['metadata']['papermill']['start_time'])
        if 'duration' in cell['metadata']['papermill']:
            durations.append(cell['metadata']['papermill']['duration'] or 0)
    if len(durations) > 0:
        items.append({
            'header': last_header,
            'start_time': start_times[0] if len(start_times) > 0 else None,
            'duration': sum(durations, 0),
        })
        durations = []
        start_times = []
    return pd.DataFrame(items)

def get_last_header(output_path):
    headers = []
    last_header = None
    
    with open(output_path, 'r') as f:
        notebook = json.load(f)
        for cell in notebook['cells']:
            if cell['cell_type'] == 'markdown':
                for text in cell['source']:
                    m = header_pattern.match(text.strip())
                    if not m:
                        continue
                    last_header = m.group(1)
                continue
            if 'execution_count' not in cell:
                continue
            if cell['execution_count'] is None:
                break
            if len(headers) > 0 and headers[-1] == last_header:
                continue
            headers.append(last_header)
    if len(headers) == 0:
        return None
    return headers[-1]
