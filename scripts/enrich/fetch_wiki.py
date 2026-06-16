#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_wiki.py
=============
گردآوریِ داده‌ها و عکسِ واقعیِ چهره‌های سرشناسِ جاویدنام از ویکی‌پدیای فارسی،
ویکی‌دیتا و ویکی‌مدیا کامِنز. خروجی در scripts/enrich/wiki_raw.json ذخیره می‌شود
تا در گام بعد پس از صحت‌سنجیِ تصویر، روی full.json اعمال شود.

اصول:
  • هیچ داده/عکسِ تولیدیِ AI نیست؛ فقط منابعِ واقعی.
  • برای هر فرد: name_en, age, birth/death(jalali+gregorian), city, occupation,
    extract(روایتِ واقعیِ ویکی)، image(کامنز/پرتره), و لینکِ صفحهٔ ویکی‌پدیا.
"""
import urllib.request, urllib.parse, json, time, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'assets', 'data')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wiki_raw.json')

UA = 'JavidNamanMemorialBot/1.0 (https://github.com/0xRadikal/Javid-Naman; human-rights research archive)'

def http_get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=35) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 503, 502):
                time.sleep(2.0 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def wiki_search(name, lang='fa'):
    """جست‌وجوی صفحهٔ ویکی‌پدیا و برگرداندنِ بهترین عنوان + pageid + qid + extract + pageimage."""
    base = f'https://{lang}.wikipedia.org/w/api.php'
    # 1) جست‌وجو
    q = {'action': 'query', 'format': 'json', 'list': 'search',
         'srsearch': name, 'srlimit': 5, 'srnamespace': 0}
    res = http_get(base + '?' + urllib.parse.urlencode(q))
    if not res or not res.get('query', {}).get('search'):
        return None
    return res['query']['search']


def wiki_page_details(title, lang='fa'):
    base = f'https://{lang}.wikipedia.org/w/api.php'
    q = {'action': 'query', 'format': 'json',
         'prop': 'pageimages|pageprops|extracts|info',
         'piprop': 'original|thumbnail', 'pithumbsize': 600,
         'exintro': 1, 'explaintext': 1, 'redirects': 1, 'inprop': 'url',
         'titles': title}
    res = http_get(base + '?' + urllib.parse.urlencode(q))
    if not res:
        return None
    pages = res.get('query', {}).get('pages', {})
    for pid, pg in pages.items():
        if pid == '-1':
            return None
        return {
            'title': pg.get('title'),
            'pageid': pg.get('pageid'),
            'qid': (pg.get('pageprops') or {}).get('wikibase_item'),
            'extract': pg.get('extract'),
            'pageimage_original': (pg.get('original') or {}).get('source'),
            'pageimage_thumb': (pg.get('thumbnail') or {}).get('source'),
            'fullurl': pg.get('fullurl'),
            'lang': lang,
        }
    return None


def wikidata_entity(qid):
    url = (f'https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}'
           f'&format=json&props=claims|labels|sitelinks')
    res = http_get(url)
    if not res:
        return None
    ent = res.get('entities', {}).get(qid)
    if not ent:
        return None
    claims = ent.get('claims', {})

    def claim_time(pid):
        try:
            return claims[pid][0]['mainsnak']['datavalue']['value']['time']
        except Exception:
            return None

    def claim_item_qid(pid):
        try:
            return claims[pid][0]['mainsnak']['datavalue']['value']['id']
        except Exception:
            return None

    img = None
    if 'P18' in claims:
        try:
            img = claims['P18'][0]['mainsnak']['datavalue']['value']
        except Exception:
            img = None
    return {
        'label_en': (ent.get('labels', {}).get('en') or {}).get('value'),
        'label_fa': (ent.get('labels', {}).get('fa') or {}).get('value'),
        'image_file': img,
        'birth': claim_time('P569'),
        'death': claim_time('P570'),
        'birthplace_qid': claim_item_qid('P19'),
        'occupation_qids': [c['mainsnak']['datavalue']['value']['id']
                            for c in claims.get('P106', [])
                            if c.get('mainsnak', {}).get('datavalue')],
        'sitelinks': {k: v.get('title') for k, v in ent.get('sitelinks', {}).items()
                      if k in ('enwiki', 'fawiki')},
    }


def commons_filepath(filename, width=600):
    return ('https://commons.wikimedia.org/wiki/Special:FilePath/'
            + urllib.parse.quote(filename.replace(' ', '_')) + f'?width={width}')


def load_notables():
    with open(os.path.join(DATA, 'javidnam.full.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [p for p in data['people'] if p.get('nt')]


def main():
    notables = load_notables()
    print(f'تعداد چهره‌های سرشناس: {len(notables)}')

    # ادامه از خروجیِ قبلی (resume)
    results = {}
    if os.path.exists(OUT):
        with open(OUT, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f'ادامه از {len(results)} رکوردِ قبلاً واکشی‌شده')

    for idx, p in enumerate(notables, 1):
        pid = p['id']
        if pid in results and results[pid].get('_done'):
            continue
        name = p['n']
        rec = {'id': pid, 'name': name, 'event': p.get('e'),
               'fa': None, 'en': None, 'wikidata': None, '_done': False}

        # 1) صفحهٔ فارسی
        fa = wiki_page_details(name, 'fa')
        time.sleep(0.8)
        if fa and fa.get('pageid'):
            rec['fa'] = fa
            qid = fa.get('qid')
            if qid:
                wd = wikidata_entity(qid)
                time.sleep(0.6)
                rec['wikidata'] = wd
                # صفحهٔ انگلیسی از sitelinks
                if wd and wd.get('sitelinks', {}).get('enwiki'):
                    en = wiki_page_details(wd['sitelinks']['enwiki'], 'en')
                    time.sleep(0.6)
                    rec['en'] = en
        rec['_done'] = True
        results[pid] = rec

        if idx % 5 == 0 or idx == len(notables):
            with open(OUT, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=1)
            found = sum(1 for r in results.values() if r.get('fa'))
            withimg = sum(1 for r in results.values()
                          if (r.get('wikidata') or {}).get('image_file')
                          or (r.get('fa') or {}).get('pageimage_original')
                          or (r.get('en') or {}).get('pageimage_original'))
            print(f'[{idx}/{len(notables)}] {name[:25]:25} | صفحه:{found} عکس:{withimg}')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print('✅ پایان واکشی. خروجی:', OUT)


if __name__ == '__main__':
    main()
