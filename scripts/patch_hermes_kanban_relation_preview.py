#!/usr/bin/env python3
"""Patch Hermes Kanban dashboard to show expandable parent/child relation previews.

The DevKit keeps the native task_links table as the authoritative relationship.
This patch only enriches the board payload and renders a compact relation preview;
it never duplicates or moves cards.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER_API = "DEVKIT_KANBAN_RELATION_PREVIEW_API_V1"
MARKER_UI = "DEVKIT_KANBAN_RELATION_PREVIEW_UI_V1"
MARKER_CSS = "DEVKIT_KANBAN_RELATION_PREVIEW_CSS_V1"

API_ANCHOR = '''        progress: dict[str, dict[str, int]] = {}  # per parent: children done / total, rendered as "N/M"
        for row in conn.execute(
            "SELECT l.parent_id AS pid, t.status AS cstatus FROM task_links l JOIN tasks t ON t.id = l.child_id").fetchall():
            p = progress.setdefault(row["pid"], {"done": 0, "total": 0})
            p["total"] += 1
            p["done"] += row["cstatus"] == "done"
'''

API_REPLACEMENT = API_ANCHOR + f'''        # {MARKER_API}: one aggregate relationship query for compact card previews.
        # Native task_links stays authoritative; this is display-only metadata.
        relation_preview: dict[str, dict[str, list[dict[str, str]]]] = {{}}
        for row in conn.execute(
            """
            SELECT l.parent_id, p.title AS parent_title, p.status AS parent_status,
                   l.child_id, c.title AS child_title, c.status AS child_status
              FROM task_links l
              JOIN tasks p ON p.id = l.parent_id
              JOIN tasks c ON c.id = l.child_id
             ORDER BY l.parent_id, l.child_id
            """
        ).fetchall():
            relation_preview.setdefault(row["child_id"], {{"parents": [], "children": []}})["parents"].append({{
                "id": row["parent_id"], "title": row["parent_title"], "status": row["parent_status"]
            }})
            relation_preview.setdefault(row["parent_id"], {{"parents": [], "children": []}})["children"].append({{
                "id": row["child_id"], "title": row["child_title"], "status": row["child_status"]
            }})
'''

API_ASSIGN_ANCHOR = '''            d["progress"] = progress.get(t.id)  # None when the task has no children
            _attach_diagnostics(d, diagnostics_per_task.get(t.id))
'''

API_ASSIGN_REPLACEMENT = f'''            d["progress"] = progress.get(t.id)  # None when the task has no children
            d["relation_preview"] = relation_preview.get(t.id)  # {MARKER_API}
            _attach_diagnostics(d, diagnostics_per_task.get(t.id))
'''

UI_HOOK_ANCHOR = '''    const t = props.task;
    const cardRef = useRef(null);
'''

UI_HOOK_REPLACEMENT = f'''    const t = props.task;
    const cardRef = useRef(null);
    const [relationsExpanded, setRelationsExpanded] = useState(false); // {MARKER_UI}
'''

UI_RENDER_ANCHOR = '''          h("div", { className: "hermes-kanban-card-title" },
            t.title || tx(i18n, "untitled", "(untitled)")),
          h("div", { className: "hermes-kanban-card-row hermes-kanban-card-meta" },
'''

UI_RENDER_REPLACEMENT = f'''          h("div", {{ className: "hermes-kanban-card-title" }},
            t.title || tx(i18n, "untitled", "(untitled)")),
          t.relation_preview && ((t.relation_preview.parents || []).length > 0 || (t.relation_preview.children || []).length > 0)
            ? h("div", {{ className: "hermes-kanban-relation", "data-devkit": "{MARKER_UI}" }},
                (t.relation_preview.parents || []).length > 0
                  ? h("button", {{
                      type: "button",
                      className: "hermes-kanban-relation-toggle hermes-kanban-relation-toggle--child",
                      title: "부모 작업 관계 보기",
                      onClick: function (e) {{ e.preventDefault(); e.stopPropagation(); setRelationsExpanded(function (v) {{ return !v; }}); }},
                    }},
                      h("span", {{ className: "hermes-kanban-relation-caret" }}, relationsExpanded ? "▾" : "▸"),
                      " ↳ 부모 ",
                      (t.relation_preview.parents || []).map(function (r) {{ return r.id; }}).join(", "),
                    )
                  : h("button", {{
                      type: "button",
                      className: "hermes-kanban-relation-toggle hermes-kanban-relation-toggle--parent",
                      title: "하위 작업 관계 보기",
                      onClick: function (e) {{ e.preventDefault(); e.stopPropagation(); setRelationsExpanded(function (v) {{ return !v; }}); }},
                    }},
                      h("span", {{ className: "hermes-kanban-relation-caret" }}, relationsExpanded ? "▾" : "▸"),
                      " 하위 작업 ",
                      (t.relation_preview.children || []).length,
                      t.progress && t.progress.total > 0 ? " · 완료 " + t.progress.done + "/" + t.progress.total : "",
                    ),
                relationsExpanded
                  ? h("div", {{ className: "hermes-kanban-relation-details" }},
                      (t.relation_preview.parents || []).map(function (r) {{
                        return h("div", {{ key: "p-" + r.id, className: "hermes-kanban-relation-item" }},
                          h("span", {{ className: "hermes-kanban-relation-status" }}, r.status),
                          h("span", {{ className: "hermes-kanban-relation-id" }}, r.id),
                          h("span", {{ className: "hermes-kanban-relation-title", title: r.title || r.id }}, r.title || r.id),
                        );
                      }}),
                      (t.relation_preview.children || []).map(function (r) {{
                        return h("div", {{ key: "c-" + r.id, className: "hermes-kanban-relation-item" }},
                          h("span", {{ className: "hermes-kanban-relation-status" }}, r.status),
                          h("span", {{ className: "hermes-kanban-relation-id" }}, r.id),
                          h("span", {{ className: "hermes-kanban-relation-title", title: r.title || r.id }}, r.title || r.id),
                        );
                      }}),
                    )
                  : null,
              )
            : null,
          h("div", {{ className: "hermes-kanban-card-row hermes-kanban-card-meta" }},
'''

CSS_BLOCK = f'''
/* {MARKER_CSS}: relationship preview for DevKit parent/child tracking cards. */
.hermes-kanban-relation {{
  margin-top: 2px;
  border-top: 1px dashed color-mix(in srgb, currentColor 16%, transparent);
  padding-top: 4px;
  min-width: 0;
}}
.hermes-kanban-relation-toggle {{
  display: flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  gap: 2px;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font-size: 10px;
  line-height: 1.35;
  color: var(--muted-foreground);
}}
.hermes-kanban-relation-toggle:hover {{
  color: var(--foreground);
}}
.hermes-kanban-relation-caret {{
  width: 10px;
  flex: 0 0 10px;
}}
.hermes-kanban-relation-details {{
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 4px;
  padding-left: 12px;
}}
.hermes-kanban-relation-item {{
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: 10px;
  line-height: 1.35;
  color: var(--muted-foreground);
}}
.hermes-kanban-relation-status {{
  border: 1px solid color-mix(in srgb, currentColor 24%, transparent);
  border-radius: 999px;
  padding: 0 4px;
  font-size: 9px;
}}
.hermes-kanban-relation-id {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  opacity: 0.8;
}}
.hermes-kanban-relation-title {{
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
'''


def replace_once(text: str, anchor: str, replacement: str, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected anchor exactly once, found {count}")
    return text.replace(anchor, replacement, 1)


def patch_api(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER_API in text:
        return
    text = replace_once(text, API_ANCHOR, API_REPLACEMENT, "plugin_api relation aggregate")
    text = replace_once(text, API_ASSIGN_ANCHOR, API_ASSIGN_REPLACEMENT, "plugin_api relation assignment")
    path.write_text(text, encoding="utf-8")


def patch_ui(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER_UI in text:
        return
    text = replace_once(text, UI_HOOK_ANCHOR, UI_HOOK_REPLACEMENT, "dashboard TaskCard state")
    text = replace_once(text, UI_RENDER_ANCHOR, UI_RENDER_REPLACEMENT, "dashboard TaskCard relation preview")
    path.write_text(text, encoding="utf-8")


def patch_css(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER_CSS in text:
        return
    path.write_text(text.rstrip() + "\n\n" + CSS_BLOCK.lstrip(), encoding="utf-8")


def check(paths: tuple[Path, Path, Path]) -> None:
    api, ui, css = (p.read_text(encoding="utf-8") for p in paths)
    for marker, text, label in (
        (MARKER_API, api, "plugin_api.py"),
        (MARKER_UI, ui, "dist/index.js"),
        (MARKER_CSS, css, "dist/style.css"),
    ):
        if marker not in text:
            raise RuntimeError(f"{label}: patch marker missing")


def self_test() -> None:
    api = API_ANCHOR + "\n" + API_ASSIGN_ANCHOR
    ui = "function TaskCard(props) {\n" + UI_HOOK_ANCHOR + "\nreturn h(Card, null,\n" + UI_RENDER_ANCHOR + "\n);\n}"
    patched_api = replace_once(api, API_ANCHOR, API_REPLACEMENT, "selftest api aggregate")
    patched_api = replace_once(patched_api, API_ASSIGN_ANCHOR, API_ASSIGN_REPLACEMENT, "selftest api assignment")
    patched_ui = replace_once(ui, UI_HOOK_ANCHOR, UI_HOOK_REPLACEMENT, "selftest ui state")
    patched_ui = replace_once(patched_ui, UI_RENDER_ANCHOR, UI_RENDER_REPLACEMENT, "selftest ui render")
    assert MARKER_API in patched_api
    assert "relation_preview" in patched_api
    assert MARKER_UI in patched_ui
    assert "relationsExpanded" in patched_ui
    assert "↳ 부모 " in patched_ui
    assert "하위 작업 " in patched_ui
    assert MARKER_CSS in CSS_BLOCK


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--hermes-root", default="/opt/hermes")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    root = Path(args.hermes_root)
    paths = (
        root / "plugins/kanban/dashboard/plugin_api.py",
        root / "plugins/kanban/dashboard/dist/index.js",
        root / "plugins/kanban/dashboard/dist/style.css",
    )
    for p in paths:
        if not p.is_file():
            raise SystemExit(f"missing Hermes dashboard file: {p}")

    if not args.check_only:
        patch_api(paths[0])
        patch_ui(paths[1])
        patch_css(paths[2])
    check(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
