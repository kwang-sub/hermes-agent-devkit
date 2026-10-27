#!/usr/bin/env python3
"""Retained technical documentation guards; role routing is deliberately excluded."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    manifest=json.loads((ROOT/'scripts/domain-contracts.json').read_text(encoding='utf-8'))
    failures=[]
    for relative, terms in manifest.items():
        path=ROOT/relative
        if not path.is_file(): failures.append('Missing technical contract: '+relative);continue
        text=path.read_text(encoding='utf-8')
        for term in terms:
            if term not in text: failures.append(f'{relative}: missing {term}')
    if failures: raise SystemExit('\n'.join(failures))
    print(f'[PASS] {len(manifest)} domain policy/source contracts retained')
if __name__=='__main__': main()
