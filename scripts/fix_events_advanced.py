#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_events_advanced.py
======================
اصلاحِ هوشمند، حرفه‌ای و محافظه‌کارانهٔ انتسابِ رویداد به جاویدنامان،
روی منبعِ حقیقت  assets/data/javidnam.full.json .

اهداف:
  ۱) افزودنِ رویدادهای تازه به schema:
        - chain_murders_77  (قتل‌های زنجیره‌ای پاییز ۱۳۷۷)
        - dey_1402          (اعتراضات دی ۱۴۰۲)
        - dey_1403          (اعتراضات دی ۱۴۰۳)
        - needs_review      (رکوردهای مشکوک/نامعتبر)
  ۲) جابه‌جاییِ رکوردهای اشتباه‌ثبت‌شده، بر اساسِ «سالِ جانباختن».

  ⚠️ درسِ مهم از تکرارِ اول:
     سالی که در روایت می‌آید همیشه «سالِ جانباختن» نیست؛ ممکن است سالِ تولد
     («متولد ۱۳۷۷») یا سالِ ورودِ دانشگاه («ورودی ۱۴۰۳») باشد. بنابراین:
        - منبعِ اصلیِ «تاریخِ جانباختن»  = date_jalali (با ماه/روز).
        - روایت فقط زمانی سالِ جانباختن را تعیین می‌کند که سال «چسبیده» به
          واژه‌های جانباختن/کشته یا به «دی‌ماهِ سال X» آمده باشد.
        - سالِ پس از «متولد/تولد/زاده/ورودی/سن» = سالِ جانباختن نیست و کنار
          گذاشته می‌شود.
