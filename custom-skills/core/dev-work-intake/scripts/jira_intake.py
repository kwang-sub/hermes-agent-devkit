#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import ssl
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_ENV_FILE = "/opt/data/profiles/orchestrator/.env"


def load_env_file(path: Path) -> bool:
    """Load an optional dotenv fallback without third-party dependencies.

    Existing process environment variables win over .env values.
    Returns True only when the file existed and was loaded.
    """
    if not path.is_file():
        return False

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise IntakeError(f"invalid .env line {line_no}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise IntakeError(f"invalid .env key on line {line_no}: {key}")

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            quote_char = value[0]
            value = value[1:-1]
            if quote_char == '"':
                value = (
                    value.replace(r"\n", "\n")
                    .replace(r"\t", "\t")
                    .replace(r'\"', '"')
                    .replace(r"\\", "\\")
                )
        else:
            # Allow inline comments only when preceded by whitespace.
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()

        os.environ.setdefault(key, value)

    return True


def resolve_env_file() -> Path:
    # JIRA_ENV_FILE itself can be supplied by the container/runtime.
    return Path(os.environ.get("JIRA_ENV_FILE", DEFAULT_ENV_FILE))


class IntakeError(RuntimeError):
    pass


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def required(name: str) -> str:
    value = env(name)
    if value is None:
        raise IntakeError(f"required environment variable is missing: {name}")
    return value


def parse_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise IntakeError(f"invalid boolean value: {value}")


def csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class JiraConfig:
    def __init__(self) -> None:
        self.deployment = "cloud"
        self.env_file = resolve_env_file()

        required_before = {
            name: os.environ.get(name)
            for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
        }
        self.env_file_loaded = load_env_file(self.env_file)

        self.base_url = required("JIRA_BASE_URL").rstrip("/")
        self.email = required("JIRA_EMAIL")
        self.api_token = required("JIRA_API_TOKEN")

        self.api_version = env("JIRA_API_VERSION", "3")
        if not re.fullmatch(r"\d+", self.api_version or ""):
            raise IntakeError("JIRA_API_VERSION must be numeric")

        self.verify_ssl = parse_bool(env("JIRA_VERIFY_SSL", "true"))
        self.ca_file = env("JIRA_CA_FILE")

        self.acceptance_names = {
            item.casefold()
            for item in csv_values(
                env(
                    "JIRA_ACCEPTANCE_CRITERIA_FIELDS",
                    "Acceptance Criteria,Acceptance criteria,Acceptance Criterion,AC,완료 조건,인수 조건",
                )
            )
        }

        self.include_names = {
            item.casefold()
            for item in csv_values(env("JIRA_INCLUDE_FIELD_NAMES"))
        }

        self.work_item_dir = Path(
            env("HERMES_WORK_ITEM_DIR", "/opt/data/work-items") or "/opt/data/work-items"
        )

        self.headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "Hermes-dev-work-intake/0.1.2",
        }

        encoded = base64.b64encode(
            f"{self.email}:{self.api_token}".encode("utf-8")
        ).decode("ascii")
        self.headers["Authorization"] = f"Basic {encoded}"

    @property
    def api_root(self) -> str:
        return f"{self.base_url}/rest/api/{self.api_version}"

    def ssl_context(self) -> ssl.SSLContext:
        if not self.verify_ssl:
            return ssl._create_unverified_context()
        if self.ca_file:
            return ssl.create_default_context(cafile=self.ca_file)
        return ssl.create_default_context()


def http_json(config: JiraConfig, path: str, query: dict[str, Any] | None = None) -> Any:
    url = f"{config.api_root}/{path.lstrip('/')}"
    if query:
        clean_query: list[tuple[str, str]] = []
        for key, value in query.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    clean_query.append((key, str(item)))
            else:
                clean_query.append((key, str(value)))
        if clean_query:
            url += "?" + urlencode(clean_query)

    request = Request(url, headers=config.headers, method="GET")

    try:
        with urlopen(request, context=config.ssl_context(), timeout=30) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if len(detail) > 1000:
            detail = detail[:1000] + "..."
        raise IntakeError(
            f"Jira HTTP {exc.code} for {url}"
            + (f": {detail}" if detail else "")
        ) from exc
    except URLError as exc:
        raise IntakeError(f"cannot connect to Jira at {url}: {exc.reason}") from exc

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntakeError(f"Jira returned invalid JSON for {url}") from exc


