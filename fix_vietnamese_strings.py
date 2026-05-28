import os, re, shutil
from datetime import datetime

ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT, "templates")
BACKUP_DIR = os.path.join(ROOT, "encoding_backups_str")

os.makedirs(BACKUP_DIR, exist_ok=True)

# Mapping of garbled fragments to correct Vietnamese
REPLACEMENTS = {
    r"Quản tr�": "Quản trị",
    r"H�": "Hồ",
    r"H�\"": "Hồ",
    r"trắc nghi�?m": "trắc nghiệm",
    r"N�Ti dung": "Nội dung",
    r"Đi�fm": "Điểm",
    r"Mức �": "Mức",
    r"Ch�?nh sửa": "Chỉnh sửa",
    r"Tâm lý học �'ường": "Tâm lý học trường",
    r"Hi�?n mật khẩu": "Hiển mật khẩu",
    r"�?n mật khẩu": "Hiển mật khẩu",
    r"�Y'�": "Hiện",
    r"\?": "",
    r"�?": "",
    r"�": "",
    r"�?": "",
    r"�\"": "",
    r"�\'": "",
    r"�\%": "",
    r"�?\"": "",
    r"�?\'": "",
    r"�\u": "",
    r"�\n": "",
    r"�\t": "",
    r"�\r": "",
    r"�\0": "",
    r"\’": "'",
    r"\“": '"',
    r"\”": '"',
    r"\‘": "'",
    r"\¨": "",
}

def backup_file(path):
    rel = os.path.relpath(path, ROOT)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    bak_path = os.path.join(BACKUP_DIR, f"{ts}_{rel.replace(os.sep, '__')}")
    os.makedirs(os.path.dirname(bak_path), exist_ok=True)
    shutil.copy2(path, bak_path)

def fix_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    original = content
    for bad, good in REPLACEMENTS.items():
        content = re.sub(bad, good, content)
    if content != original:
        backup_file(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False

if __name__ == "__main__":
    changed = []
    for dirpath, _, filenames in os.walk(TEMPLATE_DIR):
        for fname in filenames:
            if fname.lower().endswith('.html'):
                full = os.path.join(dirpath, fname)
                if fix_file(full):
                    changed.append(full)
    print("Vietnamese text fixing complete.")
    print(f"Files updated: {len(changed)}")
    for p in changed:
        print(' -', p)
