"""
Извлекает thumbnail из видеопостов (reel/video) через ffmpeg.
Сохраняет content/{id}/thumbnail.jpg и обновляет data/posts.json.
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    posts_path = Path('data/posts.json')
    if not posts_path.exists():
        print('data/posts.json not found.')
        sys.exit(1)

    posts: list[dict] = json.loads(posts_path.read_text(encoding='utf-8'))
    updated = 0

    for i, post in enumerate(posts, 1):
        if post.get('fetch_error'):
            continue
        if post.get('type') not in ('reel', 'video'):
            continue

        thumb_path = Path(f'content/{post["id"]}/thumbnail.jpg')

        if post.get('thumbnail') and thumb_path.exists():
            print(f'[{i}] {post["id"]} already has thumbnail, skipping')
            continue

        mp4_files = list(Path(f'content/{post["id"]}').glob('*.mp4'))
        if not mp4_files:
            print(f'[{i}] {post["id"]} no mp4 found, skipping')
            continue

        mp4 = mp4_files[0]
        print(f'[{i}] {post["id"]} extracting thumbnail from {mp4.name}…')

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-ss', '1',
                '-i', str(mp4),
                '-frames:v', '1',
                '-q:v', '2',
                str(thumb_path),
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode == 0 and thumb_path.exists():
            post['thumbnail'] = f'content/{post["id"]}/thumbnail.jpg'
            updated += 1
            print(f'  → saved {thumb_path}')
        else:
            print(f'  → ffmpeg failed (rc={result.returncode})', file=sys.stderr)

    posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))
    print(f'\nDone. Thumbnails extracted: {updated}')


if __name__ == '__main__':
    main()
