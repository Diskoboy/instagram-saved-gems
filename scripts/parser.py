"""
Парсит saved_posts.html и saved_collections.html → data/links.json

Usage:
  python scripts/parser.py                         # из HTML-файлов
  python scripts/parser.py --txt inst.txt          # из текстового файла со ссылками
"""
import argparse
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def extract_post_id(url: str) -> str | None:
    m = re.search(r'/(?:p|reel|tv)/([^/?#]+)', url)
    return m.group(1) if m else None


def parse_saved_posts(filepath: Path) -> list[dict]:
    posts = []
    with open(filepath, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')

    for block in soup.find_all(class_='pam'):
        # Author: first inner div with class _a6-h
        author_div = block.find('div', class_='_a6-h')
        author = author_div.get_text(strip=True) if author_div else ''

        # URL: first <a> with instagram.com
        link = block.find('a', href=re.compile(r'instagram\.com'))
        if not link:
            continue
        url = link['href'].rstrip('/')

        # Timestamp: second <tr> → second <td>
        rows = block.find_all('tr')
        saved_at = ''
        if len(rows) >= 2:
            tds = rows[1].find_all('td')
            if len(tds) >= 2:
                saved_at = tds[1].get_text(strip=True)

        post_id = extract_post_id(url)
        if post_id:
            posts.append({'id': post_id, 'url': url, 'author': author, 'saved_at': saved_at})

    return posts


def parse_saved_collections(filepath: Path) -> list[dict]:
    posts = []
    with open(filepath, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')

    for block in soup.find_all(class_='pam'):
        # URL and author: <a href=url>author</a>
        link = block.find('a', href=re.compile(r'instagram\.com'))
        if not link:
            continue
        url = link['href'].rstrip('/')
        author = link.get_text(strip=True)

        # Timestamp: row with "Added Time"
        saved_at = ''
        rows = block.find_all('tr')
        if len(rows) >= 2:
            tds = rows[1].find_all('td')
            if len(tds) >= 2:
                saved_at = tds[1].get_text(strip=True)

        post_id = extract_post_id(url)
        if post_id:
            posts.append({'id': post_id, 'url': url, 'author': author, 'saved_at': saved_at})

    return posts


def parse_txt(filepath: Path) -> list[dict]:
    posts = []
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            post_id = extract_post_id(line)
            if not post_id:
                continue
            post_type = 'reel' if '/reel/' in line else 'p'
            clean_url = f'https://www.instagram.com/{post_type}/{post_id}/'
            posts.append({'id': post_id, 'url': clean_url, 'author': '', 'saved_at': ''})
    return posts


def main():
    parser = argparse.ArgumentParser(description='Parse Instagram saved links')
    parser.add_argument('--txt', metavar='FILE', help='Text file with Instagram URLs (one per line)')
    args = parser.parse_args()

    base = Path('.')
    all_posts: list[dict] = []

    if args.txt:
        found = parse_txt(Path(args.txt))
        print(f'{args.txt}: {len(found)} posts')
        all_posts.extend(found)
    else:
        if (p := base / 'saved_posts.html').exists():
            found = parse_saved_posts(p)
            print(f'saved_posts.html: {len(found)} posts')
            all_posts.extend(found)
        else:
            print('saved_posts.html not found, skipping')

        if (p := base / 'saved_collections.html').exists():
            found = parse_saved_collections(p)
            print(f'saved_collections.html: {len(found)} posts')
            all_posts.extend(found)
        else:
            print('saved_collections.html not found, skipping')

    # Deduplicate by url, keep first occurrence
    seen: set[str] = set()
    unique: list[dict] = []
    for post in all_posts:
        if post['url'] not in seen:
            seen.add(post['url'])
            unique.append(post)

    out = Path('data/links.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(unique, ensure_ascii=False, indent=2))
    print(f'Total unique: {len(unique)} → {out}')


if __name__ == '__main__':
    main()
