#!/usr/bin/env python3
"""Check opt-in feature-document skill policies without changing runtime state."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/orchestrator/dev-feature-docs"


def require(text: str, label: str, terms: tuple[str, ...]) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise ValueError(f"{label} missing required policy terms: {', '.join(missing)}")


def main() -> int:
    required_files = (
        "SKILL.md", "README.md", "references/document-policy.md",
        "references/standard-flow.md", "references/sources.md",
        "templates/feature.md", "templates/index.md",
        "scripts/find_feature_docs.py", "tests/test_find_feature_docs.py",
    )
    content = {}
    for relative in required_files:
        text = (SKILL / relative).read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Empty feature documentation file: {relative}")
        content[relative] = text

    skill = content["SKILL.md"]
    if not skill.startswith("---\n") or "\n---\n" not in skill[4:]:
        raise ValueError("Skill YAML frontmatter is missing")
    frontmatter = skill[4:skill.index("\n---\n", 4)]
    require(frontmatter, "skill metadata", (
        "name: dev-feature-docs", "platforms: [linux]", "author: local",
        "dev-workflow-orchestrate", "dev-workspace-dispatch",
    ))
    if not re.search(r"^version: \d+\.\d+\.\d+$", frontmatter, re.M):
        raise ValueError("Skill version must use x.y.z")
    description = re.search(r"^description: (.+)$", frontmatter, re.M)
    if description is None or len(description.group(1)) > 1024:
        raise ValueError("Skill description must contain 1 to 1024 characters")

    require(skill, "feature skill boundary", (
        "계획 중 / 진행 중 / 구현 완료", "명시적 문서화 요청은 문서 쓰기 동의",
        "쓰기 직전에", "관찰 기반 best-effort", "별도 watcher",
        "문서 문제만으로 구현 Task를 BLOCKED/실패로 바꾸지 않는다",
        "읽기 전용 후보 수집기", "Orchestrator가 문서 연결",
    ))
    require(content["references/document-policy.md"], "document policy", (
        "사용자가 말한 사실·결정과 에이전트 제안", "안전한 부분 수정",
        "후속 아이디어", "제외", "Task DONE만", "근거 재사용",
    ))
    require(content["references/standard-flow.md"], "standard integration policy", (
        "명시적 지정", "승인 연결 재사용", "docs/features/README.md",
        "상태 갱신 대상", "참고 전용", "별도의 문서 선택 Gate를 만들거나",
        "승인 worktree", "지연 반영 경계", "문제만으로 Task를 BLOCKED",
        "Direct Flow에 신규 자동 탐색을 추가하지 않는다",
    ))
    require(content["templates/feature.md"], "feature template", (
        "계획 중", "합의된", "향후", "확인",
    ))
    index = content["templates/index.md"]
    if any("상태" in line for line in index.splitlines() if line.lstrip().startswith("|")):
        raise ValueError("Index must not duplicate per-document status columns")
    require(content["references/sources.md"], "policy provenance", (
        "Fission-AI/OpenSpec", "product-on-purpose/pm-skills", "snarktank/ralph",
        "MIT", "Apache-2.0", "제외", "blob SHA",
    ))

    tree = ast.parse(content["scripts/find_feature_docs.py"])
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree)
               if isinstance(node, ast.Import)}
    if imports & {"subprocess", "requests", "socket", "sqlite3", "http"}:
        raise ValueError("Candidate discovery must not depend on process/network/task APIs")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"write_text", "write_bytes", "unlink", "mkdir", "rename", "replace"}:
                raise ValueError("Candidate discovery contains a project mutation call")

    workflow = (ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md").read_text(encoding="utf-8")
    dispatch = (ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md").read_text(encoding="utf-8")
    require(workflow, "workflow optional hook", (
        'skill_view("dev-feature-docs")', "실행계획 확정 전에",
        "별도 Gate, 필수 Task field, Feature ID", "실시간 갱신을 보장하지 않는다",
        "기존 상태 머신, clarify 질문, dispatch 횟수",
    ))
    require(dispatch, "dispatch optional handoff", (
        "## 선택적 기능 문서 인계", "한국어 자유 형식 설명",
        "진입 조건이나 새로운 승인 Gate가 아니다", "필수 pin하지 않는다",
        "문서 누락/모호함/반영 실패만으로 dispatch를 차단하지 않는다",
    ))
    ci = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
    require(ci, "existing CI integration", (
        "bash scripts/verify.sh", "python3 scripts/check_feature_docs_contract.py",
        "python3 custom-skills/orchestrator/dev-feature-docs/tests/test_find_feature_docs.py",
    ))
    print("[PASS] Feature documentation static policy and optional integration contract")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[FAIL] {exc}") from exc
