#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_enrichment.py
===================
داده‌های واقعیِ گردآوری‌شده را روی javidnam.full.json اعمال می‌کند:
  • name_en (ne)        ← Wikidata label_en  (فقط اگر خالی باشد)
  • birth_year (by)     ← Wikidata P569 (سال جلالی)
  • date_gregorian (dg) ← Wikidata P570 (در نبودِ مقدارِ فعلی)
  • date_jalali (dj)    ← تبدیلِ P570 به جلالی (در نبودِ مقدارِ فعلی)
  • gender (g)          ← از extract/wikidata در صورت قطعیت (محتاطانه؛ پیش‌فرض رد)
  • photo_url (ph)      ← فقط عکس‌های صحت‌سنجی‌شدهٔ پرتره
  • memorial_links (ml) ← لینکِ صفحهٔ ویکی‌پدیای فارسی/انگلیسی (افزوده، نه جایگزین)
  • sources (src)       ← افزودنِ 'wikipedia_fa'/'wikidata' برای ردگیری

اصول:
  - هیچ روایت/عکسِ AI تولید نمی‌شود.
  - صفحه‌های blacklist (هم‌نام/ابهام‌زدایی) هیچ داده‌ای نمی‌گیرند.
  - داده‌های موجود بازنویسی نمی‌شوند مگر خالی باشند (مگر تصحیحِ صریح).
  - تغییرات در گزارش apply_report.json ثبت می‌شود.
"""
import json, os, re
import jdatetime
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, 'assets', 'data')
FULL = os.path.join(DATA, 'javidnam.full.json')
RAW = os.path.join(HERE, 'wiki_raw.json')
IMG = os.path.join(HERE, 'image_resolved.json')
REPORT = os.path.join(HERE, 'apply_report.json')

# صفحه‌هایی که نادرست/هم‌نام بودند → هیچ متادیتایی از ویکیِ آنها برداشته نشود
BLACKLIST_TITLES = {
    'اکبر محمدی', 'محمد حسینی', 'زهرا بهرامی',
    'علیرضا افتخاری', 'نسرین قادری',
}

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'


def to_fa_digits(s):
    return ''.join(FA_DIGITS[int(c)] if c.isdigit() else c for c in str(s))


def parse_wd_time(t):
    """+2022-09-16T00:00:00Z → date(2022,9,16) یا None اگر روز/ماه ناشناخته."""
    if not t:
        return None
    m = re.match(r'([+\-])(\d{4})-(\d{2})-(\d{2})', t)
    if not m:
        return None
    sign, y, mo, d = m.groups()
    y, mo, d = int(y), int(mo), int(d)
    if sign == '-' or y < 1900 or mo == 0 or d == 0:
        return None
    try:
        return date(y, mo, d)
    except Exception:
        return None


def greg_to_jalali_str(g):
    try:
        j = jdatetime.date.fromgregorian(date=g)
        return to_fa_digits(f'{j.year:04d}/{j.month:02d}/{j.day:02d}')
    except Exception:
        return None


def main():
    full = json.load(open(FULL, encoding='utf-8'))
    raw = json.load(open(RAW, encoding='utf-8'))
    imgs = json.load(open(IMG, encoding='utf-8'))
    people = {p['id']: p for p in full['people']}

    report = {'name_en': [], 'birth_year': [], 'date_gregorian': [],
              'date_jalali': [], 'photo': [], 'links': [], 'skipped_blacklist': []}

    for pid, rec in raw.items():
        if pid not in people:
            continue
        p = people[pid]
        fa = rec.get('fa') or {}
        en = rec.get('en') or {}
        wd = rec.get('wikidata') or {}
        title = fa.get('title', '')

        if title in BLACKLIST_TITLES:
            report['skipped_blacklist'].append(rec['name'])
            continue

        # --- name_en ---
        if not p.get('ne') and wd.get('label_en'):
            p['ne'] = wd['label_en']
            report['name_en'].append((rec['name'], wd['label_en']))

        # --- birth_year (jalali) از P569 ---
        bd = parse_wd_time(wd.get('birth'))
        if bd and not p.get('by'):
            try:
                jb = jdatetime.date.fromgregorian(date=bd)
                p['by'] = jb.year
                report['birth_year'].append((rec['name'], jb.year))
            except Exception:
                pass

        # --- date_gregorian + date_jalali از P570 ---
        dd = parse_wd_time(wd.get('death'))
        if dd:
            iso = dd.isoformat()
            if not p.get('dg'):
                p['dg'] = iso
                report['date_gregorian'].append((rec['name'], iso))
            if not p.get('dj'):
                dj = greg_to_jalali_str(dd)
                if dj:
                    p['dj'] = dj
                    report['date_jalali'].append((rec['name'], dj))

        # --- memorial_links: صفحهٔ ویکی‌پدیا ---
        ml = p.get('ml') or []
        added = []
        for u in (fa.get('fullurl'), en.get('fullurl')):
            if u and u not in ml:
                ml.append(u); added.append(u)
        if added:
            p['ml'] = ml
            report['links'].append((rec['name'], added))

        # --- sources: ردگیری منبع ---
        src = p.get('src') or []
        if fa.get('pageid') and 'wikipedia_fa' not in src:
            src.append('wikipedia_fa')
        if wd and 'wikidata' not in src:
            src.append('wikidata')
        p['src'] = src

    # --- عکس‌های صحت‌سنجی‌شده ---
    for pid, d in imgs.items():
        if pid not in people:
            continue
        if d.get('status') == 'verified' and d.get('photo_direct'):
            p = people[pid]
            if not p.get('ph'):
                p['ph'] = d['photo_direct']
                report['photo'].append((d['name'], d['photo_direct']))

    # ذخیره
    full['people'] = list(people.values())
    json.dump(full, open(FULL, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    json.dump(report, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('✅ اعمال شد روی javidnam.full.json')
    print(f'   name_en افزوده: {len(report["name_en"])}')
    print(f'   birth_year افزوده: {len(report["birth_year"])}')
    print(f'   date_gregorian افزوده: {len(report["date_gregorian"])}')
    print(f'   date_jalali افزوده: {len(report["date_jalali"])}')
    print(f'   عکسِ پرترهٔ تأییدشده افزوده: {len(report["photo"])}')
    print(f'   لینکِ ویکی افزوده: {len(report["links"])}')
    print(f'   blacklist (نادیده): {len(report["skipped_blacklist"])} → {report["skipped_blacklist"]}')


if __name__ == '__main__':
    main()
