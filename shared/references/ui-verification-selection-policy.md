# UI Verification Selection Policy V1

Canonical contract: `UI_VERIFICATION_SELECTION_V1`. Applies to Direct, Standard, Recovery and CHANGES_REQUESTED **only when frontend UI is in the approved Work Unit**. This selects minimum sufficient evidence; it is not a new test runner, browser provider, or permission to weaken an approved Verification Contract.

## 1. Authority and evidence

Priority: (1) approved Task/AC/latest authorized Recovery Revision; (2) project tests, CI, AGENTS and conventions; (3) `VERIFICATION_LEVEL_POLICY_V1`; (4) these UI selection defaults. An explicitly approved required E2E, visual, accessibility, viewport or browser test cannot be silently downgraded to OPTIONAL or NOT_APPLICABLE. Coder may escalate verification for newly demonstrated risk within scope; changing approved required AC/method/provider/environment needs the existing approval or Recovery Revision path.

An AC is a user-observable requirement, not a list of test invocations. Map `AC -> evidence`. One test may cover multiple AC, one AC may need different kinds of evidence. Repeating the same behavior across viewport permutations does not create new AC. Prefer existing project canonical tests to one-off browser suites.

## 2. Classify actual checks, not AC importance

- `REQUIRED`: necessary to substantiate an approved AC or identified P0/P1 risk with no adequate equivalent evidence. If required evidence is unavailable, **completion is blocked**, never PASS.
- `OPTIONAL`: useful but redundant or diagnostic test. Its NOT_RUN/environment failure does not alone prevent review or completion. A real uncovered P0/P1 defect found in an optional check is not permission to ignore evidence.
- `NOT_APPLICABLE`: no affected approved behavior, design reference or baseline. Explain why; never call omitted checks PASS.

Distinguish AC outcome from Test Case execution outcome (PASS/FAIL/BLOCKED_ENV/UNSUPPORTED/INCONCLUSIVE/NOT_RUN). Record required AC and chosen required check IDs. `Suite(required=[...])` receives only REQUIRED checks and may separately execute OPTIONAL tests. Automatically generated Cartesian test matrices are not automatically approved REQUIRED AC.

## 3. Risk and smallest sufficient verification

| Changed behavior | Preferred minimum | Escalate only for |
| --- | --- | --- |
| Copy, label, icon | existing static/targeted checks | actual layout/accessibility risk or approval |
| Search, filter, derived state | unit/component behavior test | route/browser persistence impact |
| Form, validation, keyboard | component/accessibility behavior test | native focus/navigation behavior |
| History, beforeunload, native confirm | affected focused Browser test | distinct browser journey or approved variant |
| SHARED/RESPONSIVE UI | representative Desktop/Mobile layout checks if affected | changed breakpoint, SPLIT_VIEW, divergent interactions |
| Approved IMAGE/Figma | design conformance against approved intent | specifically approved visual AC |
| Approved rendered baseline | visual regression | deterministic environment and real baseline |
| Authz, sensitive data, payments, destructive actions | relevant integration/security and critical journey tests | identified P0/P1 risk or approved production contract |

`CODE_DRIVEN` and DRAFT/reference-only design do not create mandatory pixel equality. Screenshot capture is not evidence of Korean glyph legibility, design conformance or functional correctness. For shared UI, do not repeat identical functional assertions for every viewport without risk. SPLIT_VIEW with different behavior deserves distinct checks.

## 4. Browser scope and environment separation

Browser E2E is conditional, not a universal frontend gate. Prefer the approved existing project runner/provider. Probe only capabilities required by selected browser-dependent AC; no automatic download/popup/clipboard/dialog/full viewport matrix. Fixture capability PASS never substitutes for actual product AC. Do not automatically change provider, dependency, authentication or Node isolation to obtain a pass.

Browser/font/capture infrastructure failure is BLOCKED_ENV or NOT_RUN for the affected check, not product FAIL. Continue independent checks if safe. Optional visual evidence becoming unavailable is not grounds to invent a new required AC. Missing **approved required** visual/browser checks still blocks final completion, requiring the existing reapproval/recovery route.

## 5. UI Verification Scope Decision (plan and handoff)

- `AC Evidence Map`: AC ID -> observed actual test/manual evidence or outstanding verification.
- `Required Checks`: minimum selected evidence and method/provider/risk reason.
- `Optional Checks`: non-blocking diagnostics and reason for omission.
- `Not Applicable`: e.g. DRAFT design conformance or no approved regression baseline.
- `Escalation Reason`: explain why extra browser, boundary viewport or full suite is necessary.
- `Required AC Outstanding`: never hide approved missing requirements with optional PASS.

Preserve existing Verification Level, Verification Provider, Environment Dependency, Approval fields and F/UI/AC identifiers. Do not force new project dependencies/YAML manifests or mass screen-spec migrations.

## 6. Regression examples

- Shared responsive search/filter: one targeted component test and relevant layout coverage; a 2 x 4 x N screenshot matrix is not implicitly REQUIRED.
- Dirty `beforeunload`: state logic plus the approved real browser-native dismiss test. A fixture-only dialog PASS is not product proof.
- `CODE_DRIVEN` and DRAFT image: Design Conformance NOT_REQUIRED unless separately approved. Readability is a separate affected layout check.
- Optional Korean screenshot blocked by missing font: BLOCKED_ENV, not product FAIL and not retroactively REQUIRED.
- Explicitly approved 760px viewport: REQUIRED until an authorized Revision changes it.
- High-risk authz or destructive behavior: do not replace required integration/security checks with only component tests.
