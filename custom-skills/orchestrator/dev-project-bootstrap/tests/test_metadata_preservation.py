#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import tempfile


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_project.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bootstrap_project", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    m = load_module()

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        metadata = base / ".hermes" / "project.yaml"

        # v1-style managed metadata with a user resolver and legacy Jira block.
        metadata.parent.mkdir(parents=True)
        original_resolver = """resolver:
  aliases:
    - XCommServer
    - xcomm-server
  modules:
    - XCommServer
  files:
    - properties.cfg
  paths: []
"""
        original_jira = """jira:
  project_keys:
    - DSB
"""
        original_custom = """custom_policy:
  owner: user
  keep: true
"""
        metadata.write_text(
            """# managed-by: dev-project-bootstrap
version: 1

project:
  id: "xcomm-server-jre17"
  name: "XCommServer"
  repository: "/workspace/xcomm-server-jre17"

kanban:
  board: "xcomm-server-jre17"

git:
  default_base_branch: "dev"
  worktree_root: "/workspace/.worktrees/xcomm-server-jre17"

profiles:
  orchestrator: "orchestrator"
  coder: "coder"
  reviewer: "reviewer"

"""
            + original_resolver
            + "\n"
            + original_jira
            + "\n"
            + original_custom,
            encoding="utf-8",
        )

        existing = m.read_managed_metadata(metadata)
        created, extras = m.write_metadata(
            metadata,
            existing=existing,
            project_id="xcomm-server-jre17",
            name="XCommServer",
            repository="/workspace/xcomm-server-jre17",
            board="xcomm-server-jre17",
            base="dev",
            worktree_root="/workspace/.worktrees/xcomm-server-jre17",
            orchestrator="orchestrator",
            coder="coder",
            reviewer="reviewer",
        )

        text = metadata.read_text(encoding="utf-8")
        assert created is False
        assert "version: 2" in text
        assert original_resolver.rstrip() in text
        assert original_jira.rstrip() in text
        assert original_custom.rstrip() in text
        assert "jira" in extras
        assert "custom_policy" in extras

        # A second run must still preserve user resolver exactly.
        first_resolver = m.section_map(text)["resolver"]
        existing2 = m.read_managed_metadata(metadata)
        created2, _ = m.write_metadata(
            metadata,
            existing=existing2,
            project_id="xcomm-server-jre17",
            name="XCommServer",
            repository="/workspace/xcomm-server-jre17",
            board="xcomm-server-jre17",
            base="dev",
            worktree_root="/workspace/.worktrees/xcomm-server-jre17",
            orchestrator="orchestrator",
            coder="coder",
            reviewer="reviewer",
        )
        second_resolver = m.section_map(metadata.read_text(encoding="utf-8"))["resolver"]
        assert created2 is False
        assert first_resolver == second_resolver

        # New managed metadata gets an empty resolver skeleton and no Jira section.
        new_meta = base / "new" / ".hermes" / "project.yaml"
        existing_new = m.read_managed_metadata(new_meta)
        created3, extras3 = m.write_metadata(
            new_meta,
            existing=existing_new,
            project_id="new-project",
            name="new-project",
            repository="/workspace/new-project",
            board="new-project",
            base="dev",
            worktree_root="/workspace/.worktrees/new-project",
            orchestrator="orchestrator",
            coder="coder",
            reviewer="reviewer",
        )
        new_text = new_meta.read_text(encoding="utf-8")
        assert created3 is True
        assert extras3 == []
        assert "resolver:\n  aliases: []\n  modules: []\n  files: []\n  paths: []" in new_text
        assert "\njira:" not in new_text
        assert "\nwork_sources:" not in new_text

        print("TEST_STATUS=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
