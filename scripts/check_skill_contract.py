#!/usr/bin/env python3
from __future__ import annotations
import ast, re, sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "custom-skills"
REQUIRED_SKILLS = {"dev-project-pattern","dev-skill-preflight","dev-java-guidelines","dev-spring-guidelines","dev-spring-feature","dev-spring-data","dev-spring-test","dev-api-docs"}
REQUIRED_REFERENCES = {("shared","dev-api-docs"):{"references/spring-openapi-reference.md","references/postman-reference.md"},("orchestrator","dev-workflow-orchestrate"):{"references/dispatch-efficiency.md"}}
SHARED_REQUIRED_REFERENCES={"approval-gate-rules.md"}

def fail(message:str)->None: raise SystemExit(f"[FAIL] {message}")
def parse_inline_list(value:str)->list[str]:
    value=value.strip()
    if not(value.startswith("[") and value.endswith("]")): return []
    try: parsed=ast.literal_eval(value)
    except (ValueError,SyntaxError):
        inner=value[1:-1].strip(); return [i.strip().strip("'\"") for i in inner.split(",") if i.strip()] if inner else []
    return [str(i) for i in parsed] if isinstance(parsed,list) else []
def parse_frontmatter(text:str,path:Path):
    if not text.startswith("---\n"): fail(f"missing YAML frontmatter start: {path}")
    end=text.find("\n---\n",4)
    if end<0: fail(f"missing YAML frontmatter end: {path}")
    frontmatter=text[4:end]; body=text[end+5:].strip()
    if not body: fail(f"empty SKILL.md body: {path}")
    scalar={}; lists={}
    for line in frontmatter.splitlines():
        m=re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$",line)
        if m:
            k,v=m.groups()
            if v:
                scalar[k]=v.strip().strip("'\"")
                if v.strip().startswith("["): lists[k]=parse_inline_list(v)
            continue
        n=re.match(r"^\s+([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$",line)
        if n and n.group(2).strip().startswith("["): lists[n.group(1)]=parse_inline_list(n.group(2))
    return scalar,lists,body
def require_terms(text,label,terms):
    missing=[t for t in terms if t not in text]
    if missing: fail(f"{label} missing required contract terms: "+", ".join(missing))
def forbid_terms(text,label,terms):
    present=[t for t in terms if t in text]
    if present: fail(f"{label} contains forbidden contract terms: "+", ".join(present))