"""
import json
import os
import re
import datetime
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'assets', 'data')
SRC = os.path.join(DATA, 'javidnam.full.json')
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'event_fix_report_v3.json')

FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def fa2en(s):
    return s.translate(FA_DIGITS) if s else s


YEAR_RE = re.compile(r'(13[0-9]{2}|14[0-9]{2})')
DEY_RE = re.compile(r'(۱۸|۱۹|18|19)\s*دی')

# واژه‌هایی که سالِ پیش/پس‌ازشان «سالِ جانباختن نیست» (تولد/ورود/سن)
NON_DEATH_BEFORE = re.compile(
    r'(متولد|تولد|زاده|زادهٔ|ورودی|ورود|سال\s*تولد|سن|ساله|اردیبهشت\s*$)'
)
# واژه‌هایی که اگر «پس از» سال بیایند، آن سال = تولد/زندگی‌نامه است
NON_DEATH_AFTER = re.compile(
    r'^\s*(به\s*دنیا|متولد|تولد|زاده|–|-|تا\s|د\s*دنیا)'
)
# واژه‌هایی که سالِ نزدیک‌شان «سالِ جانباختن» است
DEATH_WORDS = re.compile(
    r'(جان[\s‌]?باخت|جان[\s‌]?فدا|کشته|شهید\s*شد|اعدام|به[\s‌]?قتل|به\s*خاک\s*سپرده|تیرباران)'
)


def death_year_from_story(text):
    """
    استخراجِ «سالِ جانباختن» از روایت، با حساسیتِ بالا به سالِ تولد/زندگی‌نامه.
    خروجی: (year, confidence) یا (None, None).
      - high  : الگوی «دی[‌ماه] <سال>» که نه پیش‌اش تولد باشد نه پس‌اش زندگی‌نامه،
                و در نزدیکی واژهٔ جانباختن/تاریخِ رویداد.
      - medium: تنها یک سالِ معتبرِ غیرِتولدی، نزدیک واژهٔ جانباختن.
    """
    if not text:
        return None, None
    t = fa2en(text)

    # ۱) الگوی صریحِ «دی [ماه] <سال>»
    for m in re.finditer(r'دی[\s‌]*(?:ماه|مَاه)?[\s‌]*(13\d{2}|14\d{2})', t):
        y = int(m.group(1))
        if not (1357 <= y <= 1405):
            continue
        pre = t[max(0, m.start() - 18):m.start()]
        post = t[m.end():m.end() + 12]
        # رد اگر بافتِ تولد/زندگی‌نامه باشد (مثل «۱۵ دی ۱۳۸۸ به دنیا آمد» یا
        # «(۱۵ دی ۱۳۷۸ – ۳۰ شهریور ۱۴۰۱)»)
        if NON_DEATH_BEFORE.search(pre) or NON_DEATH_AFTER.search(post):
            continue
        return y, 'high'

    # ۲) همهٔ سال‌ها با بافتِ پیش از آن
    candidates = []
    for mt in YEAR_RE.finditer(t):
        y = int(mt.group(1))
        if not (1357 <= y <= 1405):
            continue
        pre = t[max(0, mt.start() - 16):mt.start()]
        post = t[mt.end():mt.end() + 12]
        if NON_DEATH_BEFORE.search(pre) or NON_DEATH_AFTER.search(post):
            continue
        candidates.append((y, mt.start()))

    if not candidates:
        return None, None

    uniq_years = set(y for y, _ in candidates)
    if len(uniq_years) == 1:
        y = next(iter(uniq_years))
        for yy, pos in candidates:
            window = t[max(0, pos - 35):pos + 10]
            if DEATH_WORDS.search(window):
                return y, 'medium'
        return y, 'weak'

    return None, None


def dj_year(rec):
    dj = fa2en(rec.get('dj') or '')
    m = re.match(r'(1[34]\d\d)', dj)
    return int(m.group(1)) if m else None


def dj_has_month(rec):
    """آیا date_jalali ماه/روزِ معتبر دارد؟ (مثلِ ۱۴۰۴/۱۰/۱۸)"""
    dj = fa2en(rec.get('dj') or '')
    m = re.match(r'1[34]\d\d/(\d{1,2})/(\d{1,2})', dj)
    if not m:
        return False
    mo = int(m.group(1))
    return 1 <= mo <= 12


# ---------------------------------------------------------------------------
NEW_EVENTS = {
    'chain_murders_77': {
        'title': 'قتل‌های زنجیره‌ای ۱۳۷۷',
        'title_en': 'Chain Murders of 1998',
        'year_fa': '۱۳۷۷', 'year': 1377, 'order': 15, 'category': 'state_killing',
    },
    'dey_1402': {
        'title': 'اعتراضات دی ۱۴۰۲',
        'title_en': 'December 2023 Protests',
        'year_fa': '۱۴۰۲', 'year': 1402, 'order': 16, 'category': 'uprising',
    },
    'dey_1403': {
        'title': 'اعتراضات دی ۱۴۰۳',
        'title_en': 'December 2024 Protests',
        'year_fa': '۱۴۰۳', 'year': 1403, 'order': 17, 'category': 'uprising',
    },
    'needs_review': {
        'title': 'در دستِ بازبینی',
        'title_en': 'Pending Review',
        'year_fa': '—', 'year': 0, 'order': 99, 'category': 'review',
    },
}

YEAR_TO_EVENT = {
    1377: 'chain_murders_77', 1378: 'kuye_daneshgah_78', 1388: 'green_88',
    1396: 'dey_96', 1397: 'mordad_97', 1398: 'aban_98', 1400: 'khuzestan_1400',
    1401: 'khizesh_1401', 1402: 'dey_1402', 1403: 'dey_1403', 1404: 'khizesh_1404',
}

YEAR_BASED_EVENTS = {
    'kuye_daneshgah_78', 'green_88', 'dey_96', 'mordad_97', 'aban_98',
    'khuzestan_1400', 'khizesh_1401', 'khizesh_1404',
    'chain_murders_77', 'dey_1402', 'dey_1403',
}

JUNK_PATTERNS = [re.compile(p) for p in [
    r'تام\s*مورلی', r'محل\s*دفن\s*او\s*فاضلاب', r'وحوش\s*انگلیسی',
    r'حمله\s*انگلیسی', r'هواپیمای\s*فوکر',
]]


def is_junk(rec):
    s = (rec.get('s') or '')
    for pat in JUNK_PATTERNS:
        if pat.search(s):
            return True
    y = dj_year(rec)
    if y is not None and y < 1357:   # تاریخِ جانباختنِ پیش از انقلاب در رویدادِ اعتراضی
        return True
    return False


def decide_target(rec):
    """کلیدِ رویدادِ درست + دلیل + اطمینان. تغییری نباشد → event فعلی."""
    cur = rec.get('e')
    s = rec.get('s') or ''

    # ۰) نامعتبر/مزاح
    if is_junk(rec):
        return 'needs_review', 'junk_or_invalid', 'high'

    # رویدادهای تخصصی دست‌نخورده می‌مانند
    if cur not in YEAR_BASED_EVENTS:
        return cur, 'protected_event', 'n/a'

    djy = dj_year(rec)
    has_month = dj_has_month(rec)
    sy, sconf = death_year_from_story(s)
    mentions_dey = bool(re.search(r'دی', fa2en(s)))

    # نکتهٔ ویژه: خیزش خوزستان ۱۴۰۰ در «تیر/مرداد ۱۴۰۰» (کم‌آبی) رخ داد، نه دی.
    # پس اگر سال ۱۴۰۰ است ولی روایت از «دی» می‌گوید، تاریخِ دیِ ۱۴۰۰ وجود نداشته
    # و این به‌احتمال‌قوی خطای تایپیِ ۱۴۰۰→۱۴۰۱ است → خیزش ۱۴۰۱.
    def map_year(y):
        if y == 1400 and mentions_dey:
            return 'khizesh_1401'
        return YEAR_TO_EVENT.get(y)

    # ۱) سندِ روایتِ قوی (دیِ سالِ X صریح) → برنده، حتی بر date_jalali
    if sy is not None and sconf == 'high':
        target = map_year(sy)
        if target and target != cur:
            return target, f'story_death_year={sy}(strong)', 'high'
        if target == cur:
            return cur, 'unchanged', 'n/a'

    # ۲) date_jalali با ماه/روز = سندِ معتبرِ تاریخِ جانباختن
    if has_month and djy is not None:
        target = map_year(djy)
        if target and target != cur:
            return target, f'date_jalali_year={djy}', 'medium'
        if target == cur:
            return cur, 'unchanged', 'n/a'

    # ۳) date_jalali فقط سال (بدونِ ماه) = سندِ ضعیف‌تر ولی معتبر اگر روایت ردش نکند
    if djy in YEAR_TO_EVENT and not has_month:
        # اگر روایتِ قوی/متوسط سالِ دیگری می‌گوید، روایت برنده
        if sy is not None and sconf in ('high', 'medium') and sy in YEAR_TO_EVENT and sy != djy:
            target = YEAR_TO_EVENT[sy]
            if target != cur:
                return target, f'story_year={sy}_over_djYearOnly', sconf
            return cur, 'unchanged', 'n/a'
        target = YEAR_TO_EVENT[djy]
        if target != cur:
            return target, f'date_jalali_year_only={djy}', 'medium'
        return cur, 'unchanged', 'n/a'

    # ۴) date_jalali نیست؛ فقط روایتِ متوسط/قوی
    if djy is None and sy is not None and sconf in ('high', 'medium') and sy in YEAR_TO_EVENT:
        target = YEAR_TO_EVENT[sy]
        if target != cur:
            return target, f'story_year={sy}_noDate', sconf
    return cur, 'unchanged', 'n/a'


def main():
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)

    events = data['events']
    people = data['people']

    added_events = []
    for k, v in NEW_EVENTS.items():
        if k not in events:
            events[k] = v
            added_events.append(k)

    moves = []
    counter_before = Counter(p.get('e') for p in people)
    for rec in people:
        cur = rec.get('e')
        target, reason, conf = decide_target(rec)
        if target != cur:
            moves.append({
                'id': rec.get('id'), 'name': rec.get('n'),
                'from': cur, 'to': target, 'reason': reason, 'confidence': conf,
                'date_jalali': rec.get('dj'),
                'story_excerpt': (rec.get('s') or '')[:140],
            })
            rec['e'] = target
            if target == 'needs_review':
                rec['fr'] = reason

    counter_after = Counter(p.get('e') for p in people)

    events_sorted = dict(sorted(events.items(), key=lambda kv: kv[1].get('order', 999)))
    data['events'] = events_sorted
    data['meta']['by_event'] = {k: counter_after.get(k, 0) for k in events_sorted.keys()}
    data['meta']['total'] = len(people)
    data['meta']['generated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ver = data['meta'].get('version', '4.0.0')
    try:
        parts = ver.split('.'); parts[1] = str(int(parts[1]) + 1)
        data['meta']['version'] = '.'.join(parts)
    except Exception:
        data['meta']['version'] = '4.1.0'

    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    report = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'added_events': added_events,
        'total_moves': len(moves),
        'moves_by_target': dict(Counter(m['to'] for m in moves)),
        'moves_by_confidence': dict(Counter(m['confidence'] for m in moves)),
        'before': dict(counter_before), 'after': dict(counter_after),
        'moves': moves,
    }
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print('✅ رویدادهای تازه:', added_events)
    print(f'✅ جابه‌جایی‌ها: {len(moves)}')
    print('   مقصد:', report['moves_by_target'])
    print('   اطمینان:', report['moves_by_confidence'])
    print('\n— توزیعِ نهایی —')
    for k in events_sorted:
        print(f'   {k:20} : {counter_after.get(k,0)}')
    print(f'\n📄 {REPORT}')


if __name__ == '__main__':
    main()
