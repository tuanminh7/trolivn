import os
import sys
from datetime import datetime

ROOT = os.path.dirname(__file__)
BACKUP_DIR = os.path.join(ROOT, 'encoding_backups')
TEXT_EXT = {'.py', '.html', '.htm', '.md', '.txt', '.css', '.js', '.json', '.csv', '.yml', '.yaml', '.ini', '.cfg', '.sql'}

def is_text_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in TEXT_EXT

def scan_and_fix(root):
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    problems = []
    fixed = []
    for dirpath, dirs, files in os.walk(root):
        # skip virtual env and .git
        if 'venv' in dirpath.split(os.sep) or '.git' in dirpath.split(os.sep):
            continue
        for f in files:
            path = os.path.join(dirpath, f)
            if not is_text_file(path):
                continue
            try:
                with open(path, 'rb') as fh:
                    data = fh.read()
                # try decode utf-8
                data.decode('utf-8')
            except Exception as e:
                problems.append((path, str(e)))
                # attempt to read as cp1252 then rewrite as utf-8
                try:
                    text = data.decode('cp1252')
                    # backup
                    rel = os.path.relpath(path, root)
                    ts = datetime.now().strftime('%Y%m%d%H%M%S')
                    bak_path = os.path.join(BACKUP_DIR, ts + '_' + rel.replace(os.sep, '__'))
                    os.makedirs(os.path.dirname(bak_path), exist_ok=True)
                    with open(bak_path, 'wb') as bf:
                        bf.write(data)
                    # write utf-8
                    with open(path, 'w', encoding='utf-8') as wf:
                        wf.write(text)
                    fixed.append(path)
                except Exception as e2:
                    print('Failed to fix', path, e2)
    return problems, fixed

if __name__ == '__main__':
    problems, fixed = scan_and_fix(ROOT)
    print('\nScan complete.')
    print('Files with encoding problems:', len(problems))
    for p, err in problems:
        print('-', p, '->', err)
    print('\nFiles auto-fixed (cp1252 -> utf-8):', len(fixed))
    for p in fixed:
        print('-', p)
    if problems and not fixed:
        print('\nNo fixes applied. For difficult encodings, review backups in', BACKUP_DIR)
    sys.exit(0)
