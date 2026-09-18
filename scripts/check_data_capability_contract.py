#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
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

if (ROOT / "custom-skills/coder/dev-db-migration").exists():
    raise SystemExit("dev-db-migration must remain shared/pinnable; Coder owns mutation responsibility by contract")

foundation_path = ROOT / "shared/references/data-design-rules.md"
if not foundation_path.is_file():
    raise SystemExit("data-design-rules.md is missing")

vendor_root = ROOT / "custom-skills/shared/dev-data-feature/references/vendors"
for name in ("mssql", "mysql", "mariadb", "postgresql", "oracle"):
    path = vendor_root / f"{name}.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing database vendor reference: {name}")

migration_root = ROOT / "custom-skills/shared/dev-db-migration"
migration_guard = migration_root / "scripts/migration_guard.py"
migration_tests = migration_root / "tests/test_migration_guard.py"
for path in (migration_guard, migration_tests):
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing migration policy helper/test: {path.relative_to(ROOT)}")

pattern = (ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md").read_text(encoding="utf-8")
breakdown = (ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md").read_text(encoding="utf-8")
dispatch = (ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md").read_text(encoding="utf-8")
data_entry = (ROOT / "custom-skills/shared/dev-data-feature/SKILL.md").read_text(encoding="utf-8")
data_modeling = (ROOT / "custom-skills/shared/dev-data-modeling/SKILL.md").read_text(encoding="utf-8")
db_schema = (ROOT / "custom-skills/shared/dev-db-schema/SKILL.md").read_text(encoding="utf-8")
migration = (migration_root / "SKILL.md").read_text(encoding="utf-8")
stack_guide = (ROOT / "shared/references/stack-capability-skill-guide.md").read_text(encoding="utf-8")
detector = (ROOT / "custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py").read_text(encoding="utf-8")
cache = (ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/stack_cache.py").read_text(encoding="utf-8")
documentation = (ROOT / "custom-skills/shared/dev-data-feature/references/documentation-contract.md").read_text(encoding="utf-8")
example_dbml = (ROOT / "custom-skills/shared/dev-data-modeling/examples/schema.dbml").read_text(encoding="utf-8")
foundation = foundation_path.read_text(encoding="utf-8")

checks = {
    "data foundation": (foundation, (
        "Current State", "History / Ledger", "Snapshot", "Derived Data",
        "Subject Area", "TableGroup", "docs/data/schema.dbml", "LOGICAL_RELATIONAL", "PHYSICAL",
        "Design-Time DBA", "Coder physicalization", "PROJECT_EXISTING", "PROJECT_INFERRED", "DEVKIT_DEFAULT",
        "tbl_<subject_area>_<entity>", "V<yyyyMMddHHmmss>", "UTC", "Flyway", "Liquibase", "outOfOrder=true",
        "public_id", "external_id", "UUIDv7",
        "created_at", "created_by", "updated_at", "updated_by",
        "deleted_at", "deleted_by", "is_deleted",
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
    "dispatch": (dispatch, (
        "Coder/Reviewer 공통 사용 가능 skill만 pin", "VALIDATED_SKILLS", "kanban_create.skills",
    )),
    "data entry": (data_entry, (
        "canonical runtime entry", "DBA logical phase", "Coder physical phase", "Subject Area",
        "shared/pinnable `dev-db-migration`", "migration 파일 작성·변경의 실행 권한은 Coder",
        "Data Model Gate", "LOGICAL_RELATIONAL", "Physicalization Required", "TableGroup",
        "APPROVED", "DBML Canvas", "Design-Time",
    )),
    "data modeling": (data_modeling, (
        "Design-Time DBA", "Subject Area", "TableGroup", "책임", "cardinality",
        "Current / History / Snapshot / Derived", "docs/data/schema.dbml", "dbml_guard.py",
        "--require-subject-area", "tbl_<subject_area>_<entity>", "Data Model Status: DRAFT | APPROVED",
    )),
    "db schema": (db_schema, (
        "Coder migration", "Approved Subject Area", "DEVKIT_DEFAULT Physical Naming",
        "tbl_<subject_area>_<entity>", "tbl_investment_account", "Data Naming Source",
        "Internal PK", "Internal FK", "public_id", "external_id", "UUIDv7",
        "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by", "is_deleted",
    )),
    "migration": (migration, (
        "shared/pinnable", "migration 파일 작성·변경의 실행 책임은 Coder", "Reviewer", "read-only",
        "APPROVED DBA Logical Model", "Flyway", "Liquibase", "default",
        "tbl_<subject_area>_<entity>", "V<yyyyMMddHHmmss>__<description>.sql", "UTC",
        "outOfOrder=true", "기존 V...sql 수정", "새 V...sql 추가", "ddl-auto: validate",
        "/opt/custom-skills/shared/dev-db-migration/scripts/migration_guard.py",
        "--allocate-flyway-version", "MIGRATION_TOOL=conflict",
    )),
    "stack guide": (stack_guide, (
        "Data canonical entry", "dev-data-feature", "dev-data-modeling", "dev-db-schema",
        "dev-db-query", "dev-db-migration", "dev-db-performance", "DBML Canvas",
    )),
    "detector": (detector, (
        'DETECTOR_VERSION = ', "BACKEND_ENTRY_BY_STACK", "BACKEND_HINT_BY_STACK", "DATABASE_JVM_MARKERS", "DATABASE_NPM_MARKERS",
        "schema.prisma", "database_vendors", "data_entry_candidate", "dev-data-feature",
    )),
    "stack cache": (cache, (
        "database_vendors", "data_entry_candidate", "DATABASE_VENDORS", "DATA_ENTRY_CANDIDATE",
    )),
    "documentation": (documentation, (
        "schema.dbml", "DBML Canvas", "canonical relational model", "QUERY_ONLY",
        "MODEL_CHANGE", "SCHEMA_CHANGE", "MIGRATION", "PERFORMANCE",
    )),
    "default dbml example": (example_dbml, (
        "Table account", "id bigint [pk]", "Table transaction",
        "account_id bigint [not null]", "TableGroup finance",
        "Ref: transaction.account_id > account.id",
    )),
}
for label, (text, terms) in checks.items():
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")

for forbidden in ("Table tbl_", "CREATE TABLE", "ALTER TABLE"):
    if forbidden in example_dbml:
        raise SystemExit(f"default DBML example contains physical implementation syntax: {forbidden}")

for legacy_pk in ("account_id bigint [pk]", "transaction_id bigint [pk]"):
    if legacy_pk in example_dbml:
        raise SystemExit(f"default DBML example uses legacy default PK naming: {legacy_pk}")

for name in ("dev-data-feature", "dev-data-modeling"):
    text = (ROOT / "custom-skills/shared" / name / "SKILL.md").read_text(encoding="utf-8")
    if "실제 DB migration 실행" in text and "하지 않는다" not in text:
        raise SystemExit(f"{name} appears to grant physical migration execution authority")

subprocess.run([sys.executable, str(migration_tests)], cwd=ROOT, check=True)

print("[PASS] Data/DBA logical + shared Coder migration capability contract")
