#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_STATUS = {"DRAFT", "REFERENCE", "APPROVED"}
ALLOWED_SOURCE = {"IMAGE", "FIGMA"}
ALLOWED_FIDELITY = {"STRUCTURE", "VISUAL", "HIGH"}
ALLOWED_VIEW_STRATEGY = {"SHARED", "RESPONSIVE", "HYBRID", "SPLIT_VIEW"}
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


# Bounded Markdown contract, not a general Markdown/YAML parser.
BEHAVIOR_SECTIONS = ("화면 기능 목록", "UI 요소 및 기능 연결", "기능별 동작 명세", "기능별 검증 조건")
FEATURE_COLUMNS = ("기능 ID", "기능명", "사용자 목적 / 설명", "연결 UI ID", "확정 상태", "근거")
UI_COLUMNS = ("UI ID", "요소 / 종류 / 표시명", "위치 / 영역", "연결 기능 ID", "노출 조건", "활성화 / 표시 규칙", "플랫폼 차이")
AC_COLUMNS = ("검증 ID", "기능 ID", "사전 조건 / 상태", "사용자 조작 / 트리거", "기대 결과", "검증 방법")
DETAIL_FIELDS = ("관련 UI", "실행 시점", "사전 조건 / 입력 검증", "정상 결과", "상태 / 예외 처리", "화면 이동 / 저장", "플랫폼 차이")
FEATURE_STATES = {"CONFIRMED", "PROPOSED", "UNKNOWN"}


