"""Build a portable, credential-free delivery archive from explicit directories."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    directories=['src','sql','tests','tools','docs','data/extracts','data/marts','powerbi','excel','.github']
    files=[ROOT/n for n in ['README.md','LICENSE','pyproject.toml','.gitignore','.gitattributes','data/source-map.json']]
    for directory in directories:files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
    files.extend(p for p in (ROOT/'outputs').iterdir() if p.is_file() and p.suffix in ['.json','.csv','.pdf','.png','.md','.xml'] and not p.name.endswith('transfer.json') and p.name!='package-receipt.json')
    files=[p for p in files if '__pycache__' not in p.parts and '.pbi' not in p.parts and p.suffix not in ['.pyc','.log']]
    archive=ROOT.parent/'Payer-Access-Intelligence-Portfolio.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(set(files)):z.write(path,'payer-access-intelligence/'+path.relative_to(ROOT).as_posix())
    receipt={'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'files':len(set(files))}
    (ROOT/'outputs/package-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
