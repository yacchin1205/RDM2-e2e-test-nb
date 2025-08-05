#!/usr/bin/env python3
"""
Remove sensitive metadata from Jupyter notebooks before commit.
Specifically removes lc_notebook_meme.lc_server_signature.history
"""

import json
import sys
from pathlib import Path

def clean_notebook(filepath):
    """Remove sensitive metadata from a notebook file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    modified = False
    
    # Clean notebook-level metadata
    if 'metadata' in notebook:
        if 'lc_notebook_meme' in notebook['metadata']:
            if 'lc_server_signature' in notebook['metadata']['lc_notebook_meme']:
                if 'history' in notebook['metadata']['lc_notebook_meme']['lc_server_signature']:
                    del notebook['metadata']['lc_notebook_meme']['lc_server_signature']['history']
                    modified = True
                    print(f"  Removed lc_server_signature.history from {filepath}")
    
    # Clean cell-level metadata
    if 'cells' in notebook:
        for i, cell in enumerate(notebook['cells']):
            if 'metadata' in cell:
                if 'lc_cell_meme' in cell['metadata']:
                    if 'lc_server_signature' in cell['metadata']['lc_cell_meme']:
                        if 'history' in cell['metadata']['lc_cell_meme']['lc_server_signature']:
                            del cell['metadata']['lc_cell_meme']['lc_server_signature']['history']
                            modified = True
                            print(f"  Removed lc_server_signature.history from cell {i} in {filepath}")
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python clean_notebook_metadata.py <notebook.ipynb> [notebook2.ipynb ...]")
        sys.exit(1)
    
    total_cleaned = 0
    for filepath in sys.argv[1:]:
        path = Path(filepath)
        if path.suffix == '.ipynb' and path.exists():
            if clean_notebook(path):
                total_cleaned += 1
        else:
            print(f"Warning: {filepath} is not a valid notebook file or doesn't exist")
    
    print(f"\nCleaned {total_cleaned} notebook(s)")
    return 0

if __name__ == '__main__':
    sys.exit(main())