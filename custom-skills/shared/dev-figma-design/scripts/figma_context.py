#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.figma.com"
TIMEOUT = 20
MAX_DEPTH = 6
HOSTS = {"figma.com", "www.figma.com"}
FILE_TYPES = {"design", "file", "proto", "board", "make"}


class FigmaError(RuntimeError):
    pass


def normalize_node_id(value: str | None) -> str | None:
    if not value:
        return None
    value = urllib.parse.unquote(value).strip()
    if ":" in value or ";" in value:
        return value
    if re.fullmatch(r"\d+(?:-\d+)+", value):
        return value.replace("-", ":")
    return value


def parse_figma_url(url: str) -> tuple[str, str | None]:
    parsed = urllib.parse.urlparse(url)
    if (parsed.hostname or "").lower() not in HOSTS:
        raise FigmaError("Figma URL host must be figma.com")
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) < 2 or parts[0] not in FILE_TYPES:
        raise FigmaError("Unsupported Figma URL path")
    key = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise FigmaError("Invalid Figma file key")
    query = urllib.parse.parse_qs(parsed.query)
    node = (query.get("node-id") or query.get("node_id") or [None])[0]
    return key, normalize_node_id(node)


def auth_headers() -> dict[str, str]:
    oauth = os.getenv("FIGMA_OAUTH_TOKEN", "").strip()
    token = os.getenv("FIGMA_ACCESS_TOKEN", "").strip()
    if oauth:
        return {"Authorization": f"Bearer {oauth}"}
    if token:
        return {"X-Figma-Token": token}
    raise FigmaError("Set FIGMA_ACCESS_TOKEN or FIGMA_OAUTH_TOKEN")


def request_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = API_BASE + path + (("?" + query) if query else "")
    headers = {"Accept": "application/json", "User-Agent": "hermes-agent-devkit/figma-read"}
    headers.update(auth_headers())
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise FigmaError("Figma API returned non-object JSON")
            return data
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise FigmaError("Figma authentication/permission failed (HTTP 403)") from exc
        if exc.code == 404:
            raise FigmaError("Figma file or node was not found (HTTP 404)") from exc
        if exc.code == 429:
            retry = exc.headers.get("Retry-After") if exc.headers else None
            suffix = f"; retry-after={retry}" if retry else ""
            raise FigmaError(f"Figma rate limit exceeded (HTTP 429){suffix}") from exc
        raise FigmaError(f"Figma API request failed (HTTP {exc.code})") from exc
    except urllib.error.URLError as exc:
        raise FigmaError(f"Figma API network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise FigmaError("Figma API returned invalid JSON") from exc


def summarize(node: dict[str, Any], child_limit: int = 80) -> dict[str, Any]:
    keys = (
        "id", "name", "type", "visible", "locked", "opacity",
        "absoluteBoundingBox", "absoluteRenderBounds", "layoutMode", "layoutWrap",
        "primaryAxisSizingMode", "counterAxisSizingMode", "itemSpacing", "counterAxisSpacing",
        "paddingLeft", "paddingRight", "paddingTop", "paddingBottom", "constraints",
        "clipsContent", "cornerRadius", "rectangleCornerRadii", "fills", "strokes",
        "strokeWeight", "effects", "blendMode", "characters", "style", "styles",
        "componentId", "componentProperties", "reactions", "annotations",
    )
    result = {key: node[key] for key in keys if key in node}
    children = node.get("children")
    if isinstance(children, list):
        kept = [child for child in children[:child_limit] if isinstance(child, dict)]
        result["children"] = [summarize(child, child_limit) for child in kept]
        if len(children) > child_limit:
            result["childrenTruncated"] = len(children) - child_limit
    return result


def inspect(url: str, depth: int, render: bool, raw: bool, allow_file: bool) -> dict[str, Any]:
    key, node_id = parse_figma_url(url)
    if depth < 1 or depth > MAX_DEPTH:
        raise FigmaError(f"depth must be 1..{MAX_DEPTH}")
    quoted_key = urllib.parse.quote(key, safe="")

    if node_id:
        response = request_json(f"/v1/files/{quoted_key}/nodes", {"ids": node_id, "depth": str(depth)})
        entry = (response.get("nodes") or {}).get(node_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("document"), dict):
            raise FigmaError("Requested Figma node was not returned")
        result: dict[str, Any] = {
            "status": "pass",
            "source": {"url": url, "fileKey": key, "nodeId": node_id, "fileName": response.get("name"), "lastModified": response.get("lastModified"), "version": response.get("version")},
            "node": summarize(entry["document"]),
            "components": entry.get("components", {}),
            "componentSets": entry.get("componentSets", {}),
            "styles": entry.get("styles", {}),
        }
        if render:
            image = request_json(f"/v1/images/{quoted_key}", {"ids": node_id, "format": "png", "scale": "1"})
            result["renderUrl"] = (image.get("images") or {}).get(node_id)
        if raw:
            result["raw"] = response
        return result

    if not allow_file:
        raise FigmaError("Figma URL has no node-id; use a selected frame/component URL or --allow-file")
    response = request_json(f"/v1/files/{quoted_key}", {"depth": str(min(depth, 2))})
    document = response.get("document")
    if not isinstance(document, dict):
        raise FigmaError("Figma file document was not returned")
    result = {
        "status": "pass",
        "source": {"url": url, "fileKey": key, "nodeId": None, "fileName": response.get("name"), "lastModified": response.get("lastModified"), "version": response.get("version")},
        "node": summarize(document),
        "components": response.get("components", {}),
        "componentSets": response.get("componentSets", {}),
        "styles": response.get("styles", {}),
    }
    if raw:
        result["raw"] = response
    return result


def safe_output(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    roots = [Path(item).expanduser().resolve() for item in os.getenv("HERMES_WRITE_SAFE_ROOT", "/workspace:/opt/data").split(":") if item]
    for root in roots:
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue
    raise FigmaError("preview output must be inside HERMES_WRITE_SAFE_ROOT")


def download_preview(url: str, output: str) -> Path:
    target = safe_output(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-agent-devkit/figma-read"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            target.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise FigmaError(f"Figma preview download failed: {exc.reason}") from exc
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Read bounded Figma design context for Hermes")
    sub = parser.add_subparsers(dest="command", required=True)
    parse = sub.add_parser("parse")
    parse.add_argument("--url", required=True)
    read = sub.add_parser("inspect")
    read.add_argument("--url", required=True)
    read.add_argument("--depth", type=int, default=4)
    read.add_argument("--render", action="store_true")
    read.add_argument("--raw", action="store_true")
    read.add_argument("--allow-file", action="store_true")
    read.add_argument("--preview-out")
    args = parser.parse_args()

    try:
        key, node_id = parse_figma_url(args.url)
        if args.command == "parse":
            print(json.dumps({"status": "pass", "fileKey": key, "nodeId": node_id}, ensure_ascii=False))
            return 0
        result = inspect(args.url, args.depth, bool(args.render or args.preview_out), args.raw, args.allow_file)
        if args.preview_out:
            if not node_id:
                raise FigmaError("--preview-out requires a node-id URL")
            render_url = result.get("renderUrl")
            if not isinstance(render_url, str) or not render_url:
                raise FigmaError("Figma did not return a render URL")
            result["previewPath"] = str(download_preview(render_url, args.preview_out))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except FigmaError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
