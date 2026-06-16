#!/usr/bin/env python3
"""
Download every person photo once and compute robust visual fingerprints.

Outputs scripts/photo_hashes.json:
  { photo_url: {ok, w, h, phash, dhash, ahash, whash, face_phash, sha1, ids:[...] } }

Fingerprints:
  - phash/dhash/ahash/whash : whole-image perceptual hashes (imagehash, hex)
  - face_phash              : perceptual hash of the largest detected face crop
                              (lets us match the SAME face even when the photo
                               was cropped / re-hosted differently)
  - sha1                    : exact-bytes hash (catches byte-identical re-uploads)
Multiple records can point at the same URL -> we hash once, list all ids.
"""
import json, os, io, hashlib, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, ssl

from PIL import Image
import imagehash
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, 'assets/data/javidnam.full.json')
OUT  = os.path.join(ROOT, 'scripts/photo_hashes.json')
CACHE_DIR = os.path.expanduser('~/jv_photo_cache')  # persistent (NOT /tmp which is volatile)
os.makedirs(CACHE_DIR, exist_ok=True)

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


def url_key(u):
    return hashlib.sha1(u.encode('utf-8')).hexdigest()


def fetch(u):
    path = os.path.join(CACHE_DIR, url_key(u))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, 'rb').read()
    # marker for known-dead urls so we don't retry them every run
    dead = path + '.dead'
    if os.path.exists(dead):
        return None
    req = urllib.request.Request(u, headers={'User-Agent': UA, 'Referer': 'https://twitter.com/'})
    try:
        with urllib.request.urlopen(req, timeout=12, context=CTX) as r:
            data = r.read()
        if data:
            open(path, 'wb').write(data)
        return data
    except Exception:
        open(dead, 'wb').write(b'')
        return None


def face_hash(cv_img):
    try:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                              minSize=(40, 40))
        if len(faces) == 0:
            return None, 0
        # largest face
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        # pad a bit
        pad = int(0.15 * max(w, h))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(cv_img.shape[1], x + w + pad), min(cv_img.shape[0], y + h + pad)
        crop = cv_img[y0:y1, x0:x1]
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(crop_rgb)
        return str(imagehash.phash(pil, hash_size=16)), len(faces)
    except Exception:
        return None, 0


def process(u):
    """CPU/decode work — MUST run single-threaded (cv2 + PIL not thread-safe here)."""
    rec = {'ok': False}
    path = os.path.join(CACHE_DIR, url_key(u))
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        return u, rec
    data = open(path, 'rb').read()
    if not data:
        return u, rec
    try:
        rec['sha1'] = hashlib.sha1(data).hexdigest()
        pil = Image.open(io.BytesIO(data)).convert('RGB')
        rec['w'], rec['h'] = pil.size
        rec['phash'] = str(imagehash.phash(pil, hash_size=16))
        rec['dhash'] = str(imagehash.dhash(pil, hash_size=16))
        rec['ahash'] = str(imagehash.average_hash(pil, hash_size=16))
        rec['whash'] = str(imagehash.whash(pil, hash_size=16))
        cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        fh, nfaces = face_hash(cv_img)
        rec['face_phash'] = fh
        rec['nfaces'] = nfaces
        rec['ok'] = True
    except Exception as e:
        rec['err'] = str(e)[:120]
    return u, rec


def main():
    data = json.load(open(FULL))
    url2ids = defaultdict(list)
    for p in data['people']:
        u = (p.get('ph') or '').strip()
        if u:
            url2ids[u].append(p['id'])
    urls = list(url2ids.keys())
    print(f'unique photo urls: {len(urls)} (records with photo: {sum(len(v) for v in url2ids.values())})', flush=True)

    # ---- PHASE 1: download concurrently (network I/O is thread-safe) ----
    dl = 0
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(fetch, u): u for u in urls}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass
            dl += 1
            if dl % 300 == 0:
                print(f'  downloaded {dl}/{len(urls)}', flush=True)
    cached = len([f for f in os.listdir(CACHE_DIR) if not f.endswith('.dead')])
    print(f'download phase done, cached image files: {cached}', flush=True)

    # ---- PHASE 2: decode + hash + face detect SINGLE-THREADED (cv2/PIL safe) ----
    results = {}
    done = 0
    for u in urls:
        _, rec = process(u)
        rec['ids'] = url2ids[u]
        results[u] = rec
        done += 1
        if done % 300 == 0:
            ok = sum(1 for r in results.values() if r.get('ok'))
            print(f'  hashed {done}/{len(urls)}, ok={ok}', flush=True)
            json.dump(results, open(OUT, 'w'), ensure_ascii=False)  # incremental save

    ok = sum(1 for r in results.values() if r.get('ok'))
    faces = sum(1 for r in results.values() if r.get('face_phash'))
    print(f'DONE: {ok}/{len(urls)} decoded, {faces} with detected face')
    json.dump(results, open(OUT, 'w'), ensure_ascii=False)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
