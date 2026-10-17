import json
import duckdb
from .config import ROOT
from .io import dump_json


def export(preview=False):
    from .powerbi import generate
    from .workbook import workbook
    base=ROOT/'outputs'/'preview' if preview else ROOT
    receipt=json.loads((base/'outputs'/'build-receipt.json').read_text())
    if (receipt['mode']=='preview')!=preview:raise ValueError('Preview/real mismatch')
    con=duckdb.connect(str(base/'data/warehouse/access.duckdb'),read_only=True)
    pbi=generate(base,con,preview)
    xlsx=workbook(base,con,preview)
    dump_json(base/'outputs/export-receipt.json',{'mode':receipt['mode'],'powerbi':pbi,'excel':str(xlsx)})
    con.close()
    print('Exported Power BI project and live-formula Excel workbook:',base)
