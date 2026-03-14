"""
Мигрирует данные из старых flat-файлов в per-post структуру.

  data/posts.json    → data/posts/{id}/meta.json
  data/analysis.json → data/posts/{id}/transcription.json + ocr.json
  data/enriched.json → data/posts/{id}/enriched.json

Пропускает уже мигрированные посты (если meta.json существует).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import load_meta, save_meta, save_transcription, save_ocr, save_enriched  # noqa: E402


def migrate_posts(posts_path: Path) -> int:
    if not posts_path.exists():
        print(f'{posts_path} not found, skipping.')
        return 0
    posts = json.loads(posts_path.read_text(encoding='utf-8'))
    migrated = 0
    skipped = 0
    for post in posts:
        pid = post.get('id')
        if not pid:
            continue
        if load_meta(pid) is not None:
            skipped += 1
            continue
        save_meta(pid, post)
        migrated += 1
    if skipped:
        print(f'  posts: {migrated} migrated, {skipped} already exist')
    return migrated


def migrate_analysis(analysis_path: Path) -> tuple[int, int]:
    if not analysis_path.exists():
        print(f'{analysis_path} not found, skipping.')
        return 0, 0
    records = json.loads(analysis_path.read_text(encoding='utf-8'))
    t_count = 0
    o_count = 0
    for record in records:
        pid = record.get('id')
        if not pid:
            continue
        if record.get('transcription'):
            save_transcription(pid, record['transcription'])
            t_count += 1
        if record.get('screen_text'):
            save_ocr(pid, record['screen_text'])
            o_count += 1
    return t_count, o_count


def migrate_enriched(enriched_path: Path) -> int:
    if not enriched_path.exists():
        print(f'{enriched_path} not found, skipping.')
        return 0
    items = json.loads(enriched_path.read_text(encoding='utf-8'))
    migrated = 0
    for item in items:
        pid = item.get('id')
        if not pid:
            continue
        save_enriched(pid, item)
        migrated += 1
    return migrated


def main():
    posts_count = migrate_posts(Path('data/posts.json'))
    print(f'Posts migrated: {posts_count}')

    t_count, o_count = migrate_analysis(Path('data/analysis.json'))
    print(f'Transcriptions migrated: {t_count}, OCR migrated: {o_count}')

    enriched_count = migrate_enriched(Path('data/enriched.json'))
    print(f'Enriched migrated: {enriched_count}')

    print('Migration done.')


if __name__ == '__main__':
    main()
