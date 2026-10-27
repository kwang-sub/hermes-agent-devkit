#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    obj=json.loads((ROOT/'custom-skills/shared/capability-lifecycle.json').read_text(encoding='utf-8'))
    assert obj['version']==2
    seen=set()
    for entry in obj['capabilities']:
        name=entry['name']; assert name not in seen; seen.add(name)
        assert (ROOT/'custom-skills/shared'/name/'SKILL.md').is_file(),name
        assert not any(key in entry for key in ('strict_pin','planner_required','coder_required','reviewer_required'))
        assert isinstance(entry['approval_required'],bool)
    print('[PASS] Role-independent lazy capability registry')
if __name__=='__main__': main()
