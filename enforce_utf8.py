import os
import shutil
from datetime import datetime

# Directories and file extensions to process
ROOT = os.path.dirname(__file__)
BACKUP_DIR = os.path.join(ROOT, 'encoding_backups')
TEXT_EXT = {'.py', '.html', '.htm', '.md', '.txt', '.css', '.js', '.json', '.csv', '.yml', '.yaml', '.ini', '.cfg', '.sql'}

def is_text_file(path):
    return os.path.splitext(path)[1].lower() in TEXT_EXT

def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def backup_file(path, rel_path):
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    backup_name = f"{ts}_{rel_path.replace(os.sep, '__')}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(path, backup_path)

def enforce_utf8(root):
    ensure_backup_dir()
    changed = []
    for dirpath, _, files in os.walk(root):
        # Skip virtual environments and git folders
        if 'venv' in dirpath.split(os.sep) or '.git' in dirpath.split(os.sep):
            continue
        for filename in files:
            path = os.path.join(dirpath, filename)
            if not is_text_file(path):
                continue
            try:
                # Read as binary then decode with replace to catch any bad bytes
                with open(path, 'rb') as f:
                    raw = f.read()
                text = raw.decode('utf-8', errors='replace')
                # If there were replacement characters, we rewrite the file
                if '\ufffd' in text:
                    rel = os.path.relpath(path, root)
                    backup_file(path, rel)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    changed.append(path)
            except Exception as e:
                print(f"Error processing {path}: {e}")
    return changed

if __name__ == '__main__':
    changed_files = enforce_utf8(ROOT)
    print('UTF-8 enforcement complete.')
    print(f'Files rewritten: {len(changed_files)}')
    for f in changed_files:
        print(' -', f)