def main()->int:
    discovered={}; paths_by_name=defaultdict(list); related_by_skill={}
    for skill_file in sorted(SKILLS_ROOT.glob("*/*/SKILL.md")):
        text=skill_file.read_text(encoding="utf-8"); scalar,lists,_=parse_frontmatter(text,skill_file)
        scope=skill_file.parent.parent.name; name=scalar.get("name","").strip(); desc=scalar.get("description","").strip()
        if not name or name!=skill_file.parent.name: fail(f"skill name/path mismatch: {skill_file}")
        if (scope,name) in discovered: fail(f"duplicate skill name within scope {scope!r}: {name!r}")
        if not desc or len(desc)>1024: fail(f"invalid description: {skill_file}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*",name): fail(f"skill name must be lowercase kebab-case: {name}")
        discovered[(scope,name)]=skill_file; paths_by_name[name].append(skill_file); related_by_skill[(scope,name)]=lists.get("related_skills",[])
    missing=sorted(REQUIRED_SKILLS-paths_by_name.keys())
    if missing: fail("required capability skills are missing: "+", ".join(missing))
    for key,refs in REQUIRED_REFERENCES.items():
        sf=discovered.get(key)
        if sf is None: fail(f"required skill missing for reference validation: {key}")
        for rel in refs:
            target=sf.parent/rel
            if not target.is_file() or not target.read_text(encoding="utf-8").strip(): fail(f"required reference missing/empty for {key}: {rel}")
    shared_reference_root=REPO_ROOT/"shared"/"references"
    for rel in SHARED_REQUIRED_REFERENCES:
        target=shared_reference_root/rel
        if not target.is_file() or not target.read_text(encoding="utf-8").strip(): fail(f"required shared reference missing/empty: {rel}")
    for (scope,name),related in sorted(related_by_skill.items()):
        for r in related:
            if r.startswith("dev-") and r not in paths_by_name: print(f"[WARN] related skill is not installed in custom-skills: {scope}/{name} -> {r}")
    for name,paths in sorted((n,p) for n,p in paths_by_name.items() if len(p)>1): print(f"[INFO] scope-scoped duplicate skill name allowed: {name} ({', '.join(sorted(p.parent.parent.name for p in paths))})")

    implement=discovered[("coder","dev-implement-plan")].read_text(encoding="utf-8")
    breakdown=discovered[("orchestrator","dev-breakdown")].read_text(encoding="utf-8")
    dispatch=discovered[("orchestrator","dev-workspace-dispatch")].read_text(encoding="utf-8")
    workflow_file=discovered[("orchestrator","dev-workflow-orchestrate")]; workflow=workflow_file.read_text(encoding="utf-8")
    reviewer=discovered[("reviewer","dev-code-review")].read_text(encoding="utf-8")
    approval=(shared_reference_root/"approval-gate-rules.md").read_text(encoding="utf-8")

    require_terms(breakdown,"dev-breakdown",('skill_view("dev-project-pattern")',"dev-java-guidelines"))
    require_terms(dispatch,"dev-workspace-dispatch preflight",('skill_view("dev-skill-preflight")',"VALIDATED_SKILLS","REJECTED_SKILLS","kanban_create.skills"))
    require_terms(workflow,"dev-workflow-orchestrate approval gates",(
        "/opt/data/shared/references/approval-gate-rules.md","WORKSPACE_APPROVED","BRANCH_APPROVED","MODEL_APPROVED","PLAN_APPROVED",
        "한 번의 사용자 확인에서는 하나의 의사결정만 요청한다","clarify","choices","↑/↓ + Enter",
        "[Project 선택]","[Workspace 선택]","[Branch 선택]","[Coder 모델 선택]","[작업 계획 승인]",
        "DEFAULT | PREMIUM","같은 Gate를 다시 출력","NO_EXTRA_KANBAN_CONFIRMATION","추가 Kanban 생성 확인 없이 즉시 AUTO_DISPATCH"))
    require_terms(approval,"shared approval gate rules",(
        "clarify","choices","↑/↓ 이동 + Enter 선택","Other (type your answer)","Workspace와 Branch는 서로 다른 Gate다",
        "AUTO_DISPATCH","NO_EXTRA_KANBAN_CONFIRMATION","Kanban 작업 카드를 등록할까요?"))
    forbid_terms(workflow,"number-list approval UX",("1. PREMIUM","2. DEFAULT","번호 또는 요구사항을 입력해주세요."))
    require_terms(workflow,"dispatch efficiency",("prepare_dispatch.py","정확히 한 번","working-tree 전체 scan을 하지 않는다","kanban_create tool 1회","kanban_show tool 1회","hermes project list","Kanban body 임시 파일","dispatch-efficiency.md","skipped-approved-preservation","change_summary.py --include","review_context.py --include"))
    require_terms(dispatch,"dev-workspace-dispatch fast path",("--confirmed-dirty","repository-wide dirty/EOL/untracked 분류를 **생략**","WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation","*_COUNT=-1","git diff --name-only -z HEAD","WORKSPACE_CLASSIFICATION_TOTAL_SECONDS",'initial_status="blocked"',"kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>)","subscribe_notification.py --board BOARD --task-id <CREATED_TASK_ID>","NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true","kanban_unblock(board=BOARD, task_id=<CREATED_TASK_ID>)","board == BOARD","HERMES_KANBAN_BOARD","CLI body-file 지원 여부 탐색","CLI fallback을 탐색하지 않고 BLOCK"))
    efficiency=(workflow_file.parent/"references"/"dispatch-efficiency.md").read_text(encoding="utf-8")
    require_terms(efficiency,"dispatch-efficiency reference",("skipped-approved-preservation","change_summary.py --include","review_context.py --include","큰 파일을 임의의 MB threshold로 제외하지 않는다","hermes project --help","CLI body-file capability probing"))
    for cap in ("dev-java-guidelines","dev-spring-guidelines","dev-spring-feature","dev-spring-data","dev-spring-test","dev-api-docs"):
        if f'skill_view("{cap}")' not in implement: fail(f"dev-implement-plan must explicitly load {cap} via skill_view")
    require_terms(implement,"dev-implement-plan scoped summary",("scoped change_summary.py","Standard Flow에서 `--include` 없이","--allow-full-scan","tracked와 untracked 모두 Git pathspec","Changed Files"))
    require_terms(reviewer,"dev-code-review scoped review",("review_context.py --include","Standard Flow에서는 `--include`를 반드시 제공","--allow-full-scan","tracked와 untracked 모두 Git pathspec","Java Convention Review Gate"))
    print(f"[PASS] Custom skill contract: {len(discovered)} scoped skills ({len(paths_by_name)} unique names) validated")
    return 0
if __name__=="__main__": sys.exit(main())
