"""Export small, hash-verified source slices from a complete CI acquisition.

Original archive hashes and full row counts remain in the manifest. This is not
an independent second source: the slices are derivatives of the downloaded CMS files.
"""
import csv
import json
import os
import shutil
from pathlib import Path

from pai.config import ROOT
from pai.io import dump_json, sha256
from pai.normalize import text_encoding


def export():
    raw = ROOT / 'data' / 'raw'
    out = ROOT.parent / '_payer_source_transport'
    out.mkdir(exist_ok=True)
    manifest = json.loads((raw / 'manifest.json').read_text())
    manifest['transport'] = 'filtered'
    manifest['ci_run_url'] = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    catalog = json.loads((raw / 'products' / 'catalog.json').read_text())
    codes = {x['rxcui'] for x in catalog}
    manifest['transport_files'] = []
    for snap in manifest['snapshots']:
        month = snap['month']
        folder = out / month
        folder.mkdir(exist_ok=True)
        snap['full_row_counts'] = {}
        fids = set()
        for filename, delim in [('plans.txt','|'),('formulary.txt','|'),('enrollment.csv',','),('indications.txt','|')]:
            src = raw / month / filename
            if not src.exists():
                continue
            with src.open(encoding=text_encoding(src), newline='') as f, (folder / filename).open('w',encoding='utf-8-sig',newline='') as dest:
                reader = csv.DictReader(f,delimiter=delim)
                w = csv.DictWriter(dest, fieldnames=[*reader.fieldnames,'ORIGINAL_SOURCE_ROW'],delimiter=delim)
                w.writeheader()
                n = 0
                for i,row in enumerate(reader,2):
                    n += 1
                    clean = {k.strip().upper().replace(' ','_'):v.strip() for k,v in row.items()}
                    if filename == 'formulary.txt':
                        fids.add(clean['FORMULARY_ID'])
                        retain = clean['RXCUI'] in codes
                    elif filename == 'indications.txt':
                        retain = clean['RXCUI'] in codes
                    else:
                        retain = clean.get('CONTRACT_ID',clean.get('CONTRACT_NUMBER','')).startswith('S')
                    if retain:
                        w.writerow({**row,'ORIGINAL_SOURCE_ROW':i})
                snap['full_row_counts'][filename] = n
            manifest['transport_files'].append({'path':f'{month}/{filename}','sha256':sha256(folder/filename)})
        dump_json(folder/'formulary_ids.json',sorted(fids))
        manifest['transport_files'].append({'path':f'{month}/formulary_ids.json','sha256':sha256(folder/'formulary_ids.json')})
    (out/'products').mkdir(exist_ok=True)
    shutil.copyfile(raw/'products'/'catalog.json',out/'products'/'catalog.json')
    manifest['transport_files'].append({'path':'products/catalog.json','sha256':sha256(out/'products'/'catalog.json')})
    dump_json(out/'manifest.json',manifest)
    print('Transport complete',out)


if __name__ == '__main__':
    export()
