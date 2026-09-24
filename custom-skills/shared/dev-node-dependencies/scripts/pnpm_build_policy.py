#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from node_workspace import WorkspaceError, resolve_cwd, resolve_package_root


EXACT_REGISTRY_MATCHER = re.compile(
    r"^(?:@[^/@\s]+/[^@\s]+|[^@/\s]+)@"
    r"\d+\.\d+\.\d+"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)
PLACEHOLDER_TEXT = "set this to true or false"


class BuildPolicyError(RuntimeError):
    def __init__(self, message: str, blocker_class: str = "PNPM_BUILD_POLICY_INVALID"):
        super().__init__(message)
        self.blocker_class = blocker_class


def _run_config_get(pnpm_binary: str, package_root: Path, key: str):
    result = subprocess.run(
        [pnpm_binary, "config", "get", "--json", key],
        cwd=package_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise BuildPolicyError(
            f"pnpm config get failed for {key}: {detail or 'unknown error'}",
            blocker_class="PNPM_BUILD_POLICY_READ_FAILED",
        )
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BuildPolicyError(
            f"pnpm config get returned invalid JSON for {key}: {raw}",
            blocker_class="PNPM_BUILD_POLICY_READ_FAILED",
        ) from exc


def is_exact_registry_matcher(value: str) -> bool:
    return bool(EXACT_REGISTRY_MATCHER.fullmatch(value.strip()))


def inspect_build_policy(package_root: Path, pnpm_binary: str) -> dict[str, object]:
    strict_value = _run_config_get(pnpm_binary, package_root, "strictDepBuilds")
    dangerous_value = _run_config_get(
        pnpm_binary, package_root, "dangerouslyAllowAllBuilds"
    )
    allow_value = _run_config_get(pnpm_binary, package_root, "allowBuilds")

    strict = True if strict_value is None else strict_value
    dangerous = False if dangerous_value is None else dangerous_value
    allow_builds = {} if allow_value is None else allow_value

    if not isinstance(strict, bool):
        raise BuildPolicyError("strictDepBuilds must resolve to a boolean")
    if not isinstance(dangerous, bool):
        raise BuildPolicyError("dangerouslyAllowAllBuilds must resolve to a boolean")
    if not isinstance(allow_builds, dict):
        raise BuildPolicyError("allowBuilds must resolve to an object")

    if strict is not True:
        raise BuildPolicyError(
            "strictDepBuilds=false weakens the DevKit fail-closed dependency build policy",
            blocker_class="PNPM_BUILD_POLICY_UNSAFE",
        )
    if dangerous is True:
        raise BuildPolicyError(
            "dangerouslyAllowAllBuilds=true is forbidden; approve dependency builds explicitly in pnpm-workspace.yaml",
            blocker_class="PNPM_BUILD_POLICY_UNSAFE",
        )

    approved: list[str] = []
    denied: list[str] = []
    pending: list[str] = []
    broad_approvals: list[str] = []

    for raw_matcher, decision in sorted(allow_builds.items()):
        matcher = str(raw_matcher).strip()
        if decision is True:
            approved.append(matcher)
            if not is_exact_registry_matcher(matcher):
                broad_approvals.append(matcher)
        elif decision is False:
            denied.append(matcher)
        else:
            pending.append(matcher)

    if pending:
        raise BuildPolicyError(
            "unreviewed pnpm dependency build entries require one-time user approval: "
            + ", ".join(pending),
            blocker_class="PNPM_BUILD_POLICY_REVIEW_REQUIRED",
        )
    if broad_approvals:
        raise BuildPolicyError(
            "approved dependency builds must use exact package@version matchers by default: "
            + ", ".join(broad_approvals),
            blocker_class="PNPM_BUILD_POLICY_SCOPE_TOO_BROAD",
        )

    policy_file = package_root / "pnpm-workspace.yaml"
    return {
        "policy_file": str(policy_file) if policy_file.is_file() else "NOT_PRESENT",
        "strict_dep_builds": strict,
        "dangerously_allow_all_builds": dangerous,
        "allow_builds": {str(key): value for key, value in allow_builds.items()},
        "approved": approved,
        "denied": denied,
    }


def build_decision_plan(
    policy: dict[str, object],
    *,
    approvals: list[str],
    denials: list[str],
) -> dict[str, object]:
    if not approvals and not denials:
        raise BuildPolicyError(
            "at least one --approve or --deny matcher is required",
            blocker_class="PNPM_BUILD_POLICY_DECISION_EMPTY",
        )

    normalized_approvals = sorted(set(value.strip() for value in approvals if value.strip()))
    normalized_denials = sorted(set(value.strip() for value in denials if value.strip()))

    invalid = [
        matcher
        for matcher in [*normalized_approvals, *normalized_denials]
        if not is_exact_registry_matcher(matcher)
    ]
    if invalid:
        raise BuildPolicyError(
            "DevKit build decisions require exact package@version matchers: "
            + ", ".join(invalid),
            blocker_class="PNPM_BUILD_POLICY_MATCHER_NOT_EXACT",
        )

    contradictions = sorted(set(normalized_approvals) & set(normalized_denials))
    if contradictions:
        raise BuildPolicyError(
            "the same matcher cannot be both approved and denied: "
            + ", ".join(contradictions),
            blocker_class="PNPM_BUILD_POLICY_DECISION_CONFLICT",
        )

    existing = policy.get("allow_builds")
    merged: dict[str, bool] = {}
    if isinstance(existing, dict):
        for key, value in existing.items():
            if isinstance(value, bool):
                merged[str(key)] = value

    for matcher in normalized_approvals:
        merged[matcher] = True
    for matcher in normalized_denials:
        merged[matcher] = False

    allow_json = json.dumps(merged, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "allow_builds": merged,
        "allow_builds_json": allow_json,
        "commands": [
            "pnpm config set --location=project --json strictDepBuilds true",
            "pnpm config set --location=project --json dangerouslyAllowAllBuilds false",
            "pnpm config set --location=project --json allowBuilds "
            + shlex.quote(allow_json),
        ],
    }


def _resolve_package(args: argparse.Namespace) -> tuple[Path, Path, str]:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise BuildPolicyError(
            f"workspace does not exist: {workspace}",
            blocker_class="PROJECT_STRUCTURE_INVALID",
        )
    cwd = resolve_cwd(workspace, args.cwd)
    package_root = resolve_package_root(workspace, cwd)
    pnpm_binary = shutil.which("pnpm")
    if not pnpm_binary:
        raise BuildPolicyError(
            "pnpm standalone executable is unavailable in the DevKit runtime",
            blocker_class="DEVKIT_RUNTIME_CAPABILITY_MISSING",
        )
    return workspace, package_root, pnpm_binary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or plan updates to pnpm's standard allowBuilds project policy."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--approve", action="append", default=[])
    parser.add_argument("--deny", action="append", default=[])
    args = parser.parse_args()

    try:
        workspace, package_root, pnpm_binary = _resolve_package(args)
        policy = inspect_build_policy(package_root, pnpm_binary)

        print(f"WORKSPACE={workspace}")
        print(f"PACKAGE_ROOT={package_root}")
        print(f"PNPM_BUILD_POLICY_FILE={policy['policy_file']}")
        print("PNPM_BUILD_POLICY_SOURCE=pnpm-workspace.yaml")
        print("PNPM_STRICT_DEP_BUILDS=true")
        print("PNPM_DANGEROUSLY_ALLOW_ALL_BUILDS=false")
        print(
            "PNPM_APPROVED_BUILDS="
            + (",".join(policy["approved"]) if policy["approved"] else "NONE")
        )
        print(
            "PNPM_DENIED_BUILDS="
            + (",".join(policy["denied"]) if policy["denied"] else "NONE")
        )

        if args.approve or args.deny:
            plan = build_decision_plan(
                policy,
                approvals=args.approve,
                denials=args.deny,
            )
            print("PNPM_BUILD_POLICY_DECISION=READY")
            print(f"PNPM_ALLOW_BUILDS_JSON={plan['allow_builds_json']}")
            for index, command in enumerate(plan["commands"], start=1):
                print(f"POLICY_UPDATE_COMMAND_{index}={command}")
        else:
            print("PNPM_BUILD_POLICY=PASS")
        return 0
    except BuildPolicyError as exc:
        print("PNPM_BUILD_POLICY=BLOCKED", file=sys.stderr)
        print(f"BLOCKER_CLASS={exc.blocker_class}", file=sys.stderr)
        print(f"BLOCKER={exc}", file=sys.stderr)
        return 2
    except WorkspaceError as exc:
        print("PNPM_BUILD_POLICY=BLOCKED", file=sys.stderr)
        print("BLOCKER_CLASS=PROJECT_STRUCTURE_INVALID", file=sys.stderr)
        print(f"BLOCKER={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
