#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hash_cached.py — phase 2 only: hash images already in ~/jv_photo_cache.
Resource-safe: cv2 single-thread, batch processing, incremental + resumable save.
NO network access (download already done by photo_hash.py).
"""
import json, os, io, hashlib, sys
from collections import defaultdict

import cv2
cv2.setNumThreads(1)            # critical: avoid resource blow-up
import numpy as np
from PIL import Image
import imagehash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, 'assets/data/javidnam.full.json')
OUT  = os.path.join(ROOT, 'scripts/photo_hashes.json')
CACHE_DIR = os.path.expanduser('~/jv_photo_cache')

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def url_key(u):
    return hashlib.sha1(u.encode('utf-8')).hexdigest()

def face_hash(cv_img):
    try:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        if len(faces) == 0:
            return None, 0
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        pad = int(0.15 * max(w, h))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(cv_img.shape[1], x + w + pad), min(cv_img.shape[0], y + h + pad)
        crop = cv2.cvtColor(cv_img[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
        return str(imagehash.phash(Image.fromarray(crop), hash_size=16)), len(faces)
    except Exception:
        return None, 0

def process(path):
    rec = {'ok': False}
    try:
        data = open(path, 'rb').read()
        if not data:
            return rec
        rec['sha1'] = hashlib.sha1(data).hexdigest()
        pil = Image.open(io.BytesIO(data)).convert('RGB')
        # downscale very large images before face detection to save memory
        if max(pil.size) > 1400:
            pil.thumbnail((1400, 1400))
        rec['w'], rec['h'] = pil.size
        rec['phash'] = str(imagehash.phash(pil, hash_size=16))
        rec['dhash'] = str(imagehash.dhash(pil, hash_size=16))
        rec['ahash'] = str(imagehash.average_hash(pil, hash_size=16))
        cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        fh, nf = face_hash(cv_img)
        rec['face_phash'] = fh
        rec['nfaces'] = nf
        rec['ok'] = True
    except Exception as e:
        rec['err'] = str(e)[:100]
    return rec

def main():
    data = json.load(open(FULL))
    url2ids = defaultdict(list)
    for p in data['people']:
        u = (p.get('ph') or '').strip()
        if u:
            url2ids[u].append(p['id'])
    urls = list(url2ids.keys())

    results = {}
    if os.path.exists(OUT):                 # resume
        try:
            results = json.load(open(OUT))
            print('resuming, already have', len(results), 'entries', flush=True)
        except Exception:
            results = {}

    todo = [u for u in urls if u not in results]
    print(f'{len(urls)} urls, {len(todo)} to hash', flush=True)
    done = 0
    for u in todo:
        path = os.path.join(CACHE_DIR, url_key(u))
        if os.path.exists(path) and os.path.getsize(path) > 0:
            rec = process(path)
        else:
            rec = {'ok': False, 'missing': True}
        rec['ids'] = url2ids[u]
        results[u] = rec
        done += 1
        if done % 200 == 0:
            ok = sum(1 for r in results.values() if r.get('ok'))
            print(f'  {done}/{len(todo)} hashed (total ok={ok})', flush=True)
            json.dump(results, open(OUT, 'w'), ensure_ascii=False)

    ok = sum(1 for r in results.values() if r.get('ok'))
    faces = sum(1 for r in results.values() if r.get('face_phash'))
    json.dump(results, open(OUT, 'w'), ensure_ascii=False)
    print(f'DONE: {ok} decoded, {faces} with face. wrote {OUT}', flush=True)

if __name__ == '__main__':
    main()
