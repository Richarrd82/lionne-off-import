#!/usr/bin/env python3
"""Download a pinned OFF Parquet snapshot with bounded concurrent range reads.

The snapshot has thousands of row groups: remote SQL can issue many tiny reads.
This downloader avoids that latency, checks Content-Range, and verifies the full
file against the upstream LFS SHA-256. No credentials or application data.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision',required=True)
    p.add_argument('--output',required=True,type=pathlib.Path)
    args=p.parse_args()
    if not re.fullmatch('[a-f0-9]{40}',args.revision):raise SystemExit('Expected immutable commit')
    base='https://huggingface.co'
    with urllib.request.urlopen(f'{base}/api/datasets/openfoodfacts/product-database/tree/{args.revision}',timeout=30) as r:entries=json.load(r)
    metadata=next(x for x in entries if x['path']=='food.parquet');size=metadata['size'];expected=metadata['lfs']['oid']
    url=f'{base}/datasets/openfoodfacts/product-database/resolve/{args.revision}/food.parquet'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise SystemExit('Output exists; do not overwrite a verified snapshot')
    partial=args.output.with_suffix('.partial');chunk=32*1024*1024
    fd=os.open(partial,os.O_CREAT|os.O_RDWR,0o600);os.ftruncate(fd,size)
    def fetch(start):
        end=min(start+chunk,size)-1
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','User-Agent':'LIONNE-OFF-Preview/1.0'})
                with urllib.request.urlopen(req,timeout=90) as r:
                    if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise ValueError('Server did not return the requested byte range')
                    data=r.read(end-start+2)
                if len(data)!=end-start+1:raise ValueError('Incomplete range')
                offset=0
                while offset<len(data):offset+=os.pwrite(fd,data[offset:],start+offset)
                return len(data)
            except Exception:
                if attempt==2:raise
                time.sleep(2**attempt)
    done=0;started=time.time();last=0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for f in concurrent.futures.as_completed([pool.submit(fetch,x) for x in range(0,size,chunk)]):
                done+=f.result()
                if time.time()-last>10:
                    print(f'Downloaded {done/size:.0%} ({done/1024**2:.0f} MiB), {done/1024**2/max(1,time.time()-started):.1f} MiB/s',flush=True);last=time.time()
    finally:os.close(fd)
    h=hashlib.sha256()
    with partial.open('rb') as f:
        while data:=f.read(8*1024*1024):h.update(data)
    if h.hexdigest()!=expected:raise ValueError('Snapshot SHA-256 does not match upstream')
    partial.replace(args.output)
    args.output.with_suffix('.source.json').write_text(json.dumps({'revision':args.revision,'url':url,'sha256':expected,'size':size},indent=2))
    print('Verified official snapshot',expected,flush=True)

if __name__=='__main__':main()