def contract_lines(text: str) -> list[str]:
    """Ignore fenced examples and HTML comments so they cannot satisfy coverage."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    result: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        result.append(line)
    return result


def sections(lines: list[str], level: int) -> dict[str, list[str]]:
    """Collect headings of one exact level; stop a section at any parent heading."""
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading and len(heading[1]) <= level:
            current = None
        if heading and len(heading[1]) == level:
            current = heading[2].strip()
            if current in result:
                raise SpecError(f"duplicate contract heading: {current}")
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return result


def cell_text(value: str) -> str:
    return value.strip().strip("`").strip()


def filled(value: str, label: str, approved: bool) -> None:
    value = cell_text(value)
    placeholders = {"", "-", "—", "...", "…", "TODO", "TBD", "N/A", "NONE"}
    if value.upper() in placeholders or re.fullmatch(r"<[^>]+>", value):
        raise SpecError(f"empty or placeholder value: {label}")
    if re.match(r"^(TODO|TBD)(?:\s|:|$)", value, re.IGNORECASE):
        raise SpecError(f"unresolved placeholder: {label}")
    if approved and re.match(r"^UNKNOWN(?:\s|:|$)", value, re.IGNORECASE):
        raise SpecError(f"unresolved approved behavior: {label}")


def table_rows(lines: list[str], columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    """One pipe table per section; literal pipes must be escaped as \\|."""
    rows: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        if not line.endswith("|"):
            raise SpecError(f"table row must end with a pipe: {label}")
        cells = [cell_text(value.replace(r"\|", "|")) for value in re.split(r"(?<!\\)\|", line[1:-1])]
        if len(cells) != len(columns):
            raise SpecError(f"wrong table column count: {label}")
        rows.append(cells)
    if len(rows) < 3 or tuple(rows[0]) != columns:
        raise SpecError(f"missing table header or data rows: {label}")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        raise SpecError(f"invalid table separator: {label}")
    return [dict(zip(columns, row)) for row in rows[2:]]


def index_rows(rows: list[dict[str, str]], key: str, prefix: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        identity = row[key]
        if not re.fullmatch(rf"{prefix}-\d{{2,}}", identity):
            raise SpecError(f"invalid {prefix} ID: {identity}")
        if identity in result:
            raise SpecError(f"duplicate {prefix} ID: {identity}")
        result[identity] = row
    return result


def id_refs(value: str, prefix: str, label: str, allow_none: bool = False) -> set[str]:
    if allow_none and value == "NONE":
        return set()
    tokens = [cell_text(token) for token in value.split(",")]
    if not all(re.fullmatch(rf"{prefix}-\d{{2,}}", token) for token in tokens):
        raise SpecError(f"invalid {prefix} references: {label}")
    if len(tokens) != len(set(tokens)):
        raise SpecError(f"duplicate {prefix} references: {label}")
    return set(tokens)


def require_known(refs: set[str], known: dict, label: str) -> None:
    missing = refs - known.keys()
    if missing:
        raise SpecError(f"unknown references in {label}: {', '.join(sorted(missing))}")


def validate_details(lines: list[str], features: dict[str, dict[str, str]],
                     links: dict[str, set[str]], approved: bool) -> None:
    details: dict[str, dict[str, str]] = {}
    for heading, body in sections(lines, 3).items():
        match = re.fullmatch(r"(F-\d{2,})(?:\s+.+)?", heading)
        if not match:
            raise SpecError(f"invalid behavior detail heading: {heading}")
        identity = match[1]
        if identity in details:
            raise SpecError(f"duplicate behavior detail: {identity}")
        if identity not in features:
            raise SpecError(f"unknown behavior detail: {identity}")
        fields: dict[str, str] = {}
        for row in table_rows(body, ("항목", "동작 명세"), identity):
            key = row["항목"]
            if key in fields:
                raise SpecError(f"duplicate behavior field: {identity}/{key}")
            filled(key, identity, approved)
            if key != "관련 UI":
                filled(row["동작 명세"], f"{identity}/{key}", approved)
            fields[key] = row["동작 명세"]
        missing = set(DETAIL_FIELDS) - fields.keys()
        if missing:
            raise SpecError(f"missing behavior fields for {identity}: {', '.join(sorted(missing))}")
        if id_refs(fields["관련 UI"], "UI", identity, allow_none=True) != links[identity]:
            raise SpecError(f"behavior detail UI mismatch: {identity}")
        if not links[identity]:
            filled(fields.get("미노출 사유", ""), f"{identity}/no-UI rationale", approved)
        details[identity] = fields
    if features.keys() != details.keys():
        raise SpecError("missing behavior details: " + ", ".join(sorted(features.keys() - details.keys())))


def validate_behavior(text: str, values: dict[str, str], *, require_contract: bool,
                      require_approved: bool) -> dict[str, str]:
    version = values.get("spec_version", "1")
    if version not in {"1", "2"}:
        raise SpecError(f"unsupported spec_version: {version}")
    if version == "1":
        if require_contract or require_approved:
            raise SpecError("spec_version: 2 is required for new or meaningfully changed screen behavior")
        return {"spec_version": "1", "behavior_status": "UNSPECIFIED",
                "behavior_contract_status": "LEGACY_NOT_CHECKED"}
    status = values.get("behavior_status", "").upper()
    if status not in {"DRAFT", "APPROVED"}:
        raise SpecError("behavior_status must be DRAFT or APPROVED for spec_version: 2")
    if require_approved and status != "APPROVED":
        raise SpecError("behavior approval is required independently of design approval")
    approved = status == "APPROVED"
    body_start = text.find("\n---\n", 4) + len("\n---\n")
    groups = sections(contract_lines(text[body_start:]), 2)
    missing = set(BEHAVIOR_SECTIONS) - groups.keys()
    if missing:
        raise SpecError("missing behavior sections: " + ", ".join(sorted(missing)))
    features = index_rows(table_rows(groups[BEHAVIOR_SECTIONS[0]], FEATURE_COLUMNS, "features"), "기능 ID", "F")
    ui_lines = groups[BEHAVIOR_SECTIONS[1]]
    # An entirely non-visual screen may explicitly have no UI inventory.
    nonempty_ui = [line.strip() for line in ui_lines if line.strip()]
    ui = {} if nonempty_ui == ["NONE"] else index_rows(table_rows(ui_lines, UI_COLUMNS, "UI"), "UI ID", "UI")
    links: dict[str, set[str]] = {}
    for identity, row in features.items():
        for key in ("기능명", "사용자 목적 / 설명", "근거"):
            filled(row[key], f"{identity}/{key}", approved)
        if row["확정 상태"] not in FEATURE_STATES:
            raise SpecError(f"invalid feature state: {identity}")
        if approved and row["확정 상태"] != "CONFIRMED":
            raise SpecError(f"unconfirmed feature in approved behavior: {identity}")
        links[identity] = id_refs(row["연결 UI ID"], "UI", identity, allow_none=True)
        require_known(links[identity], ui, identity)
    reverse: dict[str, set[str]] = {}
    for identity, row in ui.items():
        for key in UI_COLUMNS[1:]:
            if key != "연결 기능 ID":
                filled(row[key], f"{identity}/{key}", approved)
        reverse[identity] = id_refs(row["연결 기능 ID"], "F", identity)
        require_known(reverse[identity], features, identity)
        expected = {fid for fid, ids in links.items() if identity in ids}
        if reverse[identity] != expected:
            raise SpecError(f"non-reciprocal feature/UI mapping: {identity}")
    validate_details(groups[BEHAVIOR_SECTIONS[2]], features, links, approved)
    criteria = index_rows(table_rows(groups[BEHAVIOR_SECTIONS[3]], AC_COLUMNS, "acceptance criteria"), "검증 ID", "AC")
    covered: set[str] = set()
    for identity, row in criteria.items():
        refs = id_refs(row["기능 ID"], "F", identity)
        require_known(refs, features, identity)
        for key in AC_COLUMNS[2:]:
            filled(row[key], f"{identity}/{key}", approved)
        covered.update(refs)
    if features.keys() - covered:
        raise SpecError("missing acceptance coverage: " + ", ".join(sorted(features.keys() - covered)))
    return {"spec_version": version, "behavior_status": status,
            "behavior_contract_status": "STRUCTURE_PASS"}


def validate(spec: Path, *, require_behavior_contract: bool = False,
             require_approved_behavior: bool = False) -> dict[str, str]:
    if not spec.is_file():
        raise SpecError(f"screen spec not found: {spec}")
    text = spec.read_text(encoding="utf-8")
    values = parse_frontmatter(text)
    required = ("screen", "status", "source", "reference", "fidelity", "viewport")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise SpecError("missing required frontmatter: " + ", ".join(missing))

    status = values["status"].upper()
    source = values["source"].upper()
    fidelity = values["fidelity"].upper()
    view_strategy = values.get("view_strategy", "").upper()
    if status not in ALLOWED_STATUS:
        raise SpecError(f"invalid status: {values['status']}")
    if source not in ALLOWED_SOURCE:
        raise SpecError(f"invalid source: {values['source']}")
    if fidelity not in ALLOWED_FIDELITY:
        raise SpecError(f"invalid fidelity: {values['fidelity']}")
    if view_strategy and view_strategy not in ALLOWED_VIEW_STRATEGY:
        raise SpecError(f"invalid view_strategy: {values['view_strategy']}")

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

    behavior = validate_behavior(text, values, require_contract=require_behavior_contract,
                                 require_approved=require_approved_behavior)
    return {
        **values,
        **behavior,
        "status": status,
        "source": source,
        "fidelity": fidelity,
        "view_strategy": view_strategy or "UNSPECIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hermes frontend screen reference package")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--require-behavior-contract", action="store_true",
                        help="Require the v2 body contract for new or meaningfully changed specs")
    parser.add_argument("--require-approved-behavior", action="store_true",
                        help="Require v2 and explicitly recorded behavior approval before implementation")
    args = parser.parse_args()
    try:
        result = validate(Path(args.spec).expanduser().resolve(),
                          require_behavior_contract=args.require_behavior_contract,
                          require_approved_behavior=args.require_approved_behavior)
    except (SpecError, OSError, UnicodeError) as exc:
        print(f"SCREEN_SPEC_STATUS=blocked\nERROR={exc}")
        return 2
    print("SCREEN_SPEC_STATUS=pass")
    print(f"SCREEN={result['screen']}")
    print(f"DESIGN_STATUS={result['status']}")
    print(f"DESIGN_SOURCE={result['source']}")
    print(f"DESIGN_FIDELITY={result['fidelity']}")
    print(f"VIEWPORT={result['viewport']}")
    print(f"VIEW_STRATEGY={result['view_strategy']}")
    print(f"SPEC_VERSION={result['spec_version']}")
    print(f"BEHAVIOR_STATUS={result['behavior_status']}")
    print(f"BEHAVIOR_CONTRACT_STATUS={result['behavior_contract_status']}")
    if result['behavior_contract_status'] == 'LEGACY_NOT_CHECKED':
        print("WARNING=Legacy spec has no behavior coverage check; upgrade when meaningfully changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
