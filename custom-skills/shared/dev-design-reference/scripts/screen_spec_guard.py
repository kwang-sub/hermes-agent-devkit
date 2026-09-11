#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_STATUS = {"DRAFT", "REFERENCE", "APPROVED"}
ALLOWED_SOURCE = {"IMAGE", "FIGMA"}
ALLOWED_FIDELITY = {"STRUCTURE", "VISUAL", "HIGH"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class SpecError(RuntimeError):
    pass


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise SpecError("screen spec must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SpecError("screen spec frontmatter end marker is missing")
    values: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", raw)
        if not match:
            raise SpecError(f"unsupported frontmatter line: {raw}")
        key, value = match.groups()
        values[key] = value.strip().strip('"\'')
    return values


def validate(spec: Path) -> dict[str, str]:
    if not spec.is_file():
        raise SpecError(f"screen spec not found: {spec}")
    values = parse_frontmatter(spec.read_text(encoding="utf-8"))
    required = ("screen", "status", "source", "reference", "fidelity", "viewport")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise SpecError("missing required frontmatter: " + ", ".join(missing))

    status = values["status"].upper()
    source = values["source"].upper()
    fidelity = values["fidelity"].upper()
    if status not in ALLOWED_STATUS:
        raise SpecError(f"invalid status: {values['status']}")
    if source not in ALLOWED_SOURCE:
        raise SpecError(f"invalid source: {values['source']}")
    if fidelity not in ALLOWED_FIDELITY:
        raise SpecError(f"invalid fidelity: {values['fidelity']}")

    viewport = values["viewport"]
    if viewport != "UNKNOWN" and not re.fullmatch(r"\d{2,5}x\d{2,5}", viewport):
        raise SpecError("viewport must be <width>x<height> or UNKNOWN")

    reference = values["reference"]
    if source == "IMAGE":
        parsed = urlparse(reference)
        if parsed.scheme or parsed.netloc:
            raise SpecError("IMAGE reference must be a repository/local path, not URL")
        target = (spec.parent / reference).resolve()
        if target.suffix.lower() not in IMAGE_EXTENSIONS:
            raise SpecError("IMAGE reference must be PNG/JPG/JPEG/WEBP")
        if not target.is_file():
            raise SpecError(f"IMAGE reference not found: {target}")
    else:
        parsed = urlparse(reference)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"figma.com", "www.figma.com"}:
            raise SpecError("FIGMA reference must be an https://figma.com URL")

    return {
        **values,
        "status": status,
        "source": source,
        "fidelity": fidelity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hermes frontend screen reference package")
    parser.add_argument("--spec", required=True)
    args = parser.parse_args()
    try:
        result = validate(Path(args.spec).expanduser().resolve())
    except SpecError as exc:
        print(f"SCREEN_SPEC_STATUS=blocked\nERROR={exc}")
        return 2
    print("SCREEN_SPEC_STATUS=pass")
    print(f"SCREEN={result['screen']}")
    print(f"DESIGN_STATUS={result['status']}")
    print(f"DESIGN_SOURCE={result['source']}")
    print(f"DESIGN_FIDELITY={result['fidelity']}")
    print(f"VIEWPORT={result['viewport']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
