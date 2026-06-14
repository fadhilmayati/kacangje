#!/usr/bin/env python3
"""
susun-fail — Organize files in a folder by criteria (date, type, size)
Usage: python3 susun-fail.py '{"folder": "/Users/ali/Downloads", "by": "date"}'
by: date, type, size
"""
import json, sys, os, shutil
from pathlib import Path
from datetime import datetime

def organize(data):
    folder = Path(data.get("folder", str(Path.home() / "Downloads")))
    by = data.get("by", "date")
    dry_run = data.get("dry_run", False)

    if not folder.exists():
        return {"success": False, "error": f"Folder '{folder}' tak wujud"}
    if not folder.is_dir():
        return {"success": False, "error": f"'{folder}' bukan folder"}
    try:
        folder = folder.resolve()
    except Exception as e:
        return {"success": False, "error": f"Path tidak sah: {e}"}

    files = [f for f in folder.iterdir() if f.is_file()]
    if not files:
        return {"success": True, "summary": "Tiada fail dalam folder.", "moved": 0}

    moved = 0
    errors = []

    for f in files:
        try:
            if by == "date":
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                subdir = folder / mtime.strftime("%Y-%m")
            elif by == "type":
                ext = f.suffix[1:].lower() if f.suffix else "lain-lain"
                subdir = folder / ext.upper()
            elif by == "size":
                size = f.stat().st_size
                if size < 1024 * 100:
                    subdir = folder / "kecil"  # < 100KB
                elif size < 1024 * 1024:
                    subdir = folder / "sederhana"  # < 1MB
                else:
                    subdir = folder / "besar"  # > 1MB
            else:
                return {"success": False, "error": f"criteria '{by}' tak dikenal"}

            dest = subdir / f.name
            if dest.exists():
                base, ext = os.path.splitext(f.name)
                dest = subdir / f"{base}_duplicate{ext}"

            if dry_run:
                print(f"  [DRY RUN] {f.name} → {subdir.name}/")
            else:
                subdir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dest))
            moved += 1
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    summary = f"Susun selesai. {moved} fail dipindah ikut {by}."
    if dry_run:
        summary = f"[DRY RUN] {moved} fail akan dipindah ikut {by}."

    result = {"success": True, "summary": summary, "moved": moved, "by": by, "folder": str(folder)}
    if errors:
        result["errors"] = errors
    return result


if __name__ == "__main__":
    data = json.loads(sys.stdin.read() if not sys.argv[1:] else sys.argv[1])
    result = organize(data)
    print(json.dumps(result, indent=2))
