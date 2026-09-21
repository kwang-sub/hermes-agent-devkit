#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import project_builds
import dev_environment_preflight as shared


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the Hermes Java toolchain for one executable workspace without bootstrapping it as a managed project."
    )
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        print(f"ERROR=workspace not found: {workspace}")
        return 2

    try:
        projects = project_builds.discover_build_projects(workspace)
        toolchain_file, warnings = project_builds.configure_java_toolchain(
            workspace,
            projects,
        )
    except shared.PreflightError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"WORKSPACE={workspace}")
    print(f"BUILD_PROJECT_COUNT={len(projects)}")
    print(f"TOOLCHAIN_FILE={toolchain_file}")
    for index, warning in enumerate(warnings, start=1):
        print(f"WARNING_{index}={warning}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
