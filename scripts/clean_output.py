#!/usr/bin/env python3
import json
import sys
import re

def contains_rdm_nii_url(content):
    """Check if content contains rdm.nii.ac.jp URL."""
    if isinstance(content, str):
        return bool(re.search(r'rdm\.nii\.ac\.jp', content))
    elif isinstance(content, list):
        return any(contains_rdm_nii_url(item) for item in content)
    elif isinstance(content, dict):
        return any(contains_rdm_nii_url(v) for v in content.values())
    else:
        return False

def contains_email(content):
    """Check if content contains email address."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    if isinstance(content, str):
        return bool(re.search(email_pattern, content))
    elif isinstance(content, list):
        return any(contains_email(item) for item in content)
    elif isinstance(content, dict):
        return any(contains_email(v) for v in content.values())
    else:
        return False

def contains_aws_access_token(content):
    """Check if content contains AWS access token pattern."""
    # AWS access key pattern: 20 characters starting with AKIA, ABIA, ACCA, or ASIA
    aws_pattern = r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b'
    if isinstance(content, str):
        return bool(re.search(aws_pattern, content))
    elif isinstance(content, list):
        return any(contains_aws_access_token(item) for item in content)
    elif isinstance(content, dict):
        return any(contains_aws_access_token(v) for v in content.values())
    else:
        return False

def clean_outputs_with_rdm_nii(notebook_path):
    """Remove outputs from cells containing rdm.nii.ac.jp, email addresses, or AWS access tokens in outputs."""
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    modified = False
    cleaned_count = 0
    
    # Process each cell
    for cell in notebook.get('cells', []):
        # Check outputs only
        if 'outputs' in cell and len(cell['outputs']) > 0:
            output_contains_sensitive = False
            
            for output in cell['outputs']:
                if contains_rdm_nii_url(output) or contains_email(output) or contains_aws_access_token(output):
                    output_contains_sensitive = True
                    break
            
            # If output contains sensitive information, clear outputs
            if output_contains_sensitive:
                cell['outputs'] = []
                modified = True
                cleaned_count += 1
    
    if modified:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        print(f"Updated: {notebook_path} (cleaned outputs from {cleaned_count} cells containing sensitive information)")
    else:
        print(f"No changes needed: {notebook_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for notebook_path in sys.argv[1:]:
            clean_outputs_with_rdm_nii(notebook_path)
    else:
        print("Usage: python clean_output.py <notebook1.ipynb> [notebook2.ipynb ...]")
        sys.exit(1)