#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required_skills = (
    "dev-data-feature",
    "dev-data-modeling",
    "dev-db-schema",
    "dev-db-query",
    "dev-db-migration",
    "dev-db-performance",
)
for name in required_skills:
    path = ROOT / "custom-skills" / "shared" / name / "SKILL.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing data shared skill: {name}")

foundation_path = ROOT / "shared/references/data-design-rules.md"
if not foundation_path.is_file():
    raise SystemExit("data-design-rules.md is missing")

vendor_root = ROOT / "custom-skills/shared/dev-data-feature/references/vendors"
for name in ("mssql", "mysql", "mariadb", "postgresql", "oracle"):
    path = vendor_root / f"{name}.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing database vendor reference: {name}")

pattern = (ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md").read_text(encoding="utf-8")
breakdown = (ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md").read_text(encoding="utf-8")
data_entry = (ROOT / "custom-skills/shared/dev-data-feature/SKILL.md").read_text(encoding="utf-8")
data_modeling = (ROOT / "custom-skills/shared/dev-data-modeling/SKILL.md").read_text(encoding="utf-8")
stack_guide = (ROOT / "shared/references/stack-capability-skill-guide.md").read_text(encoding="utf-8")
detector = (ROOT / "custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py").read_text(encoding="utf-8")
cache = (ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/stack_cache.py").read_text(encoding="utf-8")
documentation = (ROOT / "custom-skills/shared/dev-data-feature/references/documentation-contract.md").read_text(encoding="utf-8")
foundation = foundation_path.read_text(encoding="utf-8")

checks = {
    "data foundation": (foundation, (
        "Current State", "History / Ledger", "Snapshot", "Derived Data",
        "docs/data/schema.dbml", "LOGICAL_RELATIONAL", "PHYSICAL", "Design-Time DBA",
    )),
    "project pattern": (pattern, (
        "dev-data-feature", "Data Capability Hints", "Database Vendor Candidates",
        "docs/data/schema.dbml", "DBML Canvas", "dev-spring-data",
    )),
    "breakdown": (breakdown, (
        "dev-data-feature", "Data Model Gate", "Data Model Status", "Data Task Class",
        "DBML Path", "dev-data-modeling", "dev-db-schema", "dev-db-query",
        "dev-db-migration", "dev-db-performance",
    )),
    "data entry": (data_entry, (
        "canonical runtime entry", "Data Task Class", "Database Vendor", "DBML Mode",
        "Data Model Gate", "DBML Canvas", "Design-Time DBA", "lazy-load",
    )),
    "data modeling": (data_modeling, (
        "책임", "cardinality", "Current / History / Snapshot / Derived",
        "docs/data/schema.dbml", "dbml_guard.py", "full DBML parser",
    )),
    "stack guide": (stack_guide, (
        "Data canonical entry", "dev-data-feature", "dev-data-modeling", "dev-db-schema",
        "dev-db-query", "dev-db-migration", "dev-db-performance", "DBML Canvas",
    )),
    "detector": (detector, (
        'DETECTOR_VERSION = "4"', "DATABASE_JVM_MARKERS", "DATABASE_NPM_MARKERS",
        "schema.prisma", "database_vendors", "data_entry_candidate", "dev-data-feature",
    )),
    "stack cache": (cache, (
        "database_vendors", "data_entry_candidate", "DATABASE_VENDORS", "DATA_ENTRY_CANDIDATE",
    )),
    "documentation": (documentation, (
        "schema.dbml", "DBML Canvas", "canonical relational model", "QUERY_ONLY",
        "MODEL_CHANGE", "SCHEMA_CHANGE", "MIGRATION", "PERFORMANCE",
    )),
}
for label, (text, terms) in checks.items():
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")

# Design-time data capability must not claim direct operational authority.
for name in required_skills:
    text = (ROOT / "custom-skills/shared" / name / "SKILL.md").read_text(encoding="utf-8")
    if "운영 DB" in text and "직접" in text and "수행" in text and "하지 않는다" not in text:
        raise SystemExit(f"{name} appears to grant direct operational DB authority")

print("[PASS] Data/DBA/DBML capability contract")
