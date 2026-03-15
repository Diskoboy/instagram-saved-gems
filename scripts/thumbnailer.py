"""
Extract thumbnails from video posts (reel/video) via ffmpeg.
Saves content/{id}/thumbnail.jpg and updates meta.json.

Извлекает thumbnail из видеопостов (reel/video) через ffmpeg.
Сохраняет content/{id}/thumbnail.jpg и обновляет meta.json.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import all_post_ids, load_meta, save_meta  # noqa: E402


def main():
    ids = all_post_ids()
    updated = 0

    for i, pid in enumerate(ids, 1):
        post = load_meta(pid)
        if not post:
            continue
        if post.get('fetch_error'):
            continue
        if post.get('type') == 'image':
            media = post.get('media', [])
            if media and Path(media[0]).exists():
                post['thumbnail'] = media[0]
                save_meta(pid, post)
                updated += 1
                print(f'[{i}] {pid} image → thumbnail = {media[0]}')
            else:
                print(f'[{i}] {pid} image but no media file found, skipping')
            continue

        if post.get('type') not in ('reel', 'video'):
            continue

        thumb_path = Path(f'content/{pid}/thumbnail.jpg')

        if post.get('thumbnail') and thumb_path.exists():
            print(f'[{i}] {pid} already has thumbnail, skipping')
            continue

        mp4_files = list(Path(f'content/{pid}').glob('*.mp4'))
        if not mp4_files:
            print(f'[{i}] {pid} no mp4 found, skipping')
            continue

        mp4 = mp4_files[0]
        print(f'[{i}] {pid} extracting thumbnail from {mp4.name}…')

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
            post['thumbnail'] = f'content/{pid}/thumbnail.jpg'
            save_meta(pid, post)
            updated += 1
            print(f'  → saved {thumb_path}')
        else:
            print(f'  → ffmpeg failed (rc={result.returncode})', file=sys.stderr)

    print(f'\nDone. Thumbnails extracted: {updated}')


if __name__ == '__main__':
    main()
