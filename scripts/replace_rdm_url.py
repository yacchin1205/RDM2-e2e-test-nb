#!/usr/bin/env python3
import json
import sys
import re

def replace_rdm_urls_in_content(content):
    """Replace rdm.nii.ac.jp URLs with rdm.example.com in content."""
    if isinstance(content, str):
        # Replace URLs while preserving subdomains
        return re.sub(r'https?://([^/]*\.)?(rdm\.nii\.ac\.jp)', r'https://\1rdm.example.com', content)
    elif isinstance(content, list):
        return [replace_rdm_urls_in_content(item) for item in content]
    else:
        return content

def replace_emails_in_content(content):
    """Replace email addresses with example.com domains in content."""
    if isinstance(content, str):
        # Replace email addresses, but keep test@example.com and user@example.com as is
        def replace_email(match):
            email = match.group(0)
            if email.endswith('@example.com'):
                return email
            # Extract username part and create example email
            username = email.split('@')[0]
            return f"{username}@example.com"
        return re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', replace_email, content)
    elif isinstance(content, list):
        return [replace_emails_in_content(item) for item in content]
    else:
        return content

def replace_rdm_urls_in_notebook(notebook_path):
    """Replace rdm.nii.ac.jp URLs and emails in parameters cells."""
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    modified = False
    
    # Process each cell
    for cell in notebook.get('cells', []):
        # Process source
        if 'source' in cell:
            original = cell['source']
            
            # Check if this is a markdown cell or a code cell with parameters tag
            is_markdown = cell.get('cell_type') == 'markdown'
            is_parameters_code = (
                cell.get('cell_type') == 'code' and
                'metadata' in cell and 
                'tags' in cell['metadata'] and 
                'parameters' in cell['metadata']['tags']
            )
            
            if is_markdown or is_parameters_code:
                # Replace RDM URLs
                cell['source'] = replace_rdm_urls_in_content(cell['source'])
                # Replace emails
                cell['source'] = replace_emails_in_content(cell['source'])
            
            if original != cell['source']:
                modified = True
    
    if modified:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        print(f"Updated: {notebook_path}")
    else:
        print(f"No changes needed: {notebook_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for notebook_path in sys.argv[1:]:
            replace_rdm_urls_in_notebook(notebook_path)
    else:
        print("Usage: python replace_rdm_url.py <notebook1.ipynb> [notebook2.ipynb ...]")
        sys.exit(1)