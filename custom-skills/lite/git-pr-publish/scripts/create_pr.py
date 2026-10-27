#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from pr_publish_lib import (
    PublishError,
    current_branch,
    emit,
    head_sha,
    list_open_prs,
    remote_head_sha,
    repo_root,
    resolve_workspace,
    run,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Create an approved GitHub pull request")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base", required=True)
    value.add_argument("--head", required=True)
    value.add_argument("--title", required=True)
    value.add_argument("--body", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        root = repo_root(workspace)
        branch = current_branch(root)
        if branch != args.head:
            raise PublishError(f"head branch mismatch before PR create: expected {args.head}, got {branch}")
        if args.base == args.head:
            raise PublishError("PR base and head must differ")
        if not args.title.strip():
            raise PublishError("PR title is empty")
        if not args.body.strip():
            raise PublishError("PR body is empty")

        local = head_sha(root)
        remote = remote_head_sha(root, args.remote, args.head)
        if remote is None:
            raise PublishError(f"remote head does not exist: {args.remote}/{args.head}")
        if remote != local:
            raise PublishError(
                f"remote head changed after PR preview: local={local} remote={remote}"
            )

        existing = list_open_prs(root, base=args.base, head=args.head)
        if existing:
            emit("STATUS", "existing-pr")
            emit("PR_NUMBER", existing[0].get("number", ""))
            emit("PR_URL", existing[0].get("url", ""))
            emit("PR_TITLE", existing[0].get("title", ""))
            return 0

        created = run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                args.base,
                "--head",
                args.head,
                "--title",
                args.title,
                "--body",
                args.body,
            ],
            cwd=root,
        )
        url = created.stdout.strip().splitlines()[-1] if created.stdout.strip() else ""
        if not url.startswith("http"):
            raise PublishError(f"gh pr create did not return a PR URL: {created.stdout.strip()}")

        emit("STATUS", "created")
        emit("PR_URL", url)
        emit("BASE", args.base)
        emit("HEAD", args.head)
        return 0
    except PublishError as exc:
        emit("STATUS", "blocked")
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
