#!/usr/bin/env python3
"""Сборка архива исходников без .env, кэшей и сырых выгрузок."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def include(path):
    rel=path.relative_to(ROOT)
    if any(x in {'.git','.venv','__pycache__','raw','reports'}for x in rel.parts):return False
    if path.name.startswith('.env') and path.name!='.env.example':return False
    return path.is_file() and path.suffix not in {'.pyc','.pyo','.zip','.partial'} and path.name not in {'.DS_Store','tests-initial.log'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    target=args.output.expanduser().resolve()
    if target.exists():p.error('Refusing to overwrite existing archive')
    target.parent.mkdir(parents=True,exist_ok=True)
    paths=sorted(x for x in ROOT.rglob('*')if include(x));manifest=[]
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED)as z:
        for path in paths:
            name=str(path.relative_to(ROOT));data=path.read_bytes();z.writestr('godiyak-yaroslav-m25-555-etl-2026/'+name,data)
            manifest.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    with zipfile.ZipFile(target)as z:
        assert z.testzip()is None
        assert len(z.namelist())==len(paths)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n')
    target.with_suffix(target.suffix+'.manifest.json').write_text(json.dumps({'archive':target.name,'sha256':digest,'files':manifest},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'archive':str(target),'files':len(paths),'sha256':digest},ensure_ascii=False))


if __name__=='__main__':main()
