from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Post, ThreadSummary


THREAD_RE = re.compile(r"(?:^|[?&])tid=(\d+)")
WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


def clean_text(value: str) -> str:
    lines = []
    for line in value.replace("\xa0", " ").splitlines():
        cleaned = WHITESPACE_RE.sub(" ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _tid_from_href(href: str) -> str | None:
    parsed = urlparse(href)
    tid = parse_qs(parsed.query).get("tid", [None])[0]
    if tid:
        return tid
    match = THREAD_RE.search(href)
    return match.group(1) if match else None


def _split_cell_lines(cell) -> list[str]:
    return clean_text(cell.get_text("\n")).splitlines()


def _parse_counts(value: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s*/\s*(\d+)", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _class_names(node) -> set[str]:
    if node is None:
        return set()
    class_value = node.get("class", [])
    if isinstance(class_value, str):
        return set(class_value.split())
    return set(class_value)


def _is_pinned_thread(anchor, row) -> bool:
    nodes = [node for node in (anchor, row) if node]
    nodes.extend(anchor.find_parents(["tbody", "tr", "th", "td"]))

    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id.startswith("stickthread_"):
            return True
        if _class_names(node) & {"stickthread", "sticky", "pinned"}:
            return True

    tbody = anchor.find_parent("tbody")
    if tbody is not None:
        previous_tbody_text = [clean_text(node.get_text("\n")) for node in tbody.find_previous_siblings("tbody")]
        next_tbody_text = [clean_text(node.get_text("\n")) for node in tbody.find_next_siblings("tbody")]
        if not any("版块主题" in text for text in previous_tbody_text) and any(
            "版块主题" in text for text in next_tbody_text
        ):
            return True

    return False


def parse_forum_listing(html: str, base_url: str) -> list[ThreadSummary]:
    soup = BeautifulSoup(html, "html.parser")
    threads: list[ThreadSummary] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "viewthread.php" not in href:
            continue

        tid = _tid_from_href(href)
        title = clean_text(anchor.get_text())
        if not tid or not title or tid in seen:
            continue

        row = anchor.find_parent("tr")
        author = created_at = last_author = last_at = ""
        replies = views = None
        if row:
            cells = row.find_all(["td", "th"], recursive=False)
            anchor_cell = anchor.find_parent(["td", "th"])
            anchor_cell_index = cells.index(anchor_cell) if anchor_cell in cells else -1
            trailing_cells = cells[anchor_cell_index + 1 :] if anchor_cell_index >= 0 else []
            if trailing_cells:
                author_lines = _split_cell_lines(trailing_cells[0])
                author = author_lines[0] if author_lines else ""
                created_at = author_lines[1] if len(author_lines) > 1 else ""
            if len(trailing_cells) > 1:
                replies, views = _parse_counts(clean_text(trailing_cells[1].get_text(" ")))
            if len(trailing_cells) > 2:
                last_lines = _split_cell_lines(trailing_cells[2])
                last_author = last_lines[0] if last_lines else ""
                last_at = last_lines[1] if len(last_lines) > 1 else ""

        seen.add(tid)
        threads.append(
            ThreadSummary(
                tid=tid,
                title=title,
                url=urljoin(base_url, href),
                author=author,
                created_at=created_at,
                replies=replies,
                views=views,
                last_author=last_author,
                last_at=last_at,
                is_pinned=_is_pinned_thread(anchor, row),
            )
        )

    return threads


def is_login_required_page(html: str) -> bool:
    text = clean_text(BeautifulSoup(html, "html.parser").get_text("\n"))
    return "您还未登录" in text or "无权访问该版块" in text


def parse_thread(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []

    for container in soup.find_all(id=re.compile(r"^post_\d+")):
        message = container.select_one(".t_msgfont") or container.select_one("[id^=postmessage_]")
        if not message:
            continue

        pid = str(container.get("id", "")).removeprefix("post_")

        author_node = container.select_one(".postauthor > .postinfo a") or container.select_one(".postauthor a")
        if not author_node:
            fallback_author_node = container.select_one(".postauthor")
            if fallback_author_node and fallback_author_node.name != "td":
                author_node = fallback_author_node
        info_node = (
            container.select_one(".authorinfo [id^=authorposton]")
            or container.select_one(".postcontent .postinfo")
            or container.select_one(".postinfo")
        )
        info_text = clean_text(info_node.get_text("\n")) if info_node else ""
        published_at = re.sub(r"^发表于\s*", "", info_text.splitlines()[0]).strip() if info_text else ""

        posts.append(
            Post(
                author=clean_text(author_node.get_text()) if author_node else "",
                published_at=published_at,
                content=clean_text(message.get_text("\n")),
                pid=pid,
            )
        )

    return posts
