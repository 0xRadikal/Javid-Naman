#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
select_images.py
================
از wiki_raw.json عکس‌ها را استخراج و فیلتر می‌کند:
  • نام فایل که حاوی نشانه‌های کلاژ/تظاهرات/پلاکارد است → رد (NOT-PORTRAIT)
  • نام فایلی که به فرد دیگری اشاره دارد (مثل Mousavi برای حبیبی‌موسوی) → رد
  • صفحه‌های blacklist (ابهام‌زدایی/هم‌نام) → رد
  • بقیه → پرتره‌ی معتبر (نام فایل اغلب نامِ خودِ فرد است)
خروجی: image_decisions.json  (id → {url, status, reason})
"""
import json, os, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'wiki_raw.json')
OUT = os.path.join(HERE, 'image_decisions.json')

# صفحه‌هایی که اشتباه/ابهام‌زدایی/فرد دیگرند → هیچ داده‌ای از آنها برداشته نشود
BLACKLIST_TITLES = {
    'اکبر محمدی',        # صفحهٔ ابهام‌زدایی
    'محمد حسینی',        # ابهام‌زدایی (سید محمد حسینی شهید نیست)
    'زهرا بهرامی',       # ابهام‌زدایی (بازیگر)
    'علیرضا افتخاری',    # خوانندهٔ موسیقی (نه شهیدِ دی ۱۴۰۴)
    'نسرین قادری',       # خوانندهٔ اسرائیلی
}

# نشانه‌های نام‌فایلِ غیرپرتره
BAD_TOKENS = [
    'solidarity', 'colage', 'collage', 'protest', 'demonstration', 'rally',
    'mural', 'placard', 'banner', 'memorial_park', 'park_of_iran', 'statue',
    'mousavi', 'mir-hossein', 'mir_hossein',  # عکسِ میرحسین موسوی، نه خودِ فرد
    'iep2009', '.svg',  # svg اغلب لوگو/گرافیک است
]


def commons(filename, w=600):
    return ('https://commons.wikimedia.org/wiki/Special:FilePath/'
            + urllib.parse.quote(filename.replace(' ', '_')) + f'?width={w}')


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    decisions = {}
    accept = reject = none = 0
    for pid, rec in raw.items():
        name = rec['name']
        fa = rec.get('fa') or {}
        wd = rec.get('wikidata') or {}
        en = rec.get('en') or {}
        title = fa.get('title', '')

        if title in BLACKLIST_TITLES:
            decisions[pid] = {'name': name, 'url': None,
                              'status': 'blacklist', 'reason': f'صفحهٔ نادرست: {title}'}
            none += 1
            continue

        # منبعِ عکس به‌ترتیبِ اولویت
        candidates = []
        if wd.get('image_file'):
            candidates.append(('wikidata_P18', wd['image_file'], commons(wd['image_file'])))
        if fa.get('pageimage_original'):
            f = fa['pageimage_original']
            candidates.append(('fa_pageimage', f.rsplit('/', 1)[-1], f))
        if en.get('pageimage_original'):
            f = en['pageimage_original']
            candidates.append(('en_pageimage', f.rsplit('/', 1)[-1], f))

        chosen = None
        for src, fname, url in candidates:
            low = fname.lower()
            if any(tok in low for tok in BAD_TOKENS):
                continue
            chosen = (src, url)
            break

        if chosen:
            decisions[pid] = {'name': name, 'url': chosen[1],
                              'status': 'wiki', 'source': chosen[0],
                              'wiki_url': fa.get('fullurl'), 'reason': 'پرتره از ویکی'}
            accept += 1
        else:
            # هیچ عکسِ معتبری از ویکی نبود → نیاز به منبعِ خبری
            decisions[pid] = {'name': name, 'url': None, 'status': 'need_search',
                              'wiki_url': fa.get('fullurl'),
                              'reason': 'عکسِ ویکی نامناسب/موجود نبود'}
            reject += 1

    json.dump(decisions, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'✅ عکسِ ویکیِ معتبر: {accept}')
    print(f'   نیاز به جست‌وجوی خبری: {reject}')
    print(f'   blacklist (بدون داده): {none}')
    print('خروجی:', OUT)
    print()
    print('=== نمونهٔ عکس‌های پذیرفته‌شده ===')
    for pid, d in list(decisions.items()):
        if d['status'] == 'wiki':
            print(f"  {d['name']:22} | {d['url'][:70]}")


if __name__ == '__main__':
    main()
