#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_images.py
=================
برای هر عکسِ انتخاب‌شده در image_decisions.json، URLِ مستقیمِ دائمیِ
upload.wikimedia.org را از imageinfo API می‌گیرد (قابل embed در سایت).
SVG و فایل‌های غیرتصویری رد می‌شوند. خروجی: image_resolved.json
"""
import urllib.request, urllib.parse, json, time, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'wiki_raw.json')
DEC = os.path.join(HERE, 'image_decisions.json')
OUT = os.path.join(HERE, 'image_resolved.json')
UA = 'JavidNamanMemorialBot/1.0 (https://github.com/0xRadikal/Javid-Naman; research)'


def http_get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def imageinfo(filename, host):
    q = {'action': 'query', 'format': 'json', 'titles': 'File:' + filename,
         'prop': 'imageinfo', 'iiprop': 'url|mime|size', 'iiurlwidth': 600}
    res = http_get(f'https://{host}/w/api.php?' + urllib.parse.urlencode(q))
    if not res:
        return None
    for pid, pg in res.get('query', {}).get('pages', {}).items():
        ii = pg.get('imageinfo')
        if ii:
            return ii[0]
    return None


def filename_from_url(url):
    """نام فایل را از URLِ ویکی‌مدیا استخراج می‌کند."""
    m = re.search(r'Special:FilePath/([^?]+)', url)
    if m:
        return urllib.parse.unquote(m.group(1)), 'commons.wikimedia.org'
    m = re.search(r'/wikipedia/([a-z]+)/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?]+)', url)
    if m:
        lang = m.group(1)
        fname = urllib.parse.unquote(m.group(2))
        host = 'commons.wikimedia.org' if lang == 'commons' else f'{lang}.wikipedia.org'
        return fname, host
    return None, None


def main():
    dec = json.load(open(DEC, encoding='utf-8'))
    resolved = {}
    ok = skip = 0
    for pid, d in dec.items():
        entry = dict(d)
        if d['status'] != 'wiki' or not d.get('url'):
            resolved[pid] = entry
            continue
        fname, host = filename_from_url(d['url'])
        if not fname:
            entry['status'] = 'need_search'
            entry['reason'] = 'URLِ ویکی قابل‌تجزیه نبود'
            resolved[pid] = entry
            skip += 1
            continue
        info = imageinfo(fname, host)
        time.sleep(0.5)
        if not info:
            entry['status'] = 'need_search'
            entry['reason'] = 'imageinfo نیافت'
            resolved[pid] = entry
            skip += 1
            continue
        mime = info.get('mime', '')
        if 'svg' in mime or not mime.startswith('image'):
            entry['status'] = 'need_search'
            entry['reason'] = f'نوعِ نامناسب: {mime}'
            resolved[pid] = entry
            skip += 1
            continue
        # URL مستقیم؛ thumb برای فایل‌های بزرگ، اصلی برای کوچک‌ها
        direct = info.get('thumburl') or info.get('url')
        entry['photo_direct'] = direct
        entry['photo_fullres'] = info.get('url')
        entry['mime'] = mime
        entry['width'] = info.get('width')
        entry['height'] = info.get('height')
        entry['status'] = 'resolved'
        resolved[pid] = entry
        ok += 1
        print(f"  ✓ {d['name']:22} | {mime} | {direct[:70]}")

    json.dump(resolved, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n✅ resolved: {ok} | skipped→need_search: {skip}')
    print('خروجی:', OUT)


if __name__ == '__main__':
    main()
