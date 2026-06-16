#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedup_advanced.py
=================
Intelligent, multi-signal duplicate detection & merge for javidnam.full.json.

Signals combined (NO single blind signal is trusted alone):
  1. VISUAL   : perceptual-hash clusters from scripts/photo_hashes.json
                - exact sha1 match            -> same image bytes
                - phash/dhash Hamming <= TH    -> visually same photo (re-host/crop)
                - face_phash Hamming <= FTH    -> same face even if framing differs
  2. NAME     : Persian-normalized fuzzy name match
                - equality after normalization
                - prefix / subset (رسول ضیایی  ⊂  رسول ضیایی زردخشویی)
                - token-set / SequenceMatcher ratio
  3. CONTEXT  : same city (normalized), same death date, story overlap, age/birth_year

Decision (high-confidence duplicate) requires a STRONG primary signal corroborated
by at least one secondary signal, so we never merge on a coincidence:

  STRONG primary  = (visual_same) OR (name_equal) OR (name_subset)
  CORROBORATION   = same_city OR name_overlap OR story_overlap OR same_birth_year
                    OR same_death_date

  - visual_same + ANY corroboration            -> duplicate  (covers Pantea/Taha)
  - name_equal  + (same_city OR same_by OR vis) -> duplicate
  - name_subset + (same_city OR vis OR same_by) -> duplicate  (covers Ziaei)

Merge = pick the most-complete record as base, then COMPLEMENT every empty field
from the others, choose the *best* conflicting value (e.g. larger documented age
when birth years suggest it, longer story, real face photo over wrong photo, etc.),
and UNION all sources.

Outputs:
  - rewrites assets/data/javidnam.full.json (merged)
  - scripts/dedup_advanced_report.json (full audit of every merge)
A backup is written to /home/user/Javid-Naman/scripts/.full_before_dedup_adv.json
and ~/jv_full_before_dedup_adv.json (persistent).
"""
import json, os, re, sys, shutil
from collections import defaultdict
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, 'assets/data/javidnam.full.json')
HASHES = os.path.join(ROOT, 'scripts/photo_hashes.json')
REPORT = os.path.join(ROOT, 'scripts/dedup_advanced_report.json')

# ---- thresholds (Hamming distance on 16x16 hashes = 256 bits) ----
# We separate two visual confidence levels:
#   SAME_IMG  : the SAME picture (re-hosted/re-encoded/cropped a little). Strong
#               enough to stand on its own *with light corroboration*.
#   SAME_FACE : plausibly the same person but a DIFFERENT photo. Treated only as
#               CORROBORATION for a name signal, never alone (avoids blind errors).
PHASH_SAME_IMG = 12   # phash/dhash <= 12  -> same picture
FACE_SAME_IMG  = 18   # face crop nearly identical -> same picture (cropped)
FACE_CORROB    = 78   # face <= 78 -> plausibly same person, corroboration only
NAME_RATIO = 0.88     # SequenceMatcher ratio for fuzzy name equality
STORY_OVERLAP = 0.6

# ----------------- Persian normalization -----------------
FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
def fa_num(s):
    return (s or '').translate(FA_DIGITS)

def norm_text(s):
    if not s:
        return ''
    s = fa_num(s)
    s = s.replace('\u200c', ' ').replace('\u200f', '').replace('\u200e', '')
    s = s.replace('ي', 'ی').replace('ك', 'ک').replace('ﻩ', 'ه').replace('ة', 'ه')
    s = s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ٱ', 'ا')
    s = re.sub(r'[ًٌٍَُِّْ]', '', s)         # harakat
    s = re.sub(r'[^\w\u0600-\u06FF ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# honorific / filler tokens to drop from names
NAME_STOP = {'شهید', 'مرحوم', 'زنده', 'یاد', 'سید', 'سیده', 'حاج', 'دکتر', 'مهندس'}

def norm_name(s):
    s = norm_text(s)
    toks = [t for t in s.split() if t not in NAME_STOP]
    return ' '.join(toks)

def name_tokens(s):
    return [t for t in norm_name(s).split() if len(t) > 1]

def ratio(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def is_subset_name(a, b):
    """True if one normalized name's token list is a contiguous prefix/subset of the other
       (handles family-name extensions: 'رسول ضیایی' ⊂ 'رسول ضیایی زردخشویی')."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    short, lng = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(short) < 2:           # single-token "subset" is too weak
        return False
    # prefix match: short is the leading tokens of long
    if lng[:len(short)] == short:
        return True
    # subset match: every short token present in long, same order
    it = iter(lng)
    if all(tok in it for tok in short):
        return True
    return False

