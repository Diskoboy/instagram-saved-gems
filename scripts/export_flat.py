"""
Flat export of all media files to tmp/media/.
Copies files from content/{id}/ with {id}_ prefix for uniqueness.
Excludes thumbnail.jpg and *.info.json. Incremental: skips already copied files.

Плоский экспорт медиафайлов в tmp/media/.
Копирует файлы из content/{id}/ с префиксом {id}_ для уникальности имён.
Пропускает thumbnail.jpg и *.info.json. Инкрементальный: не перезаписывает уже скопированные.

Usage:
  python scripts/export_flat.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import all_post_ids  # noqa: E402

MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webp'}
CONTENT_DIR = Path('content')
OUT_DIR = Path('tmp/media')


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    no_media = 0

    ids = all_post_ids()
    if not ids:
        print('No posts found.')
        return

    for pid in ids:
        src_dir = CONTENT_DIR / pid
        if not src_dir.exists():
            no_media += 1
            continue

        files = [
            f for f in src_dir.iterdir()
            if f.is_file()
            and f.suffix.lower() in MEDIA_EXTS
            and f.name != 'thumbnail.jpg'
            and not f.name.endswith('.info.json')
        ]

        if not files:
            no_media += 1
            continue

        for src in files:
            dst = OUT_DIR / f'{pid}_{src.name}'
            if dst.exists():
                skipped += 1
                continue
            shutil.copy2(src, dst)
            copied += 1

    print(f'Done. Copied: {copied}, skipped (already exists): {skipped}, no media: {no_media}')


if __name__ == '__main__':
    main()
