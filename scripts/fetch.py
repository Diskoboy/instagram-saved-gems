"""
Читает data/links.json, скачивает медиа через yt-dlp → content/<post_id>/
Для image-постов использует Instagram API как fallback (cookies из Firefox).
Формирует data/posts.json
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

YTDLP = str(Path(__file__).parent.parent / '.venv/bin/yt-dlp')
FIREFOX_PROFILE = os.environ.get('FIREFOX_PROFILE', str(Path.home() / 'snap/firefox/common/.mozilla/firefox'))
BROWSER = os.environ.get('BROWSER', 'firefox')
CHROME_PROFILE = os.environ.get('CHROME_PROFILE', '')

_SHORTCODE_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'


def shortcode_to_mediaid(code: str) -> int:
    n = 0
    for c in code:
        n = n * 64 + _SHORTCODE_ALPHABET.index(c)
    return n


def _load_browser_cookies() -> dict:
    """Read Instagram cookies from Firefox or Chrome profile sqlite."""
    if BROWSER == 'chrome':
        return _load_chrome_cookies()
    return _load_firefox_cookies()


def _load_firefox_cookies() -> dict:
    """Read Instagram cookies from Firefox profile sqlite."""
    profile_dir = Path(FIREFOX_PROFILE)
    # If pointing at parent dir, find actual profile
    if not (profile_dir / 'cookies.sqlite').exists():
        for child in profile_dir.iterdir():
            if (child / 'cookies.sqlite').exists():
                profile_dir = child
                break
    db = profile_dir / 'cookies.sqlite'
    if not db.exists():
        return {}
    try:
        conn = sqlite3.connect(f'file:{db}?immutable=1', uri=True)
        rows = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram%'"
        ).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _load_chrome_cookies() -> dict:
    """Read Instagram cookies from Chrome profile sqlite."""
    import platform
    candidates = []
    if CHROME_PROFILE:
        candidates.append(Path(CHROME_PROFILE) / 'Network' / 'Cookies')
        candidates.append(Path(CHROME_PROFILE) / 'Cookies')
    system = platform.system()
    if system == 'Windows':
        base = Path.home() / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'User Data'
        candidates.append(base / 'Default' / 'Network' / 'Cookies')
    elif system == 'Darwin':
        base = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome'
        candidates.append(base / 'Default' / 'Cookies')
    else:
        base = Path.home() / '.config' / 'google-chrome'
        candidates.append(base / 'Default' / 'Cookies')
    for db in candidates:
        if not db.exists():
            continue
        try:
            conn = sqlite3.connect(f'file:{db}?immutable=1', uri=True)
            rows = conn.execute(
                "SELECT name, value FROM cookies WHERE host_key LIKE '%instagram%'"
            ).fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
        except Exception:
            continue
    return {}


def determine_type(url: str, media_files: list[Path]) -> str:
    if '/reel/' in url:
        return 'reel'
    if '/tv/' in url:
        return 'video'
    if len(media_files) > 1:
        return 'carousel'
    return 'image'


def extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'#\w+', text or '')))


def download_with_ytdlp(url: str, out_dir: Path) -> subprocess.CompletedProcess:
    cmd = [
        YTDLP,
        '--write-info-json',
        '--no-playlist',
        '--cookies-from-browser', f'{BROWSER}:{CHROME_PROFILE if BROWSER == "chrome" else FIREFOX_PROFILE}',
        '--sleep-interval', '1',
        '--max-sleep-interval', '3',
        '--socket-timeout', '30',
        '--write-thumbnail',
        '--convert-thumbnails', 'jpg',
        '-o', str(out_dir / 'media_%(autonumber)s.%(ext)s'),
        '-o', f'thumbnail:{out_dir}/thumbnail.%(ext)s',
        url,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def download_with_instagram_api(post_id: str, out_dir: Path) -> bool:
    """Fallback for image posts. Uses Instagram private API with Firefox cookies."""
    cookies = _load_browser_cookies()
    if not cookies.get('sessionid'):
        return False

    cookie_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
    headers = {
        'Cookie': cookie_str,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
        'Accept': '*/*',
        'X-IG-App-ID': '936619743392459',
        'X-CSRFToken': cookies.get('csrftoken', ''),
        'Referer': 'https://www.instagram.com/',
    }

    try:
        media_id = shortcode_to_mediaid(post_id)
        url = f'https://i.instagram.com/api/v1/media/{media_id}/info/'
        req = urllib.request.Request(url, headers=headers)
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print(f'  instagram api error: {e}', file=sys.stderr)
        return False

    item = data.get('items', [{}])[0]
    caption = item.get('caption')
    if isinstance(caption, dict):
        (out_dir / 'description.txt').write_text(caption.get('text', ''), encoding='utf-8')

    def _get_media_items(item: dict) -> list[dict]:
        if item.get('media_type') == 8:  # carousel
            return item.get('carousel_media', [])
        return [item]

    downloaded = 0
    for idx, media in enumerate(_get_media_items(item), 1):
        media_type = media.get('media_type', 1)
        if media_type == 2:  # video
            versions = media.get('video_versions', [])
            ext = 'mp4'
        else:  # image
            versions = media.get('image_versions2', {}).get('candidates', [])
            ext = 'jpg'
        if not versions:
            continue
        img_url = versions[0]['url']
        dest = out_dir / f'media_{idx:03d}.{ext}'
        try:
            urllib.request.urlretrieve(img_url, dest)
            downloaded += 1
        except Exception as e:
            print(f'  download error: {e}', file=sys.stderr)

    return downloaded > 0


def download_post(url: str, post_id: str, content_dir: Path) -> dict | None:
    out_dir = content_dir / post_id
    out_dir.mkdir(parents=True, exist_ok=True)

    result = download_with_ytdlp(url, out_dir)

    if result.returncode != 0:
        print(f'  yt-dlp failed, trying instagram api…')
        success = download_with_instagram_api(post_id, out_dir)
        if not success:
            print(f'  yt-dlp error for {post_id}:\n{result.stderr[-300:]}', file=sys.stderr)
            return None

    # Collect description from instaloader .txt if no info.json
    info_files = list(out_dir.glob('*.info.json'))
    description = ''
    if info_files:
        info = json.loads(info_files[0].read_text(encoding='utf-8'))
        description = info.get('description') or info.get('title') or ''
    elif (out_dir / 'description.txt').exists():
        description = (out_dir / 'description.txt').read_text(encoding='utf-8', errors='replace').strip()

    hashtags = extract_hashtags(description)

    media_files = sorted(
        [f for f in out_dir.iterdir()
         if f.suffix not in ('.json', '.txt') and not f.name.startswith('thumbnail')],
        key=lambda f: f.name,
    )
    thumbnail_files = list(out_dir.glob('thumbnail.*'))

    return {
        'description': description,
        'hashtags': hashtags,
        'media': [str(f.relative_to(Path('.'))) for f in media_files],
        'thumbnail': str(thumbnail_files[0].relative_to(Path('.'))) if thumbnail_files else None,
    }


def main():
    links_path = Path('data/links.json')
    if not links_path.exists():
        print('data/links.json not found. Run parser.py first.')
        sys.exit(1)

    links = json.loads(links_path.read_text(encoding='utf-8'))
    content_dir = Path('content')
    content_dir.mkdir(exist_ok=True)

    posts_path = Path('data/posts.json')
    existing: dict[str, dict] = {}
    if posts_path.exists():
        for p in json.loads(posts_path.read_text(encoding='utf-8')):
            existing[p['id']] = p

    retry_errors = '--retry-errors' in sys.argv

    posts: list[dict] = []
    for i, link in enumerate(links, 1):
        post_id = link['id']
        print(f'[{i}/{len(links)}] {post_id}')

        if post_id in existing:
            prev = existing[post_id]
            # Skip if success, or if error and not in retry mode
            if not prev.get('fetch_error'):
                print('  already fetched, skipping')
                posts.append(prev)
                continue
            if prev.get('fetch_error') and not retry_errors:
                print('  previous error, skipping (use --retry-errors to retry)')
                posts.append(prev)
                continue

        meta = download_post(link['url'], post_id, content_dir)
        if meta is None:
            post = {
                'id': post_id,
                'url': link['url'],
                'author': link['author'],
                'date': link['saved_at'],
                'description': '',
                'hashtags': [],
                'type': determine_type(link['url'], []),
                'media': [],
                'fetch_error': True,
            }
        else:
            media_files = [Path(m) for m in meta['media']]
            post = {
                'id': post_id,
                'url': link['url'],
                'author': link['author'],
                'date': link['saved_at'],
                'description': meta['description'],
                'hashtags': meta['hashtags'],
                'type': determine_type(link['url'], media_files),
                'media': meta['media'],
            }
            if meta.get('thumbnail'):
                post['thumbnail'] = meta['thumbnail']

        posts.append(post)
        posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

    posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))
    ok = sum(1 for p in posts if not p.get('fetch_error'))
    err = sum(1 for p in posts if p.get('fetch_error'))
    print(f'\nDone. {ok} OK, {err} errors → {posts_path}')


if __name__ == '__main__':
    main()
