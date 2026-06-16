#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedup_records.py
================
شناساییِ محتاطانهٔ رکوردهای «قطعاً تکراری» و ادغامِ آن‌ها.

فلسفه: نام‌های پرتکرار (محمد ابراهیمی، رضا جعفری …) می‌توانند افرادِ متفاوت
باشند؛ پس ادغامِ کور ممنوع است. فقط رکوردهایی را تکراری می‌شماریم که
«شواهدِ مضاعفِ» تطبیق داشته باشند:
   نامِ یکسان  +  (شهرِ یکسان  یا  متنِ روایتِ بسیار شبیه)
و سپس بهترین رکورد (کامل‌تر) را نگه می‌داریم و اطلاعاتِ مکمل را در آن ادغام
می‌کنیم.
"""
import json
import os
import re
import datetime
from collections import defaultdict
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'assets', 'data')
SRC = os.path.join(DATA, 'javidnam.full.json')
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dedup_report.json')

FA = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def norm_name(n):
    if not n:
        return ''
    n = n.replace('\u200c', ' ').replace('ي', 'ی').replace('ك', 'ک')
    return re.sub(r'\s+', ' ', n).strip()


def norm_text(s):
    if not s:
        return ''
    s = s.translate(FA).replace('\u200c', ' ').replace('ي', 'ی').replace('ك', 'ک')
    s = re.sub(r'[#@_]', ' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def completeness(p):
    """امتیازِ کاملیِ یک رکورد (هر چه بیشتر، بهتر برای نگه‌داشتن)."""
    score = 0
    for k in ('ne', 'g', 'a', 'by', 'dj', 'dg', 'c', 'pr', 'ca', 'oc', 's', 'se', 'ph'):
        v = p.get(k)
        if v not in (None, '', [], 0):
            score += 1
    score += len(p.get('s') or '') / 200.0
    if (p.get('v') == 'documented'):
        score += 0.5
    if p.get('nt'):
        score += 0.3
    return score


def merge_into(keeper, other):
    """فیلدهای خالیِ keeper را از other پر کن (بدونِ بازنویسیِ داده‌های موجود)."""
    for k, v in other.items():
        if k in ('id', 'e'):
            continue
        if v in (None, '', [], 0):
            continue
        cur = keeper.get(k)
        if cur in (None, '', [], 0):
            keeper[k] = v
        elif k == 'src' and isinstance(cur, list) and isinstance(v, list):
            keeper[k] = sorted(set(cur) | set(v))


def main():
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)
    people = data['people']

    by_name = defaultdict(list)
    for p in people:
        by_name[norm_name(p.get('n'))].append(p)

    to_remove = set()
    merges = []

    for name, group in by_name.items():
        if not name or len(group) < 2:
            continue
        # مقایسهٔ زوجیِ رکوردهای هم‌نام
        used = set()
        for i in range(len(group)):
            if id(group[i]) in used or id(group[i]) in to_remove:
                continue
            cluster = [group[i]]
            for j in range(i + 1, len(group)):
                if id(group[j]) in to_remove:
                    continue
                a, b = group[i], group[j]
                ca, cb = (a.get('c') or '').strip(), (b.get('c') or '').strip()
                sa, sb = norm_text(a.get('s')), norm_text(b.get('s'))
                # شرطِ تکراریِ قطعی:
                same_city = ca and cb and (ca in cb or cb in ca or similar(ca, cb) > 0.7)
                story_sim = similar(sa, sb) if (sa and sb) else 0
                # تطبیقِ تاریخِ روز/ماه (روزِ یکسانِ جانباختن)
                da = (a.get('dj') or '').translate(FA)
                db = (b.get('dj') or '').translate(FA)
                md_a = re.search(r'/(\d{1,2})/(\d{1,2})', da)
                md_b = re.search(r'/(\d{1,2})/(\d{1,2})', db)
                same_md = md_a and md_b and md_a.group(0) == md_b.group(0)

                same_age = a.get('a') and b.get('a') and a.get('a') == b.get('a')
                same_by = a.get('by') and b.get('by') and a.get('by') == b.get('by')
                long_story = len(sa) > 25 and len(sb) > 25

                is_dup = False
                # شواهدِ بسیار سخت‌گیرانه (پرهیز از ادغامِ کور):
                # ۱) متنِ روایت تقریباً یکسان → قطعاً همان رکورد
                if long_story and story_sim > 0.82:
                    is_dup = True
                # ۲) نام+شهر+تاریخِ کامل یکسان + روایتِ نسبتاً مشابه
                elif same_city and same_md and long_story and story_sim > 0.6:
                    is_dup = True
                # ۳) نام+شهر+تاریخِ کامل یکسان + سن یا سالِ تولدِ یکسان (هویتِ یکسان)
                elif same_city and same_md and (same_age or same_by):
                    is_dup = True
                # ۴) یکی از دو رکورد روایتِ معنادار ندارد ولی نام+شهر+تاریخِ دقیق یکسان است
                elif same_city and same_md and (not sa or not sb):
                    is_dup = True

                if is_dup:
                    cluster.append(b)

            if len(cluster) > 1:
                # بهترین رکورد را نگه دار
                keeper = max(cluster, key=completeness)
                for rec in cluster:
                    if rec is keeper:
                        continue
                    merge_into(keeper, rec)
                    to_remove.add(id(rec))
                    used.add(id(rec))
                    merges.append({
                        'name': name,
                        'kept_id': keeper['id'], 'kept_event': keeper['e'],
                        'removed_id': rec['id'], 'removed_event': rec['e'],
                        'city': keeper.get('c'),
                    })

    new_people = [p for p in people if id(p) not in to_remove]
    data['people'] = new_people
    data['meta']['total'] = len(new_people)
    from collections import Counter
    cnt = Counter(p['e'] for p in new_people)
    data['meta']['by_event'] = {k: cnt.get(k, 0) for k in data['events'].keys()}
    data['meta']['generated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    report = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'removed': len(to_remove),
        'remaining_total': len(new_people),
        'merges': merges,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f'✅ رکوردهای تکراریِ قطعی که ادغام/حذف شد: {len(to_remove)}')
    print(f'   مجموعِ نهایی: {len(new_people)}')
    print(f'📄 گزارش: {REPORT}')


if __name__ == '__main__':
    main()
