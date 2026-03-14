"""
Per-post file storage.

Layout:
  data/posts/{id}/meta.json
  data/posts/{id}/transcription.json
  data/posts/{id}/ocr.json
  data/posts/{id}/enriched.json
"""
import json
import re as _re
from pathlib import Path
from typing import Iterator

_CODE_RE = _re.compile(
    r'import |def |git |docker|npm |pip |apt |http|`|\$\s|\.py|\.sh|\.ts|\.js|={2,}',
    _re.I,
)


def _low_overlap(screen: str, trans: str) -> bool:
    s = set(screen.lower().split())
    t = set(trans.lower().split())
    return bool(s) and (len(s & t) / len(s)) < 0.6

DATA_DIR = Path('data/posts')


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def post_dir(pid: str) -> Path:
    return DATA_DIR / pid


def all_post_ids() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir())


def load_meta(pid: str) -> dict | None:
    path = post_dir(pid) / 'meta.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def save_meta(pid: str, data: dict) -> None:
    _atomic_write(post_dir(pid) / 'meta.json', data)


def load_transcription(pid: str) -> dict:
    path = post_dir(pid) / 'transcription.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def save_transcription(pid: str, data: dict) -> None:
    _atomic_write(post_dir(pid) / 'transcription.json', data)


def load_ocr(pid: str) -> dict:
    path = post_dir(pid) / 'ocr.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def save_ocr(pid: str, data: dict) -> None:
    _atomic_write(post_dir(pid) / 'ocr.json', data)


def load_enriched(pid: str) -> dict:
    path = post_dir(pid) / 'enriched.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def save_enriched(pid: str, data: dict) -> None:
    _atomic_write(post_dir(pid) / 'enriched.json', data)


def iter_posts(with_enriched: bool = False) -> Iterator[dict]:
    """Yield post dicts. If with_enriched=True, merges enriched.json into meta."""
    for pid in all_post_ids():
        meta = load_meta(pid)
        if meta is None:
            continue
        post = dict(meta)
        if with_enriched:
            enriched = load_enriched(pid)
            if enriched:
                post.update(enriched)
        transcription = load_transcription(pid)
        if transcription.get('text'):
            post['transcription_text'] = transcription['text']

        ocr = load_ocr(pid)
        if ocr.get('combined'):
            post_type = post.get('type', '')
            screen = ocr['combined']
            if post_type in ('image', 'carousel'):
                post['ocr_text'] = screen
            elif post_type in ('reel', 'video'):
                trans = transcription.get('text', '')
                if _CODE_RE.search(screen) or _low_overlap(screen, trans):
                    post['ocr_text'] = screen

        yield post
