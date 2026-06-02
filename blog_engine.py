"""
TrendPulse Blog — SEO article management.
Reads Markdown files from data/articles/, renders them as HTML pages.
"""

import re
from pathlib import Path
from datetime import datetime

ARTICLES_DIR = Path(__file__).parent / "data" / "articles"


def list_articles() -> list:
    """Return all articles sorted by date (newest first)."""
    articles = []
    if not ARTICLES_DIR.exists():
        return articles
    for f in sorted(ARTICLES_DIR.glob("*.md"), reverse=True):
        meta, content = parse_article(f)
        if meta:
            articles.append(meta)
    return articles


def get_article(slug: str) -> dict | None:
    """Get a single article by slug."""
    f = ARTICLES_DIR / f"{slug}.md"
    if not f.exists():
        return None
    meta, content = parse_article(f)
    if meta:
        meta["content_html"] = markdown_to_html(content)
    return meta


def parse_article(path: Path) -> tuple:
    """Parse a Markdown article with YAML-like frontmatter."""
    try:
        text = path.read_text()
        meta = {"slug": path.stem}
        content = text

        # Extract TITLE: and DATE: from top of file
        for line in text.split("\n")[:10]:
            if line.startswith("TITLE:"):
                meta["title"] = line[6:].strip()
            elif line.startswith("DESC:"):
                meta["description"] = line[5:].strip()
            elif line.startswith("KEYWORDS:"):
                meta["keywords"] = line[9:].strip()
            elif line.startswith("DATE:"):
                try:
                    meta["date"] = datetime.strptime(line[5:].strip(), "%Y-%m-%d").strftime("%B %d, %Y")
                except:
                    meta["date"] = line[5:].strip()

        # Content starts after the first blank line following frontmatter
        idx = text.find("\n\n")
        if idx > 0:
            content = text[idx:].strip()

        return meta, content
    except Exception as e:
        print(f"[Blog] Error reading {path}: {e}")
        return {}, ""


def markdown_to_html(md: str) -> str:
    """Simple Markdown → HTML converter (headings, paragraphs, bold, links, lists)."""
    html = []
    in_list = False
    for line in md.split("\n"):
        # Headings
        if line.startswith("### "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h1>{line[2:]}</h1>")
        # List items
        elif line.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{inline_md(line[2:])}</li>")
        # Blank line
        elif not line.strip():
            if in_list: html.append("</ul>"); in_list = False
        # Paragraph
        else:
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<p>{inline_md(line)}</p>")
    if in_list: html.append("</ul>")
    return "\n".join(html)


def inline_md(text: str) -> str:
    """Convert inline Markdown: **bold**, [link](url)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text