def flatten_adf(node: Any, level: int = 0) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float, bool)):
        return str(node)
    if isinstance(node, list):
        return "".join(flatten_adf(item, level) for item in node)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")

    if node_type == "text":
        return str(node.get("text", ""))

    if node_type == "hardBreak":
        return "\n"

    if node_type == "mention":
        attrs = node.get("attrs") or {}
        return str(attrs.get("text") or attrs.get("displayName") or "@user")

    if node_type == "emoji":
        attrs = node.get("attrs") or {}
        return str(attrs.get("text") or attrs.get("shortName") or "")

    if node_type == "inlineCard":
        attrs = node.get("attrs") or {}
        return str(attrs.get("url") or "")

    content = node.get("content") or []

    if node_type in {"doc"}:
        return normalize_text("".join(flatten_adf(item, level) for item in content))

    if node_type in {"paragraph", "heading", "blockquote", "codeBlock"}:
        text = "".join(flatten_adf(item, level) for item in content).strip()
        if not text:
            return "\n"
        if node_type == "blockquote":
            text = "\n".join(f"> {line}" for line in text.splitlines())
        return text + "\n"

    if node_type in {"bulletList", "orderedList"}:
        lines: list[str] = []
        ordered = node_type == "orderedList"
        for index, item in enumerate(content, start=1):
            body = flatten_adf(item, level + 1).strip()
            if not body:
                continue
            prefix = f"{index}. " if ordered else "- "
            item_lines = body.splitlines()
            lines.append(prefix + item_lines[0])
            lines.extend("  " + line for line in item_lines[1:])
        return "\n".join(lines) + ("\n" if lines else "")

    if node_type == "listItem":
        return "".join(flatten_adf(item, level) for item in content).strip()

    return "".join(flatten_adf(item, level) for item in content)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and value.get("type") == "doc":
        text = flatten_adf(value)
    elif isinstance(value, str):
        text = value
    elif isinstance(value, list):
        text = "\n".join(
            part for part in (normalize_text(item) for item in value) if part
        )
    elif isinstance(value, dict):
        # Common Jira option/user/object shapes.
        for key in ("displayName", "name", "value", "summary", "key"):
            if value.get(key) is not None:
                return normalize_text(value[key])
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def person_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("displayName", "name", "emailAddress", "accountId"):
        item = value.get(key)
        if item:
            return str(item)
    return None


def object_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("name", "value", "displayName", "key", "id"):
        item = value.get(key)
        if item is not None:
            return str(item)
    return None


def split_criteria(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        return [text]

    criteria: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^(?:[-*•]\s+|\d+[.)]\s+)", "", line).strip()
        if cleaned:
            criteria.append(cleaned)
    return criteria or [text]


def fetch_comments(config: JiraConfig, issue_key: str) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    start_at = 0
    max_results = 100

    while True:
        payload = http_json(
            config,
            f"issue/{quote(issue_key, safe='')}/comment",
            {
                "startAt": start_at,
                "maxResults": max_results,
                "orderBy": "created",
            },
        )

        page = payload.get("comments") if isinstance(payload, dict) else None
        if not isinstance(page, list):
            raise IntakeError("unexpected Jira comments response schema")

        for item in page:
            if not isinstance(item, dict):
                continue
            body = normalize_text(item.get("body"))
            comments.append(
                {
                    "id": str(item.get("id", "")),
                    "author": person_name(item.get("author")),
                    "created": item.get("created"),
                    "updated": item.get("updated"),
                    "body": body,
                }
            )

        total = payload.get("total", len(comments))
        try:
            total_int = int(total)
        except (TypeError, ValueError):
            total_int = len(comments)

        start_at += len(page)
        if not page or start_at >= total_int:
            break

    return comments


