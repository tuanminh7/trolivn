import os, sys, shutil
from datetime import datetime

# Project root
ROOT = os.path.abspath(os.path.dirname(__file__))
BACKUP_DIR = os.path.join(ROOT, 'encoding_backups_vn')

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# File extensions considered as text
TEXT_EXT = {'.py', '.html', '.htm', '.md', '.txt', '.css', '.js', '.json', '.csv', '.yml', '.yaml', '.ini', '.cfg', '.sql'}

def is_text_file(path):
    return os.path.splitext(path)[1].lower() in TEXT_EXT

def backup_file(path):
    rel = os.path.relpath(path, ROOT)
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f"{ts}_{rel.replace(os.sep, '__')}")
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path

def try_decode(data, enc):
    try:
        return data.decode(enc)
    except Exception:
        return None

def detect_and_decode(data):
    # Try a list of common Vietnamese encodings before falling back to utf-8 with replace
    for enc in ('utf-8', 'utf-8-sig', 'cp1258', 'windows-1258', 'cp1252', 'iso-8859-1'):
        text = try_decode(data, enc)
        if text is not None:
            # If decoding succeeded and no replacement char, accept it
            if '\ufffd' not in text:
                return text, enc
    # Fallback: decode as utf-8 with replace (may contain �) – we will still rewrite to clean up
    return data.decode('utf-8', errors='replace'), 'utf-8-replace'

def enforce_utf8(root):
    changed = []
    for dirpath, _, files in os.walk(root):
        # Skip virtual env and .git
        if 'venv' in dirpath.split(os.sep) or '.git' in dirpath.split(os.sep):
            continue
        for filename in files:
            path = os.path.join(dirpath, filename)
            if not is_text_file(path):
                continue
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
                text, enc_used = detect_and_decode(raw)
                # If the file was not originally utf-8 or contains replacement chars, rewrite
                if enc_used != 'utf-8' or '\ufffd' in text:
                    backup_file(path)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    changed.append((path, enc_used))
            except Exception as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)
    return changed

if __name__ == '__main__':
    changed_files = enforce_utf8(ROOT)
    print('UTF-8 enforcement completed.')
    print(f'Files rewritten: {len(changed_files)}')
    for p, enc in changed_files:
        print(f' - {p} (source encoding: {enc})')
