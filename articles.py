"""
TrendPulse Articles — Markdown-based blog system.
Articles are .md files in data/articles/, rendered via marked.js.
"""
import re
from pathlib import Path
from datetime import datetime

ARTICLES_DIR = Path(__file__).parent / "data" / "articles"


from typing import Optional

def parse_article(path: Path) -> Optional[dict]:
    """Parse a markdown article with YAML-like frontmatter."""
    text = path.read_text()
    meta = {}
    body = text

    # Extract frontmatter (--- key: value ---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()

    return {
        "slug": path.stem,
        "title": meta.get("title", path.stem.replace("-", " ").title()),
        "date": meta.get("date", datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")),
        "description": meta.get("description", body[:160].replace("\n", " ")),
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "body_html": _md_to_html(body),
    }


def _md_to_html(md: str) -> str:
    """Simple markdown to HTML (handles headings, bold, links, lists, paragraphs)."""
    lines = md.split("\n")
    html = []
    in_list = False
    in_code = False

    for line in lines:
        # Code blocks
        if line.startswith("```"):
            in_code = not in_code
            html.append("</pre>" if not in_code else "<pre>")
            continue
        if in_code:
            html.append(line)
            continue

        # Headings
        if m := re.match(r"^(#{1,3})\s+(.+)$", line):
            if in_list:
                html.append("</ul>")
                in_list = False
            level = len(m.group(1))
            html.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue

        # Unordered lists
        if m := re.match(r"^[-*]\s+(.+)$", line):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{_inline_md(m.group(1))}</li>")
            continue
        elif in_list:
            html.append("</ul>")
            in_list = False

        # Bold and links in text
        if line.strip():
            html.append(f"<p>{_inline_md(line)}</p>")
        else:
            html.append("")

    if in_list:
        html.append("</ul>")

    return "\n".join(html)


def _inline_md(text: str) -> str:
    """Handle bold, italic, links, code inline."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def get_articles() -> list[dict]:
    """Get all articles sorted by date (newest first)."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    articles = []
    for f in sorted(ARTICLES_DIR.glob("*.md"), reverse=True):
        if art := parse_article(f):
            articles.append(art)
    return articles


def get_article(slug: str) -> Optional[dict]:
    """Get a single article by slug."""
    path = ARTICLES_DIR / f"{slug}.md"
    if path.exists():
        return parse_article(path)
    return None
