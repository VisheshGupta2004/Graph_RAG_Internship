from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..core.concepts import concept_id
from .html_parser import _heading_level, _unique_section_id, clean_text


VISUAL_TAGS = {"svg", "img"}
CAPTION_CLASSES = {"cap", "svg-cap"}


def extract_image_chunks(parsed_html: dict[str, Any], nested_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract inline diagrams/images and attach each one to the nearest heading."""
    soup: BeautifulSoup = parsed_html["soup"]
    source_file = parsed_html["source_file"]
    root_context = _context_from_root(nested_json)
    stack = [root_context]
    section_counts: dict[str, int] = {}
    image_chunks: list[dict[str, Any]] = []
    order = 0

    body = soup.body or soup
    for element in body.descendants:
        if not isinstance(element, Tag):
            continue

        heading_level = _heading_level(element)
        if heading_level:
            title = clean_text(element.get_text(" ", strip=True))
            if not title:
                continue
            while stack and stack[-1]["level"] >= heading_level:
                stack.pop()
            parent = stack[-1] if stack else root_context
            stack.append(
                {
                    "title": title,
                    "parent_title": parent["title"],
                    "section_id": _unique_section_id(title, source_file, section_counts),
                    "source_file": source_file,
                    "level": heading_level,
                    "breadcrumb": [*parent["breadcrumb"], title],
                }
            )
            continue

        if element.name.lower() not in VISUAL_TAGS:
            continue

        order += 1
        context = stack[-1] if stack else root_context
        visual_type = element.name.lower()
        caption = _caption_for_visual(element)
        labels = _svg_text_labels(element) if visual_type == "svg" else []
        view_box = element.get("viewBox") or element.get("viewbox") or ""

        image_id = _stable_image_id(
            source_file=source_file,
            section_id=context["section_id"],
            order=order,
            visual_type=visual_type,
            labels=labels,
            caption=caption,
        )

        image_chunks.append(
            {
                "image_id": image_id,
                "description": _description(context, source_file, caption, labels),
                "title": context["title"],
                "parent_title": context.get("parent_title") or "",
                "concept_id": concept_id(context["title"]),
                "section_id": context["section_id"],
                "source_file": source_file,
                "type": visual_type,
                "metadata": {
                    "linked_text_section_id": context["section_id"],
                    "caption": caption,
                    "svg_text_labels": labels,
                    "view_box": view_box,
                    "order_in_file": order,
                    "raw_svg_excerpt": _raw_excerpt(element) if visual_type == "svg" else "",
                    "breadcrumb": context["breadcrumb"],
                },
            }
        )

    return image_chunks


def prepare_images_for_storage(image_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize image chunks for ImageChunk insertion."""
    prepared = []
    seen_ids: set[str] = set()
    for chunk in image_chunks:
        image_id = clean_text(chunk.get("image_id", ""))
        description = clean_text(chunk.get("description", ""))
        if not image_id or not description or image_id in seen_ids:
            continue
        seen_ids.add(image_id)

        prepared.append(
            {
                "image_id": image_id,
                "description": description,
                "title": clean_text(chunk.get("title", "")),
                "parent_title": clean_text(chunk.get("parent_title", "")),
                "concept_id": clean_text(chunk.get("concept_id", "")),
                "section_id": clean_text(chunk.get("section_id", "")),
                "source_file": clean_text(chunk.get("source_file", "")),
                "type": clean_text(chunk.get("type", "")),
                "metadata": chunk.get("metadata", {}),
            }
        )
    return prepared


def find_svg_by_image_id(file_path: str | Path, requested_image_id: str) -> str | None:
    """Find the full inline SVG markup for an image_id in one HTML source file."""
    from .html_parser import build_nested_structure, parse_html

    parsed = parse_html(file_path)
    soup: BeautifulSoup = parsed["soup"]
    source_file = parsed["source_file"]
    root_context = _context_from_root(build_nested_structure(parsed))
    stack = [root_context]
    section_counts: dict[str, int] = {}
    order = 0

    body = soup.body or soup
    for element in body.descendants:
        if not isinstance(element, Tag):
            continue

        heading_level = _heading_level(element)
        if heading_level:
            title = clean_text(element.get_text(" ", strip=True))
            if not title:
                continue
            while stack and stack[-1]["level"] >= heading_level:
                stack.pop()
            parent = stack[-1] if stack else root_context
            stack.append(
                {
                    "title": title,
                    "parent_title": parent["title"],
                    "section_id": _unique_section_id(title, source_file, section_counts),
                    "source_file": source_file,
                    "level": heading_level,
                    "breadcrumb": [*parent["breadcrumb"], title],
                }
            )
            continue

        if element.name.lower() not in VISUAL_TAGS:
            continue

        order += 1
        if element.name.lower() != "svg":
            continue

        context = stack[-1] if stack else root_context
        caption = _caption_for_visual(element)
        labels = _svg_text_labels(element)
        image_id = _stable_image_id(
            source_file=source_file,
            section_id=context["section_id"],
            order=order,
            visual_type="svg",
            labels=labels,
            caption=caption,
        )
        if image_id == requested_image_id:
            return str(element)
    return None


def _context_from_root(root: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": root["title"],
        "parent_title": root.get("parent_title") or "",
        "section_id": root["section_id"],
        "source_file": root["source_file"],
        "level": root["level"],
        "breadcrumb": [root["title"]],
    }


def _caption_for_visual(element: Tag) -> str:
    caption = _caption_from_siblings(element)
    if caption:
        return caption
    parent = element.parent
    if isinstance(parent, Tag):
        return _caption_from_siblings(parent)
    return ""


def _caption_from_siblings(element: Tag) -> str:
    for sibling in element.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if _is_caption(sibling):
            return clean_text(sibling.get_text(" ", strip=True))
        if sibling.name.lower() in {"svg", "img"} or _heading_level(sibling):
            break
    return ""


def _is_caption(element: Tag) -> bool:
    if element.name.lower() in {"caption", "figcaption"}:
        return True
    return bool(set(element.get("class", [])) & CAPTION_CLASSES)


def _svg_text_labels(svg: Tag) -> list[str]:
    labels = []
    seen = set()
    for text_tag in svg.find_all("text"):
        label = clean_text(text_tag.get_text(" ", strip=True))
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def _description(context: dict[str, Any], source_file: str, caption: str, labels: list[str]) -> str:
    parts = [f"Diagram under: {context['title']}."]
    if caption:
        parts.append(f"Caption: {caption}.")
    if labels:
        parts.append(f"Visible labels: {'; '.join(labels)}.")
    parts.append(f"Context: {context.get('parent_title') or 'root'} / {source_file}.")
    description = clean_text(" ".join(parts))
    if caption or labels:
        return description
    return f'Diagram attached to section "{context["title"]}" in "{source_file}".'


def _raw_excerpt(element: Tag) -> str:
    return clean_text(str(element))[:500]


def _stable_image_id(
    source_file: str,
    section_id: str,
    order: int,
    visual_type: str,
    labels: list[str],
    caption: str,
) -> str:
    raw = f"{source_file}|{section_id}|{order}|{visual_type}|{'|'.join(labels)}|{caption}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]