def issue_link_summary(link: dict[str, Any]) -> dict[str, Any]:
    link_type = link.get("type") if isinstance(link.get("type"), dict) else {}
    if isinstance(link.get("outwardIssue"), dict):
        issue = link["outwardIssue"]
        direction = "outward"
        relation = link_type.get("outward")
    elif isinstance(link.get("inwardIssue"), dict):
        issue = link["inwardIssue"]
        direction = "inward"
        relation = link_type.get("inward")
    else:
        issue = {}
        direction = "unknown"
        relation = link_type.get("name")

    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    return {
        "direction": direction,
        "relation": relation,
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": object_name(fields.get("status")),
    }


def field_by_name(
    fields: dict[str, Any],
    names: dict[str, str],
    wanted_casefold: set[str],
) -> list[tuple[str, str, Any]]:
    result: list[tuple[str, str, Any]] = []
    for field_id, value in fields.items():
        display = names.get(field_id)
        if not display:
            continue
        if display.casefold() in wanted_casefold:
            result.append((field_id, display, value))
    return result


def make_markdown(item: dict[str, Any]) -> str:
    source = item["source"]
    work = item["work"]
    jira = item["jira"]
    hints = item["project_hints"]

    lines: list[str] = [
        f"# Work Item: {work['id']}",
        "",
        "## Source",
        f"- Type: `{source['type']}`",
        f"- Deployment: `{source['deployment']}`",
        f"- Reference: `{source['ref']}`",
        f"- URL: {source['url']}",
        "",
        "## Title",
        work["title"] or "(empty)",
        "",
        "## Description",
        work["description"] or "(empty)",
        "",
        "## Acceptance Criteria",
    ]

    if work["acceptance_criteria"]:
        lines.extend(f"- {criterion}" for criterion in work["acceptance_criteria"])
    else:
        lines.append("- (none explicitly provided)")

    lines += [
        "",
        "## Jira Metadata",
        f"- Project Key: `{hints['jira_project_key']}`",
        f"- Issue Type: {jira.get('issue_type') or '-'}",
        f"- Status: {jira.get('status') or '-'}",
        f"- Priority: {jira.get('priority') or '-'}",
        f"- Assignee: {jira.get('assignee') or '-'}",
        f"- Reporter: {jira.get('reporter') or '-'}",
        f"- Components: {', '.join(work['components']) if work['components'] else '-'}",
        f"- Labels: {', '.join(work['labels']) if work['labels'] else '-'}",
        "",
        "## Comments",
    ]

    if work["comments"]:
        for comment in work["comments"]:
            lines += [
                "",
                f"### {comment.get('author') or 'Unknown'} — {comment.get('created') or ''}",
                comment.get("body") or "(empty)",
            ]
    else:
        lines.append("- (none visible)")

    lines += ["", "## Dependencies / Issue Links"]
    if work["dependencies"]:
        for link in work["dependencies"]:
            lines.append(
                f"- {link.get('relation') or 'linked'}: "
                f"{link.get('key') or '-'} — {link.get('summary') or ''}"
            )
    else:
        lines.append("- (none)")

    if work["custom_fields"]:
        lines += ["", "## Included Custom Fields"]
        for key, value in work["custom_fields"].items():
            lines += ["", f"### {key}", value or "(empty)"]

    lines += [
        "",
        "## Project Hints",
        f"- Jira Project Key: `{hints['jira_project_key']}`",
        f"- Components: {', '.join(hints['components']) if hints['components'] else '-'}",
        f"- Labels: {', '.join(hints['labels']) if hints['labels'] else '-'}",
        "",
        "> This file is a normalized read-only intake artifact. "
        "Do not treat inferred implementation details as source requirements.",
        "",
    ]
    return "\n".join(lines)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def check_connection(config: JiraConfig) -> int:
    payload = http_json(config, "myself")
    user = person_name(payload) or "(unknown)"
    print("STATUS=connected")
    print(f"DEPLOYMENT={config.deployment}")
    print(f"API_VERSION={config.api_version}")
    print(f"USER={user}")
    print(f"BASE_URL={config.base_url}")
    print(f"CONFIG_SOURCE={'environment+fallback-file' if config.env_file_loaded else 'environment'}")
    print(f"ENV_FILE={config.env_file}")
    print(f"ENV_FILE_LOADED={'true' if config.env_file_loaded else 'false'}")
    return 0


