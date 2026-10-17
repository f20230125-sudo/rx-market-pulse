import argparse
from pathlib import Path

from .config import ROOT


def main():
    parser=argparse.ArgumentParser(description='Payer Access Intelligence — real public sources; isolated fictional preview')
    sub=parser.add_subparsers(dest='command',required=True)
    f=sub.add_parser('fetch');f.add_argument('--source-map')
    for command in ['build','export','verify','report']:
        p=sub.add_parser(command);p.add_argument('--preview',action='store_true')
    sub.add_parser('preview')
    sub.add_parser('import-slices')
    args=parser.parse_args()
    if args.command=='import-slices':
        import shutil,json
        from .io import sha256
        source=ROOT/'data/extracts'
        manifest=json.loads((source/'manifest.json').read_text())
        for item in manifest['transport_files']:
            src=(source/item['path']).resolve()
            if not src.is_relative_to(source.resolve()) or sha256(src)!=item['sha256']:raise ValueError('Source slice integrity check failed')
            target=ROOT/'data/raw'/item['path']
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,target)
        shutil.copyfile(source/'manifest.json',ROOT/'data/raw/manifest.json')
        print('Imported checksum-verified slices. Original-source receipt:',manifest['ci_run_url'])
    elif args.command=='fetch':
        from .fetch import fetch
        fetch(args.source_map)
    elif args.command=='preview':
        from .preview import seed
        from .build import build
        from .export import export
        seed();build(True);export(True)
    elif args.command=='build':
        from .build import build
        build(args.preview)
    elif args.command=='export':
        from .export import export
        export(args.preview)
    elif args.command=='verify':
        from .verify import verify
        verify(args.preview)
    elif args.command=='report':
        from .report import report
        report(args.preview)


if __name__=='__main__':
    main()