def hamming_hex(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count('1')
    except ValueError:
        return 999

def death_md(p):
    """month/day signature from date_jalali (ignore year so 18-Dey across years still groups)."""
    dj = fa_num(p.get('dj') or '')
    m = re.search(r'(\d{3,4})[/\-](\d{1,2})[/\-](\d{1,2})', dj)
    if m:
        return (int(m.group(2)), int(m.group(3)))
    return None

def death_full(p):
    dj = fa_num(p.get('dj') or '')
    m = re.search(r'(\d{3,4})[/\-](\d{1,2})[/\-](\d{1,2})', dj)
    return m.group(0) if m else None


# ----------------- completeness scoring -----------------
WEIGHT = {'n': 1, 's': 6, 'ph': 4, 'dj': 3, 'c': 2, 'a': 1, 'by': 1, 'ne': 1,
          'se': 3, 'pr': 1, 'ca': 1, 'oc': 1, 'g': 1}
def completeness(p):
    sc = 0
    for k, w in WEIGHT.items():
        v = p.get(k)
        if v not in (None, '', [], 0):
            sc += w
    sc += min(len(p.get('s') or ''), 600) / 100.0    # reward longer story
    sc += len(p.get('src') or [])
    if p.get('nt'):
        sc += 5
    return sc


def main():
    data = json.load(open(FULL))
    ppl = data['people']
    by_id = {p['id']: p for p in ppl}
    print('records:', len(ppl))

    # backup
    shutil.copy(FULL, os.path.join(ROOT, 'scripts/.full_before_dedup_adv.json'))
    shutil.copy(FULL, os.path.expanduser('~/jv_full_before_dedup_adv.json'))

    # ---- load visual fingerprints ----
    hashes = {}
    if os.path.exists(HASHES):
        hashes = json.load(open(HASHES))
    # map id -> visual record
    id2vis = {}
    for url, rec in hashes.items():
        if not rec.get('ok'):
            continue
        for pid in rec.get('ids', []):
            id2vis[pid] = rec
    print('records with usable visual fingerprint:', len(id2vis))

    # ---- candidate generation ----
    # 1) blocking by normalized first token of name + by city, to limit comparisons
    blocks = defaultdict(list)
    for p in ppl:
        toks = name_tokens(p.get('n'))
        key = toks[0] if toks else ''
        blocks[key].append(p['id'])
        # also block by city to catch cross-name visual dups in same city
        c = norm_text(p.get('c'))
        if c:
            blocks['CITY:' + c.split()[0]].append(p['id'])

    # 2) visual blocks: group ids that share sha1 or near phash
    #    (do a cheap bucket by first 4 hex of phash, plus sha1 exact)
    vis_blocks = defaultdict(set)
    for pid, rec in id2vis.items():
        if rec.get('sha1'):
            vis_blocks['SHA:' + rec['sha1']].add(pid)
        ph = rec.get('phash')
        if ph:
            vis_blocks['PHB:' + ph[:3]].add(pid)
            vis_blocks['PHB2:' + ph[3:6]].add(pid)
        fh = rec.get('face_phash')
        if fh:
            vis_blocks['FB:' + fh[:3]].add(pid)

    # build candidate pairs
    cand = set()
    for key, ids in blocks.items():
        ids = list(set(ids))
        if len(ids) > 800:      # skip giant generic blocks
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                cand.add((a, b) if a < b else (b, a))
    for key, ids in vis_blocks.items():
        ids = list(ids)
        if len(ids) > 400:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                cand.add((a, b) if a < b else (b, a))
    print('candidate pairs:', len(cand))

    # ---- rarity statistics (so common dates/cities don't act as evidence) ----
    DM_FREQ = defaultdict(int)
    CITY_FREQ = defaultdict(int)
    for p in ppl:
        dm = death_md(p)
        if dm:
            DM_FREQ[dm] += 1
        ck = norm_text(p.get('c'))
        if ck:
            CITY_FREQ[ck] += 1

    # ---- scoring each candidate ----
    def visual(a, b):
        """Return (level, why):
             level 2 = SAME PICTURE (strong)
             level 1 = same person, different photo (corroboration only)
             level 0 = no visual link / unknown
        """
        ra, rb = id2vis.get(a), id2vis.get(b)
        if not ra or not rb:
            return 0, ''
        if ra.get('sha1') and ra['sha1'] == rb.get('sha1'):
            return 2, 'sha1'
        d_ph = hamming_hex(ra.get('phash'), rb.get('phash'))
        d_dh = hamming_hex(ra.get('dhash'), rb.get('dhash'))
        if d_ph <= PHASH_SAME_IMG or d_dh <= PHASH_SAME_IMG:
            return 2, f'img(ph{d_ph}/dh{d_dh})'
        d_f = 999
        if ra.get('face_phash') and rb.get('face_phash'):
            d_f = hamming_hex(ra['face_phash'], rb['face_phash'])
            if d_f <= FACE_SAME_IMG:
                return 2, f'facecrop({d_f})'
            if d_f <= FACE_CORROB:
                return 1, f'face~{d_f}'
        return 0, ''

    dup_pairs = []
    for a, b in cand:
        pa, pb = by_id[a], by_id[b]
        na, nb = norm_name(pa.get('n')), norm_name(pb.get('n'))
        vlevel, vwhy = visual(a, b)
        same_img = vlevel >= 2
        face_corrob = vlevel >= 1
        name_eq = na and na == nb
        name_sub = is_subset_name(pa.get('n'), pb.get('n'))
        name_fuzzy = ratio(na, nb) >= NAME_RATIO
        name_overlap = bool(set(name_tokens(pa.get('n'))) & set(name_tokens(pb.get('n'))))
        same_city = norm_text(pa.get('c')) and norm_text(pa.get('c')) == norm_text(pb.get('c'))
        # looser city: share a meaningful token (>=3 chars)
        ctoks_a = {t for t in norm_text(pa.get('c')).split() if len(t) >= 3}
        ctoks_b = {t for t in norm_text(pb.get('c')).split() if len(t) >= 3}
        city_tok = bool(ctoks_a & ctoks_b)
        sa, sb = norm_text(pa.get('s')), norm_text(pb.get('s'))
        story_ov = ratio(sa, sb) >= STORY_OVERLAP if (len(sa) > 40 and len(sb) > 40) else False
        same_by = pa.get('by') and pa.get('by') == pb.get('by')
        same_dm = death_md(pa) and death_md(pa) == death_md(pb)
        same_age = pa.get('a') and pa.get('a') == pb.get('a')

        # --- RARITY-AWARE corroboration -------------------------------------
        # A shared (month,day) like 18-Dey-1404 covers hundreds of records, so it
        # is NOT discriminating. Same for huge cities (Tehran). Only treat them as
        # corroboration when they are *rare* in the dataset.
        dm = death_md(pa)
        rare_date = same_dm and DM_FREQ.get(dm, 0) <= 25
        ckey = norm_text(pa.get('c'))
        rare_city = same_city and CITY_FREQ.get(ckey, 0) <= 40
        # strong, person-specific corroborations only:
        strong_corrob = name_overlap or story_ov or same_by or rare_date or rare_city or same_age

        reason = None
        conf = 0
        # ---- Tier A: SAME PICTURE + a person-specific corroboration ----
        #      (a coincidental same-image needs name/birthyear/story/rare-context)
        if same_img and (name_overlap or same_by or story_ov or rare_date or rare_city):
            reason = f'SAME_IMG[{vwhy}]+corrob'; conf = 0.97
        # ---- Tier B: name equality + any context ----
        elif name_eq and (same_city or city_tok or same_by or same_img or same_dm or same_age):
            reason = 'NAME_EQ+ctx'; conf = 0.92
        # ---- Tier C: family-name extension (subset) + context ----
        elif name_sub and (same_city or city_tok or same_img or same_by or rare_date or same_age):
            reason = 'NAME_SUBSET+ctx'; conf = 0.9
        # ---- Tier D: fuzzy name + same city + a second independent signal ----
        elif name_fuzzy and same_city and (same_by or rare_date or story_ov or same_img):
            reason = 'NAME_FUZZY+strong_ctx'; conf = 0.85
        # ---- Tier E: near-identical long story + name overlap ----
        elif story_ov and name_overlap:
            reason = 'STORY+name'; conf = 0.84

        if reason:
            dup_pairs.append((a, b, reason, conf, vwhy))

    print('high-confidence duplicate pairs:', len(dup_pairs))

    # ---- build graph of high-confidence pairs ----
    pair_info = {}
    adj = defaultdict(set)
    for a, b, reason, conf, vwhy in dup_pairs:
        adj[a].add(b)
        adj[b].add(a)
        pair_info[(a, b)] = (reason, conf)
        pair_info[(b, a)] = (reason, conf)

    # ---- raw connected components (may over-chain) ----
    seen = set()
    raw_components = []
    for node in list(adj):
        if node in seen:
            continue
        stack = [node]; comp = []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x)
            stack.extend(adj[x] - seen)
        raw_components.append(comp)

    def sig_name(pid):
        return norm_name(by_id[pid].get('n'))

    def sig_img(pid):
        v = id2vis.get(pid) or {}
        return v.get('sha1')

    # ---- CHAIN-RESISTANT validation: split components that lack a shared anchor.
    #      A valid cluster must be either:
    #        (i) a CLIQUE-ish group sharing a dominant normalized name, OR
    #       (ii) sharing the exact same image (sha1), OR
    #      (iii) connected ONLY via name-equality/subset links (name-family).
    #      Components held together by loose visual/fuzzy links across DIFFERENT
    #      names are broken back into name-coherent sub-clusters to avoid blind
    #      over-merging of distinct people.
    NAME_LINK = {'NAME_EQ+ctx', 'NAME_SUBSET+ctx', 'NAME_FUZZY+strong_ctx'}
    final_clusters = []
    for comp in raw_components:
        if len(comp) < 2:
            continue
        if len(comp) <= 4:
            # small component: trust direct links, keep as one cluster
            final_clusters.append(comp)
            continue
        # LARGE component (>4): too risky to keep whole -> re-cluster inside it
        # using only STRONG anchors: shared exact image OR shared name family.
        sub_parent = {}
        def f2(x):
            sub_parent.setdefault(x, x)
            while sub_parent[x] != x:
                sub_parent[x] = sub_parent[sub_parent[x]]; x = sub_parent[x]
            return x
        def u2(a, b):
            ra, rb = f2(a), f2(b)
            if ra != rb: sub_parent[ra] = rb
        for x in comp:
            f2(x)
        # re-link only on strong, person-specific evidence
        comp_set = set(comp)
        for x in comp:
            for y in adj[x]:
                if y not in comp_set or y <= x:
                    continue
                r = pair_info.get((x, y), ('', 0))[0]
                strong = (
                    sig_img(x) and sig_img(x) == sig_img(y)          # exact same image
                    or (r in NAME_LINK)                               # name family link
                )
                if strong:
                    u2(x, y)
        sub = defaultdict(list)
        for x in comp:
            sub[f2(x)].append(x)
        for grp in sub.values():
            if len(grp) >= 2:
                final_clusters.append(grp)

    clusters = {i: c for i, c in enumerate(final_clusters)}
    print('duplicate clusters:', len(clusters),
          'records involved:', sum(len(v) for v in clusters.values()),
          '| raw components:', len(raw_components))

    # ---- merge each cluster ----
    MERGE_FIELDS = ['n', 'ne', 'e', 'g', 'a', 'by', 'dj', 'dg', 'c', 'pr', 'ca',
                    'oc', 's', 'se', 'ph', 'ml', 'nt', 'v', 'sl', 'src']
    report = []
    removed = set()
    for root, ids in clusters.items():
        recs = sorted([by_id[i] for i in ids], key=completeness, reverse=True)
        base = dict(recs[0])          # most complete
        others = recs[1:]
        audit = {'kept_id': base['id'], 'kept_name': base.get('n'),
                 'merged_ids': [o['id'] for o in others],
                 'merged_names': [o.get('n') for o in others],
                 'reasons': sorted({pair_info[k][0] for k in pair_info
                                    if k[0] in ids and k[1] in ids}),
                 'changes': {}}
        for o in others:
            for k in MERGE_FIELDS:
                bv, ov = base.get(k), o.get(k)
                if k == 'src':
                    merged = list(base.get('src') or [])
                    for s in (o.get('src') or []):
                        if s not in merged:
                            merged.append(s)
                    base['src'] = merged
                    continue
                if k == 'ml':
                    merged = list(base.get('ml') or [])
                    for s in (o.get('ml') or []):
                        if s not in merged:
                            merged.append(s)
                    base['ml'] = merged
                    continue
                empty_b = bv in (None, '', [], 0)
                empty_o = ov in (None, '', [], 0)
                if empty_b and not empty_o:
                    base[k] = ov
                    audit['changes'][k] = {'from': bv, 'to': ov, 'src': o['id']}
                elif not empty_b and not empty_o and bv != ov:
                    # conflict resolution
                    if k == 's' or k == 'se':
                        if len(str(ov)) > len(str(bv)):
                            audit['changes'][k] = {'from': bv[:40], 'to': ov[:40], 'src': o['id']}
                            base[k] = ov
                    elif k == 'a':
                        # Age conflict: KEEP the value from the most-complete record
                        # (it is the base, generally the better-documented source).
                        # We do NOT blindly guess; just log the discarded value so a
                        # human can review. (e.g. Pantea base=24 kept over 23.)
                        audit.setdefault('age_conflicts', []).append(
                            {'kept': bv, 'discarded': ov, 'src': o['id']})
                    elif k == 'nt':
                        if ov and not bv:
                            base[k] = ov
                    elif k == 'ph':
                        # keep base photo (it came from most-complete record); note alt
                        audit.setdefault('alt_photos', []).append(ov)
                    # else keep base value
        # notable if any was notable
        if any(o.get('nt') for o in others):
            base['nt'] = base.get('nt') or 1
        report.append(audit)
        for o in others:
            removed.add(o['id'])
        by_id[base['id']] = base

    # rebuild people list
    new_people = []
    for p in ppl:
        if p['id'] in removed:
            continue
        new_people.append(by_id[p['id']])
    print(f'removed {len(removed)} duplicate records -> {len(new_people)} remain')

    # ---- REVIEW LIST: records that share the EXACT same image but have
    #      UNRELATED names. These are NOT auto-merged (could be siblings sharing
    #      a family photo, or a wrong photo on one record). Flagged for a human.
    sha_groups = defaultdict(set)
    for url, rec in hashes.items():
        if rec.get('ok') and rec.get('sha1'):
            for pid in rec.get('ids', []):
                if pid in by_id:
                    sha_groups[rec['sha1']].add(pid)
    review = []
    for s, ids in sha_groups.items():
        ids = [i for i in ids if i not in removed]
        if len(ids) < 2:
            continue
        names = [by_id[i].get('n', '') for i in ids]
        allrel = all(
            (norm_name(names[i]) == norm_name(names[j]) or
             is_subset_name(names[i], names[j]) or
             ratio(norm_name(names[i]), norm_name(names[j])) >= NAME_RATIO)
            for i in range(len(names)) for j in range(i + 1, len(names)))
        if not allrel:
            review.append({'ids': ids, 'names': names,
                           'cities': [by_id[i].get('c') for i in ids]})
    print(f'review groups (same image, unrelated names — manual check): {len(review)}')

    dry = '--dry' in sys.argv
    json.dump({'clusters': len(clusters), 'removed': len(removed),
               'remaining': len(new_people), 'dry_run': dry,
               'review_same_image_diff_name': review,
               'merges': report}, open(REPORT, 'w'), ensure_ascii=False, indent=1)
    print('wrote report', REPORT)
    if dry:
        # print clusters with >2 members or cross-name for review
        print('\n--- DRY RUN: sample clusters ---')
        shown = 0
        for a in report:
            names = set([a['kept_name']] + a['merged_names'])
            if len(names) > 1 or len(a['merged_ids']) >= 2:
                print(' KEEP', a['kept_name'], '<=', a['merged_names'],
                      '| reasons:', a['reasons'],
                      ('| AGE_CONFLICT ' + str(a['age_conflicts']) if a.get('age_conflicts') else ''))
                shown += 1
            if shown >= 60:
                break
        print(f'(showed {shown} multi/cross-name clusters of {len(clusters)} total)')
        return
    data['people'] = new_people
    json.dump(data, open(FULL, 'w'), ensure_ascii=False, indent=1)
    print('wrote', FULL)


if __name__ == '__main__':
    main()
