# Browser Verification Contract V1

This is a verification *policy*, not a new browser provider or a new test framework.
Applies to Direct, Standard, Recovery and CHANGES_REQUESTED frontend work.

## Selection and capability preflight

1. Preserve the approved Verification Provider/Method/Environment and the project's existing
   Playwright/Cypress/Storybook/test scripts; do not install new dependencies or switch providers
   without the existing approval gate. Existing Node commands still use node_environment_gate.py,
   node_verification_cached.py and node_runtime.py.
2. Map Screen Spec F/UI/AC to required capabilities **before** attempting browser work:
   navigation, input, screenshot, native-confirm, beforeunload-dismiss, download, etc.
   Only check capabilities needed by the AC; not every screen needs a browser.
3. A previous PASS is a capability hint, not proof of this UI behavior. The independent
   Chromium/CDP A-E probes can pass while the Next.js form still fails in the actual session.
   For beforeunload, require a real user activation, actual dirty input, a dialog opening event,
   a deliberate dismiss response, then confirmation that navigation was cancelled and data retained.
4. Native dialogs block JavaScript. Trigger the navigation asynchronously and respond via the
   approved provider's supported dialog API, without synchronous blocking on navigation.
   Inspect pending/recent dialogs and session IDs before deciding to retry.
   A direct CDP observer PASS does not prove browser_exec's own native dialog response works.
5. Runtime lifecycle: bounded server readiness, uniquely named test session and isolated fixture,
   explicit origin, predictable fonts/viewport/test data, independent evidence paths, finally
   cleanup of browser tab/server/profile. Do not alter production auth, lockfiles, app config, or
   other agents' browser sessions to make an E2E pass. Reuse project harness when it exists.
6. If capability cannot be established, mark its AC NOT_RUN (not PASS/FAIL), use
   Execution Status BLOCKED_ENV, UNSUPPORTED or INCONCLUSIVE and retain evidence. No automatic
   unapproved provider fallback, and no Kanban unblock / Reviewer handoff when mandatory AC
   is still unverified. Unrelated proven tests remain recorded with their original scope/timestamp.
7. A repeated failure with identical provider, capability, session class, and failure signature
   does not justify another product Coder attempt without new evidence. Escalate as a browser
   runtime capability issue; do not rewrite product code or repeat the same probe indefinitely.

## Structured evidence

Write a JSON evidence file in the approved Task artifacts directory (not product source),
with schema browser_verification_v1, task_id, provider, session, verified_at,
capabilities, acceptance_criteria and cleanup. Use the shared
`scripts/browser_verification_evidence.py` validator before handoff.
Each capability: name, status PASS|FAIL|NOT_RUN, execution_status
PASS|FAIL|BLOCKED_ENV|UNSUPPORTED|INCONCLUSIVE|NOT_RUN, evidence.
Each AC: ac_id, method, status PASS|FAIL|NOT_RUN, capability, evidence.
No secrets, CDP websocket tokens, authentication data, session cookies or real account numbers
are allowed in evidence. Preserve source hashes, viewport, runtime version and redacted
dialog event sequence when useful.

Output remains compatible with Screen Spec AC PASS/FAIL/NOT_RUN. Internal execution status
adds a reason; it must never turn an unverified behavior into PASS.

## Handoff

Browser Provider: <approved project runner | Hermes browser_exec | NOT_REQUIRED>
Browser Capability Gate: PASS | BLOCKED | NOT_REQUIRED
Browser Capability Evidence: <validated JSON path | NONE>
Browser Execution Status: PASS | FAIL | BLOCKED_ENV | UNSUPPORTED | INCONCLUSIVE | NOT_RUN
Browser Cleanup: PASS | WARNING | NOT_RUN
Required AC Outstanding: <AC IDs | NONE>
Browser Recovery Fingerprint: <provider/capability/signature | NONE>
