#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import tempfile
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_resolve.py"


def write_project(repo: Path, project_id: str, modules=None, aliases=None, files=None):
    (repo / ".hermes").mkdir(parents=True, exist_ok=True)
    modules = modules or []
    aliases = aliases or []
    files = files or []

    lines = [
        "project:",
        f"  id: {project_id}",
        f"  name: {project_id}",
        f"  repository: {repo}",
        "",
        "resolver:",
        "  aliases:",
    ]
    lines += [f"    - {x}" for x in aliases]
    lines += ["  modules:"]
    lines += [f"    - {x}" for x in modules]
    lines += ["  files:"]
    lines += [f"    - {x}" for x in files]
    lines += [
        "",
        "work_sources:",
        "  jira:",
        "    project_keys:",
        "      - DSB",
    ]

    (repo / ".hermes" / "project.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(script, work_item, workspace, output):
    return subprocess.run(
        [
            sys.executable, str(script),
            "--work-item", str(work_item),
            "--workspace-root", str(workspace),
            "--output-dir", str(output),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ws = base / "workspace"
        out = base / "out"
        ws.mkdir()

        # Managed projects.
        server = ws / "server"
        xorg = ws / "xorg-sync"
        server.mkdir()
        xorg.mkdir()

        write_project(server, "server", modules=["scApi", "XCommServer"])
        write_project(xorg, "xorg-sync", modules=["XOrgSyncTool"])

        # Unmanaged repo-like directory with matching content.
        unmanaged = ws / "unmanaged-sso"
        unmanaged.mkdir()
        (unmanaged / "XCommServer.txt").write_text("XCommServer", encoding="utf-8")

        # Worktree with metadata must be ignored.
        wt = ws / ".worktrees" / "fake"
        (wt / ".hermes").mkdir(parents=True)
        (wt / ".hermes" / "project.yaml").write_text(
            "project:\n  id: fake\n  repository: /workspace/.worktrees/fake\n"
            "resolver:\n  modules:\n    - XCommServer\n",
            encoding="utf-8",
        )

        item = {
            "version": 1,
            "source": {"type": "jira", "ref": "DSB-39"},
            "work": {
                "id": "DSB-39",
                "title": "DB 접속정보 암호화 가이드",
                "description": "scApi, XCommServer, XOrgSyncTool 확인",
                "acceptance_criteria": [],
                "comments": [],
                "labels": [],
                "components": [],
            },
            "project_hints": {"jira_project_key": "DSB"},
        }

        work_item = base / "DSB-39.json"
        work_item.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

        proc = run(SCRIPT, work_item, ws, out)
        print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        assert proc.returncode == 0

        result = json.loads((out / "DSB-39.json").read_text(encoding="utf-8"))
        assert result["status"] == "RESOLVED_MULTI", result
        assert result["managed_projects_scanned"] == 2, result
        resolved = {Path(x["repository"]).name for x in result["resolved_projects"]}
        assert resolved == {"server", "xorg-sync"}, resolved
        assert all("unmanaged-sso" not in x["repository"] for x in result["candidates"])
        assert all(".worktrees" not in x["repository"] for x in result["candidates"])
        assert result["search_policy"]["repository_content_scanned"] is False

        # Jira key alone must not resolve.
        item["work"]["description"] = "대신저축은행 고객 요청"
        work_item.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
        proc2 = run(SCRIPT, work_item, ws, out)
        print(proc2.stdout)
        assert proc2.returncode == 0
        result2 = json.loads((out / "DSB-39.json").read_text(encoding="utf-8"))
        assert result2["status"] == "BLOCKED", result2

        print("TEST_STATUS=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
