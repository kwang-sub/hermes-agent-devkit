#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pr_publish_lib import (
    PublishError,
    changed_rows,
    current_branch,
    diff_stat,
    emit,
    ensure_gh,
    head_sha,
    list_open_prs,
    publish_fingerprint,
    remote_url,
    repo_root,
    resolve_base_branch,
    resolve_workspace,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Read-only preflight for dev-pr-publish")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base-branch")
    value.add_argument("--include", action="append", default=[])
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        root = repo_root(workspace)
        branch = current_branch(root)
        remote = args.remote
        url = remote_url(root, remote)
        ensure_gh(root)
        base = resolve_base_branch(root, remote, args.base_branch)
        rows = changed_rows(root, args.include)

        if not rows:
            raise PublishError("no publishable working-tree changes were found")
        if base and base == branch:
            raise PublishError(f"head branch must differ from base branch: {branch}")

        fingerprint = publish_fingerprint(root, args.include)
        open_prs = list_open_prs(root, base=base, head=branch) if base else []

        emit("STATUS", "ready" if base else "base-unresolved")
        emit("REPO_ROOT", root)
        emit("WORKSPACE", workspace)
        emit("BRANCH", branch)
        emit("BASE_BRANCH", base)
        emit("HEAD_SHA", head_sha(root))
        emit("REMOTE", remote)
        emit("REMOTE_URL", url)
        emit("PUBLISH_FINGERPRINT", fingerprint)
        emit("CHANGED_COUNT", len(rows))
        emit("OPEN_PR_COUNT", len(open_prs))
        if open_prs:
            emit("OPEN_PR_URL", open_prs[0].get("url", ""))

        for status, path, original in rows:
            display = f"{status} {path}"
            if original:
                display += f" <- {original}"
            emit("CHANGED_FILE", display)

        print("DIFF_STAT_BEGIN")
        print(diff_stat(root, args.include))
        print("DIFF_STAT_END")
        return 0
    except PublishError as exc:
        print(f"STATUS=blocked\nERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
