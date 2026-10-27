#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Role-specific routing checks were retired; technical checks and actual test suites remain.
for checker in check_skill_contract check_capability_lifecycle_contract check_domain_contracts check_lite_repository check_env_contract check_update_devkit_contract check_git_publish_bootstrap_contract check_gradle_launcher_contract check_maven_launcher_contract check_hermes_tui_startup_contract; do
  python3 "scripts/$checker.py"
done
for helper in patch_hermes_tui_semantic_input patch_hermes_skill_slash_suggest patch_hermes_tirith_profile_guard check_hermes_security_contract patch_hermes_gateway_site_identity patch_hermes_kanban_relation_preview patch_hermes_parent_tracking_body devkit_gateway_readiness devkit_kanban_notifier; do
  python3 "scripts/$helper.py" --self-test
done
bash -n scripts/hermes-java
bash -n scripts/hermes-maven
bash -n updatekit_lite.sh
sh -n docker/cont-init.d/018-devkit-lite-init
sh -n docker/cont-init.d/019-devkit-kanban-notifier-policy
python3 scripts/run_regression_tests.py
printf '[PASS] Repository verification completed.\n'
