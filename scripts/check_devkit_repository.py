#!/usr/bin/env python3
"""The active runtime has one policy, resolvable assets and no legacy role engine."""
from pathlib import Path
import ast
import json
import re
import shlex
ROOT = Path(__file__).resolve().parents[1]

def main():
    problems = []
    def require(path, terms):
        p = ROOT / path
        if not p.is_file(): problems.append('Missing '+path); return ''
        text = p.read_text(encoding='utf-8-sig')
        for term in terms:
            if term not in text: problems.append(f'{path}: missing {term}')
        return text
    root = require('AGENTS.md', ('default', 'dev-session', '기존 변경', '2-depth', '영어'))
    common = require('shared/AGENTS.common.md', ('default', 'dev-session', 'maven-runtime.md'))
    start = root.find('<!-- HERMES-COMMON:START -->')
    end = root.find('<!-- HERMES-COMMON:END -->') + len('<!-- HERMES-COMMON:END -->')
    if start < 0 or root[start:end].rstrip() != common.rstrip(): problems.append('Root/common policy drift')
    if len(common) > 14000: problems.append('Global policy expanded beyond compact context budget')
    for path in ('custom-skills/orchestrator','custom-skills/coder','custom-skills/reviewer',
                 'custom-skills/shared/dev-flow-model-policy','init-profiles.ps1',
                 'scripts/devkit_worker_startup.py','scripts/patch_hermes_kanban_model_transition.py',
                 'docker/cont-init.d/018-devkit-kanban-boot-recovery'):
        if (ROOT/path).exists(): problems.append('Retired runtime remains: '+path)
    image = require('Dockerfile', ('018-devkit-init', 'ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2',
        'ENV HERMES_KANBAN_DISPATCH_IN_GATEWAY=false','COPY scripts/verification /opt/devkit/scripts/verification',
        'custom-skills/_lib/process_execution.py', 'check_hermes_security_contract.py'))
    if 'devkit_session_affinity' in image or 'devkit_kanban_boot_recovery' in image: problems.append('Legacy image hooks remain')
    for line in image.replace('\\\n', ' ').splitlines():
        if not line.startswith('COPY ') or '--from=' in line: continue
        parts = shlex.split(line)
        for path in [x for x in parts[1:-1] if not x.startswith('--')]:
            if not list(ROOT.glob(path)): problems.append('Dangling Docker COPY: '+path)
    require('docker/cont-init.d/018-devkit-init', ('set -eu', 'apply', '--boot', 's6-setuidgid'))
    if not '018-devkit-init' < '02-reconcile-profiles': problems.append('Wrong boot ordering')
    require('compose.yml', ('HERMES_KANBAN_DISPATCH_IN_GATEWAY: "false"', 'S6_BEHAVIOUR_IF_STAGE2_FAILS: "2"'))
    require('scripts/verify-container-runtime.ps1', ('_kanban_dispatcher_boot() is None',
        '/opt/devkit/bin/devkit_default_profile.py', 'Default DevKit Gateway served-profile contract'))
    require('scripts/devkit_default_profile.py', ('dispatch_in_gateway', 'mode=ro', 'legacy-profiles', 'fcntl',
        'rolled-back', 'prepared', 'os.fsync', 'safe_path'))
    require('update-devkit.ps1', ('Invoke-MigrationPlan','Resolve-LocalImageId','scripts/init-devkit.ps1'))
    require('scripts/init-devkit.ps1', ('--read-only', '$ImageReference'))
    if sorted(p.name for p in ROOT.glob('*.ps1')) != ['update-devkit.ps1']:
        problems.append('Root must expose only update-devkit.ps1')
    # Referenced runtime files must resolve, even after entire role directories disappear.
    for path in list((ROOT/'custom-skills').rglob('*.md')) + list((ROOT/'shared').rglob('*.md')):
        text = path.read_text(encoding='utf-8')
        for prefix, base in [('/opt/custom-skills/', ROOT/'custom-skills'), ('/opt/data/shared/', ROOT/'shared')]:
            for suffix in re.findall(re.escape(prefix)+r'([A-Za-z0-9_./-]+\.(?:py|md|json|sh))',text):
                if not (base/suffix).is_file(): problems.append(f'{path.relative_to(ROOT)}: broken runtime file {prefix}{suffix}')
    for path in [*ROOT.glob('scripts/**/*.py'),*ROOT.glob('custom-skills/**/*.py')]:
        ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    manifest = json.loads((ROOT/'scripts/domain-contracts.json').read_text(encoding='utf-8'))
    if len(manifest) < 15 or sum(map(len,manifest.values())) < 150: problems.append('Technical domain regression checks unexpectedly lost')
    policy=json.loads((ROOT/'shared/references/skill-slash-suggest-policy.json').read_text())
    active={p.parent.name for p in ROOT.glob('custom-skills/*/*/SKILL.md')}
    # Any hidden names must refer to an installed skill, not a dead workflow.
    for key in ('hidden_skills','hidden'):
        for name in policy.get(key,[]):
            if name not in active: problems.append('Retired slash policy name: '+name)
    if problems: raise SystemExit('\n'.join(problems))
    print('[PASS] DevKit catalog, image delivery, boot guard, references and domain coverage')
if __name__ == '__main__': main()