def normalize_issue(config: JiraConfig, issue_key: str) -> int:
    issue_key = issue_key.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*-\d+", issue_key):
        raise IntakeError(f"invalid Jira issue key: {issue_key}")

    issue = http_json(
        config,
        f"issue/{quote(issue_key, safe='')}",
        {
            "fields": "*all",
            "expand": "names",
        },
    )
    if not isinstance(issue, dict):
        raise IntakeError("unexpected Jira issue response schema")

    fields = issue.get("fields")
    if not isinstance(fields, dict):
        raise IntakeError("Jira issue response has no fields object")

    names = issue.get("names")
    if not isinstance(names, dict):
        names = {}

    comments = fetch_comments(config, issue_key)

    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    project_key = str(project.get("key") or issue_key.split("-", 1)[0])

    components = [
        name
        for name in (object_name(item) for item in fields.get("components") or [])
        if name
    ]
    labels = [str(item) for item in (fields.get("labels") or []) if item is not None]

    acceptance: list[str] = []
    for _, _, value in field_by_name(fields, names, config.acceptance_names):
        acceptance.extend(split_criteria(normalize_text(value)))

    # Deduplicate while preserving order.
    acceptance = list(dict.fromkeys(item for item in acceptance if item))

    custom_fields: dict[str, str] = {}
    for _, display, value in field_by_name(fields, names, config.include_names):
        normalized = normalize_text(value)
        if normalized:
            custom_fields[display] = normalized

    issue_links = [
        issue_link_summary(link)
        for link in (fields.get("issuelinks") or [])
        if isinstance(link, dict)
    ]

    subtasks = []
    for task in fields.get("subtasks") or []:
        if not isinstance(task, dict):
            continue
        task_fields = task.get("fields") if isinstance(task.get("fields"), dict) else {}
        subtasks.append(
            {
                "key": task.get("key"),
                "summary": task_fields.get("summary"),
                "status": object_name(task_fields.get("status")),
            }
        )

    parent = None
    if isinstance(fields.get("parent"), dict):
        parent_fields = (
            fields["parent"].get("fields")
            if isinstance(fields["parent"].get("fields"), dict)
            else {}
        )
        parent = {
            "key": fields["parent"].get("key"),
            "summary": parent_fields.get("summary"),
        }

    item: dict[str, Any] = {
        "version": 1,
        "source": {
            "type": "jira",
            "deployment": config.deployment,
            "ref": issue_key,
            "url": f"{config.base_url}/browse/{quote(issue_key, safe='')}",
        },
        "work": {
            "id": issue_key,
            "title": normalize_text(fields.get("summary")),
            "description": normalize_text(fields.get("description")),
            "acceptance_criteria": acceptance,
            "comments": comments,
            "labels": labels,
            "components": components,
            "dependencies": issue_links,
            "constraints": [],
            "custom_fields": custom_fields,
        },
        "project_hints": {
            "jira_project_key": project_key,
            "components": components,
            "labels": labels,
        },
        "jira": {
            "id": issue.get("id"),
            "status": object_name(fields.get("status")),
            "issue_type": object_name(fields.get("issuetype")),
            "priority": object_name(fields.get("priority")),
            "assignee": person_name(fields.get("assignee")),
            "reporter": person_name(fields.get("reporter")),
            "parent": parent,
            "subtasks": subtasks,
            "issue_links": issue_links,
        },
    }

    output_dir = config.work_item_dir / "jira"
    json_path = output_dir / f"{issue_key}.json"
    md_path = output_dir / f"{issue_key}.md"

    atomic_write(
        json_path,
        json.dumps(item, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write(md_path, make_markdown(item))

    print("SOURCE=jira")
    print(f"ISSUE_KEY={issue_key}")
    print(f"PROJECT_KEY={project_key}")
    print(f"TITLE={item['work']['title']}")
    print(f"JSON_FILE={json_path}")
    print(f"MARKDOWN_FILE={md_path}")
    print("STATUS=normalized")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Jira intake adapter for Hermes dev-work-intake."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Validate Jira connectivity/authentication")
    mode.add_argument("--issue", help="Fetch and normalize a Jira issue key")
    args = parser.parse_args()

    config = JiraConfig()

    if args.check:
        return check_connection(config)
    if args.issue:
        return normalize_issue(config, args.issue)

    raise IntakeError("no operation selected")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IntakeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
