"""
Copy every product image from Cloudinary to Cloudflare R2 and repoint the database.

* Nothing is written to disk: each image is streamed Cloudinary -> memory -> R2.
* Cloudinary resizes/converts on the fly (WebP, max 1600px, q_auto) so the
  download uses far fewer bandwidth credits and R2 storage stays small.
* Safe to re-run: records already migrated are skipped.
* Every change is logged to r2_migration_log.json so it can be undone with --rollback.

Usage:
    python migrate_cloudinary_to_r2.py --dry-run         # show what would happen
    python migrate_cloudinary_to_r2.py --limit 5         # try a few first
    python migrate_cloudinary_to_r2.py                   # migrate everything
    python migrate_cloudinary_to_r2.py --original        # copy originals, no conversion
    python migrate_cloudinary_to_r2.py --rollback        # restore old DB values
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
import time

import django
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import boto3  # noqa: E402
from botocore.config import Config  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
import cloudinary  # noqa: E402
import cloudinary.utils  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import close_old_connections  # noqa: E402

from store.models import Product, ProductImage  # noqa: E402

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r2_migration_log.json')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif', '.heic'}
CLOUDINARY_PREFIX = 'media/'  # django-cloudinary-storage prefixes names with MEDIA_URL
MAX_WIDTH = 1600
CONTENT_TYPES = {
    '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.avif': 'image/avif',
}

# (model, field name) pairs that hold images
FIELDS = [(Product, 'image'), (Product, 'ar_image'), (ProductImage, 'image')]


def env(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"Missing {name} in .env")
    return value


def split_ext(name):
    """Split off a real image extension only (filenames may contain dots)."""
    base, ext = os.path.splitext(name)
    if ext.lower() in IMAGE_EXTS:
        return base, ext.lower()
    return name, ''


def cloudinary_public_id(db_name):
    base, _ = split_ext(db_name)
    if not base.startswith(CLOUDINARY_PREFIX):
        base = CLOUDINARY_PREFIX + base
    return base


def r2_key_for(db_name, keep_original):
    base, ext = split_ext(db_name)
    if base.startswith(CLOUDINARY_PREFIX):
        base = base[len(CLOUDINARY_PREFIX):]
    return base + ((ext or '.jpg') if keep_original else '.webp')


def source_url(db_name, keep_original):
    public_id = cloudinary_public_id(db_name)
    if keep_original:
        _, ext = split_ext(db_name)
        opts = {'format': ext.lstrip('.')} if ext else {}
    else:
        opts = {
            'format': 'webp',
            'transformation': [{'width': MAX_WIDTH, 'crop': 'limit', 'quality': 'auto:good'}],
        }
    url, _ = cloudinary.utils.cloudinary_url(public_id, secure=True, **opts)
    return url


def r2_client(workers=16):
    return boto3.client(
        's3',
        endpoint_url=f"https://{env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=env('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=env('R2_SECRET_ACCESS_KEY'),
        region_name='auto',
        config=Config(max_pool_connections=workers + 4),
    )


def exists_in_r2(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_log(entries):
    with open(LOG_FILE, 'w') as f:
        json.dump(entries, f, indent=2)


def rollback():
    entries = load_log()
    if not entries:
        sys.exit("Nothing to roll back (no r2_migration_log.json).")
    models = {m.__name__: m for m, _ in FIELDS}
    for e in entries:
        models[e['model']].objects.filter(pk=e['pk']).update(**{e['field']: e['old']})
    print(f"Restored {len(entries)} database values. R2 objects were left in place.")
    os.rename(LOG_FILE, LOG_FILE + f'.rolledback.{int(time.time())}')


def transfer_one(session, s3, bucket, db_name, keep_original):
    key = r2_key_for(db_name, keep_original)
    url = source_url(db_name, keep_original)
    if exists_in_r2(s3, bucket, key):
        return key, 0
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    ext = os.path.splitext(key)[1]
    s3.put_object(
        Bucket=bucket, Key=key, Body=resp.content,
        ContentType=CONTENT_TYPES.get(ext, resp.headers.get('Content-Type', 'image/jpeg')),
        CacheControl='public, max-age=31536000, immutable',
    )
    return key, len(resp.content)


def migrate(dry_run, limit, keep_original, workers=12):
    cloudinary.config(
        cloud_name=env('CLOUDINARY_CLOUD_NAME'),
        api_key=env('CLOUDINARY_API_KEY'),
        api_secret=env('CLOUDINARY_API_SECRET'),
        secure=True,
    )
    r2_ready = all(os.getenv(v) for v in
                   ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME'))
    if dry_run and not r2_ready:
        print("(R2 credentials not set yet - dry run will not check R2)")
        bucket, s3 = os.getenv('R2_BUCKET_NAME') or '<bucket>', None
    else:
        bucket = env('R2_BUCKET_NAME')
        s3 = r2_client(workers)
        s3.head_bucket(Bucket=bucket)  # fail fast on wrong credentials / bucket

    print(f"Database: {settings.DATABASES['default']['ENGINE']} "
          f"{settings.DATABASES['default'].get('NAME')}")
    print(f"Mode: {'ORIGINAL files' if keep_original else f'WebP, max {MAX_WIDTH}px'}"
          f" (workers={workers}){'  [DRY RUN]' if dry_run else ''}\n", flush=True)

    log = load_log()
    logged_keys = {(e['model'], e['pk'], e['field']) for e in log}
    stats = {'migrated': 0, 'skipped': 0, 'failed': 0, 'bytes': 0}
    failures = []

    # Collect pending work across all models
    tasks = []  # (model, field, pk, db_name)
    for model, field in FIELDS:
        rows = list(model.objects.exclude(**{f'{field}__isnull': True}).exclude(**{field: ''}).values_list('pk', field))
        for pk, db_name in rows:
            if (model.__name__, pk, field) in logged_keys or (
                db_name.endswith('.webp') and not db_name.startswith(CLOUDINARY_PREFIX)
            ):
                stats['skipped'] += 1
                continue
            tasks.append((model, field, pk, db_name))
            if limit and len(tasks) >= limit:
                break
        if limit and len(tasks) >= limit:
            break

    print(f"Pending records to migrate: {len(tasks)} (already skipped: {stats['skipped']})", flush=True)
    if dry_run:
        for model, field, pk, db_name in tasks:
            label = f"{model.__name__}#{pk}.{field}"
            key = r2_key_for(db_name, keep_original)
            url = source_url(db_name, keep_original)
            print(f"[dry] {label}: {db_name}\n      <- {url}\n      -> r2://{bucket}/{key}")
        return

    # Deduplicate image transfers by db_name
    unique_names = list(dict.fromkeys(db_name for _, _, _, db_name in tasks))
    uploaded = {}
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers + 4)
    session.mount('https://', adapter)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_name = {
            pool.submit(transfer_one, session, s3, bucket, db_name, keep_original): db_name
            for db_name in unique_names
        }
        done_count = 0
        for fut in as_completed(future_to_name):
            db_name = future_to_name[fut]
            done_count += 1
            try:
                key, nbytes = fut.result()
                uploaded[db_name] = key
                stats['bytes'] += nbytes
                if done_count % 50 == 0 or done_count == len(unique_names):
                    print(f"[{done_count}/{len(unique_names)}] transferred "
                          f"({stats['bytes'] / 1024 ** 2:.1f} MB so far)...", flush=True)
            except Exception as exc:
                failures.append((db_name, str(exc)))
                print(f"FAIL transfer {db_name}: {exc}", flush=True)

    # Now update database rows for all successfully uploaded images
    close_old_connections()
    for idx, (model, field, pk, db_name) in enumerate(tasks, 1):
        label = f"{model.__name__}#{pk}.{field}"
        if db_name not in uploaded:
            stats['failed'] += 1
            continue
        new_key = uploaded[db_name]
        model.objects.filter(pk=pk).update(**{field: new_key})
        log.append({'model': model.__name__, 'pk': pk, 'field': field,
                    'old': db_name, 'new': new_key})
        stats['migrated'] += 1
        if idx % 100 == 0:
            save_log(log)
            print(f"DB updated [{idx}/{len(tasks)}]...", flush=True)

    save_log(log)
    print("\n=== Summary ===", flush=True)
    print(f"Migrated: {stats['migrated']}  Skipped (already done): {stats['skipped']}  "
          f"Failed: {stats['failed']}", flush=True)
    print(f"Downloaded from Cloudinary: {stats['bytes'] / 1024 ** 3:.2f} GB "
          f"(~{stats['bytes'] / 1024 ** 3:.1f} bandwidth credits)", flush=True)
    if failures:
        print("\nFailures (re-run the script to retry):", flush=True)
        for name, err in failures[:20]:
            print(f"  {name} -> {err}", flush=True)
    if stats['migrated']:
        print(f"\nLog written to {LOG_FILE}. When happy, set USE_R2_STORAGE=True.", flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dry-run', action='store_true', help='print the plan, change nothing')
    p.add_argument('--limit', type=int, default=0, help='only process N images')
    p.add_argument('--original', action='store_true', help='copy originals instead of WebP')
    p.add_argument('--rollback', action='store_true', help='restore DB values from the log')
    p.add_argument('--workers', type=int, default=12, help='parallel download/upload threads')
    args = p.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate(args.dry_run, args.limit, args.original, args.workers)
