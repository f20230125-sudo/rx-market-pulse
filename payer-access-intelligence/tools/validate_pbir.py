"""Validate generated Power BI JSON against Microsoft's published schemas."""
import json
from functools import lru_cache

import jsonschema
import requests
from referencing import Registry,Resource

from pai.config import ROOT
from pai.io import dump_json


@lru_cache(maxsize=None)
def get_schema(url):
    if not url.startswith('https://developer.microsoft.com/json-schemas/'):
        raise ValueError('Unexpected schema authority: '+url)
    r=requests.get(url,timeout=45);r.raise_for_status()
    return r.json()


def main():
    registry=Registry(retrieve=lambda uri:Resource.from_contents(get_schema(uri)))
    checked=[];errors=[]
    for path in sorted((ROOT/'powerbi').rglob('*')):
        if path.suffix not in ['.json','.pbip','.pbir','.pbism'] or '.pbi' in path.parts:continue
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if '$schema' not in data:continue
        schema=get_schema(data['$schema'])
        validator=jsonschema.validators.validator_for(schema)(schema,registry=registry)
        found=[f'{e.json_path}: {e.message}' for e in validator.iter_errors(data)]
        checked.append(str(path.relative_to(ROOT)))
        errors.extend({'file':str(path.relative_to(ROOT)),'error':s} for s in found)
    receipt={'validator':'Microsoft published Power BI JSON schemas','status':'failed' if errors else 'passed','files':len(checked),'errors':errors,'desktop_rendered':False}
    dump_json(ROOT/'outputs/pbir-schema-validation.json',receipt)
    print(json.dumps(receipt,indent=2))
    if errors:raise ValueError('Power BI report schema validation failed')


if __name__=='__main__':main()
