"""
data/posts/{id}/ → obsidian/<post_id>.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import iter_posts  # noqa: E402


TEMPLATE = """\
---
author: {author}
date: {date}
category: {category}
tags: [{tags}]
type: {type}
---

# Insight

{insight}

{media_embeds}

[Оригинал]({url})

> {description}
"""


def format_tags(hashtags: list[str]) -> str:
    return ', '.join(hashtags)


def format_embeds(media: list[str]) -> str:
    lines = []
    for path in media:
        # Use absolute path from project root → Obsidian ![[...]] syntax
        lines.append(f'![[{path}]]')
    return '\n'.join(lines)


def main():
    posts = list(iter_posts(with_enriched=True))
    out_dir = Path('obsidian')
    out_dir.mkdir(exist_ok=True)

    for post in posts:
        category = post.get('category') or (post.get('categories') or ['прочее'])[0]
        insight = post.get('insight', '').replace('\n', ' ')
        description = post.get('description', '').replace('\n', '\n> ')

        content = TEMPLATE.format(
            author=post.get('author', ''),
            date=post.get('date', ''),
            category=category,
            tags=format_tags(post.get('hashtags', [])),
            type=post.get('type', ''),
            insight=insight or '_нет_',
            media_embeds=format_embeds(post.get('media', [])),
            url=post.get('url', ''),
            description=description or '_нет описания_',
        )

        md_path = out_dir / f"{post['id']}.md"
        md_path.write_text(content, encoding='utf-8')

    print(f'Exported {len(posts)} notes → obsidian/')


if __name__ == '__main__':
    main()
