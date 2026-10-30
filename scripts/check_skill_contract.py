#!/usr/bin/env python3
from __future__ import annotations
import ast, re, sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "custom-skills"
REQUIRED_SKILLS = {"dev-project-pattern","dev-java-guidelines","dev-spring-guidelines","dev-spring-feature","dev-spring-data","dev-spring-test","dev-api-docs"}
REQUIRED_REFERENCES = {}
SHARED_REQUIRED_REFERENCES={"development-contract.md","maven-runtime.md","verification-level-policy.md"}

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
def extract_section(text:str,start_heading:str,end_heading:str)->str:
    start=text.find(start_heading)
    if start<0: fail(f"missing section heading: {start_heading}")
    end=text.find(end_heading,start+len(start_heading))
    if end<0: fail(f"missing section end heading after {start_heading}: {end_heading}")
    return text[start:end]

def main():
    names={}; related={}
    for path in sorted(SKILLS_ROOT.glob('*/*/SKILL.md')):
        scalar,lists,body=parse_frontmatter(path.read_text(encoding='utf-8'),path)
        scope=path.parent.parent.name; name=scalar.get('name','')
        if scope not in ('core','shared'): fail(f'Legacy skill scope: {scope}')
        if name!=path.parent.name or not re.fullmatch(r'[a-z0-9][a-z0-9-]*',name): fail(f'Invalid name: {path}')
        if name in names: fail(f'Duplicate effective skill name: {name}')
        if not re.fullmatch(r'\d+\.\d+\.\d+',scalar.get('version','')): fail(f'Invalid version: {name}')
        if not scalar.get('description') or len(scalar['description'])>1024: fail(f'Invalid description: {name}')
        names[name]=path; related[name]=lists.get('related_skills',[])
    missing=(REQUIRED_SKILLS | {'dev-session','dev-review','git-pr-publish','dev-feature-docs','dev-project-setup'})-names.keys()
    if missing: fail(f'Missing active skills: {sorted(missing)}')
    for name, refs in related.items():
        for ref in refs:
            if ref not in names: fail(f'Broken related_skills: {name} -> {ref}')
    for reference in SHARED_REQUIRED_REFERENCES:
        if not (REPO_ROOT/'shared/references'/reference).is_file(): fail('Missing shared reference '+reference)
    for scope in ('orchestrator','coder','reviewer'):
        if (SKILLS_ROOT/scope).exists(): fail('Legacy role catalog remains: '+scope)
    print(f'[PASS] {len(names)} unique DevKit/shared skills; references resolvable')
if __name__=='__main__': main()
