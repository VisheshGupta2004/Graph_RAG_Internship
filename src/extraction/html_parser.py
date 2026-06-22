from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


HEADING_TAGS = {"h1", "h2", "h3", "h4"}
HEADING_CLASSES = {
    "card-h1": 1,
    "card-h2": 2,
}
CONTENT_TAGS = {
    "p",
    "li",
    "table",
    "blockquote",
    "figcaption",
    "caption",
    "text",
}
CONTENT_CLASSES = {
    "card-p",
    "svg-cap",
    "cl",
    "flow-step",
    "quiz-opt",
    "fail-item",
    "fi-tag",
    "big-stat",
    "big-unit",
    "pill",
}
NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "button",
]


def clean_text(text: str) -> str:
    """Normalize text while keeping content readable for retrieval."""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_html(file_path: str | Path) -> dict[str, Any]:
    """Parse one HTML file and return a BeautifulSoup document plus source metadata."""
    path = Path(file_path)
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    _append_template_card_html(soup, html)

    for selector in NOISE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    return {
        "soup": soup,
        "source_file": path.name,
        "source_path": str(path),
    }


def _append_template_card_html(soup: BeautifulSoup, html: str) -> None:
    """Expose iCard JavaScript template strings as parseable HTML."""
    card_templates = re.findall(r"html:`(.*?)`", html, flags=re.DOTALL)
    if not card_templates:
        return

    target = soup.body or soup
    container = soup.new_tag("div")
    container["data-extracted"] = "template-cards"
    for template in card_templates:
        fragment = BeautifulSoup(template, "lxml")
        for child in list((fragment.body or fragment).children):
            container.append(child)
    target.append(container)


def build_nested_structure(parsed_html: dict[str, Any]) -> dict[str, Any]:
    """Build a nested heading tree from h1-h4 without flattening the document."""
    soup: BeautifulSoup = parsed_html["soup"]
    source_file = parsed_html["source_file"]
    page_title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else source_file
    root = _make_node(
        title=page_title or source_file,
        level=0,
        section_id=_slugify(page_title or source_file),
        source_file=source_file,
        parent_title=None,
    )

    stack = [root]
    section_counts: dict[str, int] = {}

    body = soup.body or soup
    for element in body.descendants:
        if not isinstance(element, Tag):
            continue

        name = element.name.lower()
        heading_level = _heading_level(element)
        if heading_level:
            level = heading_level
            title = clean_text(element.get_text(" ", strip=True))
            if not title:
                continue

            while stack and stack[-1]["level"] >= level:
                stack.pop()
            parent = stack[-1] if stack else root
            section_id = _unique_section_id(title, source_file, section_counts)
            node = _make_node(
                title=title,
                level=level,
                section_id=section_id,
                source_file=source_file,
                parent_title=parent["title"],
            )
            parent["children"].append(node)
            stack.append(node)
            continue

        if _is_content_element(element) and not _inside_heading(element):
            text = _extract_content_text(element)
            if text and not _is_duplicate_of_parent_text(element, text):
                stack[-1]["content_parts"].append(text)

    _finalize_node(root)
    return root


def _make_node(
    title: str,
    level: int,
    section_id: str,
    source_file: str,
    parent_title: str | None,
) -> dict[str, Any]:
    return {
        "title": clean_text(title),
        "content": "",
        "children": [],
        "level": level,
        "section_id": section_id,
        "source_file": source_file,
        "parent_title": parent_title,
        "content_parts": [],
    }


def _finalize_node(node: dict[str, Any]) -> None:
    node["content"] = clean_text("\n".join(node.pop("content_parts", [])))
    for child in node["children"]:
        _finalize_node(child)


def _extract_content_text(element: Tag) -> str:
    if element.name == "table":
        return _table_to_text(element)
    if element.name == "text":
        return clean_text(element.get_text(" ", strip=True))
    return clean_text(element.get_text(" ", strip=True))


def _heading_level(element: Tag) -> int | None:
    name = element.name.lower()
    if name in HEADING_TAGS:
        return int(name[1])

    classes = set(element.get("class", []))
    for class_name, level in HEADING_CLASSES.items():
        if class_name in classes:
            return level
    return None


def _is_content_element(element: Tag) -> bool:
    if element.name.lower() in CONTENT_TAGS:
        return True
    return bool(set(element.get("class", [])) & CONTENT_CLASSES)


def _table_to_text(table: Tag) -> str:
    rows = []
    for row in table.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return clean_text(" ; ".join(rows))


def _inside_heading(element: Tag) -> bool:
    for parent in element.parents:
        if not isinstance(parent, Tag):
            continue
        if _heading_level(parent):
            return True
    return False


def _is_duplicate_of_parent_text(element: Tag, text: str) -> bool:
    parent = element.parent
    if not isinstance(parent, Tag):
        return False
    if parent.name in {"li", "td", "th"}:
        return clean_text(parent.get_text(" ", strip=True)) == text
    return False


def _unique_section_id(title: str, source_file: str, counts: dict[str, int]) -> str:
    base = f"{Path(source_file).stem}-{_slugify(title)}"
    count = counts.get(base, 0) + 1
    counts[base] = count
    return base if count == 1 else f"{base}-{count}"


def _slugify(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "section"
