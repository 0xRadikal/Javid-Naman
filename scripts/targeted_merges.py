#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeted_merges.py
==================
Apply a small set of HUMAN-CONFIRMED merges that the automated, conservative
pass intentionally left apart (because they relied on a cross-name same-image
bridge that — in general — is unsafe, but which the project owner has personally
verified for these specific records).

Each merge here is explicit and auditable. We KEEP the most-complete record,
complement empty fields from the duplicate, union sources, and drop the dup.
Reads  /tmp/merged_full.json   (output of dedup_advanced.py)
Writes assets/data/javidnam.full.json
"""
import json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = '/tmp/merged_full.json'
DST = os.path.join(ROOT, 'assets/data/javidnam.full.json')

# (keep_id, dup_id) — keep_id is the canonical (most complete) record.
# Justification kept inline for the audit trail.
MERGES = [
    # The two "پانته آ شیاسی" records (same name, same city Karaj). The dup has
    # no story; keep the full one (age 24, correct per project owner).
    ('jvn_77df34d02f', 'jvn_47ae00e6b3'),
    # 'مهدی بقائی' == 'Mehdi Baghaei' (Persian vs Latin transliteration), same city.
    ('jvn_189a8a3443', 'jvn_90092c53af'),
]

MERGE_FIELDS = ['n', 'ne', 'e', 'g', 'a', 'by', 'dj', 'dg', 'c', 'pr', 'ca',
                'oc', 's', 'se', 'ph', 'ml', 'nt', 'v', 'sl', 'src']


def empty(v):
    return v in (None, '', [], 0)


def main():
    data = json.load(open(SRC))
    by_id = {p['id']: p for p in data['people']}
    removed = set()
    audit = []
    for keep, dup in MERGES:
        if keep not in by_id or dup not in by_id:
            print('skip (missing):', keep, dup)
            continue
        base, o = by_id[keep], by_id[dup]
        changes = {}
        for k in MERGE_FIELDS:
            if k in ('src', 'ml'):
                merged = list(base.get(k) or [])
                for s in (o.get(k) or []):
                    if s not in merged:
                        merged.append(s)
                base[k] = merged
                continue
            if empty(base.get(k)) and not empty(o.get(k)):
                changes[k] = {'from': base.get(k), 'to': o.get(k)}
                base[k] = o.get(k)
        if o.get('nt'):
            base['nt'] = base.get('nt') or 1
        removed.add(dup)
        audit.append({'kept': keep, 'kept_name': base.get('n'),
                      'dup': dup, 'dup_name': o.get('n'), 'filled': changes})
        print(f'merged {dup} ({o.get("n")}) -> {keep} ({base.get("n")}); filled {list(changes)}')

    data['people'] = [p for p in data['people'] if p['id'] not in removed]
    json.dump(data, open(DST, 'w'), ensure_ascii=False, indent=1)
    json.dump(audit, open(os.path.join(ROOT, 'scripts/targeted_merges_report.json'),
                          'w'), ensure_ascii=False, indent=1)
    print(f'final records: {len(data["people"])}')


if __name__ == '__main__':
    main()
