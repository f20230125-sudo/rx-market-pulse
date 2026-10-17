"""Independent source audit and Excel's own formula calculation engine."""
import csv
import json
import random
from pathlib import Path

import duckdb

from .config import BRANDS, ROOT
from .io import dump_json, query_dicts, rows_csv


def source_audit(base,con):
    raw=base/'data/raw'
    catalog=json.loads((raw/'products/catalog.json').read_text())
    codes={x['rxcui']:(x['brand'],int(x['strength_mg'])) for x in catalog}
    result=[]
    for month, in con.execute('SELECT month FROM dim_snapshot ORDER BY month').fetchall():
        folder=raw/month
        # Transport is UTF-8; original CMS files can be cp1252.
        text=(folder/'formulary.txt').read_bytes()
        try:text=text.decode('utf-8-sig')
        except UnicodeDecodeError:text=text.decode('cp1252')
        import io
        planbytes=(folder/'plans.txt').read_bytes()
        try:plantext=planbytes.decode('utf-8-sig')
        except UnicodeDecodeError:plantext=planbytes.decode('cp1252')
        plan_lookup={}
        for source_plan in csv.DictReader(io.StringIO(plantext),delimiter='|'):
            pr={k.upper():v.strip() for k,v in source_plan.items()}
            if pr['CONTRACT_ID'].startswith('S'):
                plan_lookup[pr['CONTRACT_ID']+'-'+pr['PLAN_ID'].zfill(3)]=pr
        groups={}
        fids=set(json.loads((folder/'formulary_ids.json').read_text())) if (folder/'formulary_ids.json').exists() else set()
        for row in csv.DictReader(io.StringIO(text),delimiter='|'):
            r={k.upper():v.strip() for k,v in row.items()}
            fids.add(r['FORMULARY_ID'])
            if r['RXCUI'] in codes:
                groups.setdefault((r['FORMULARY_ID'],*codes[r['RXCUI']]),[]).append(r)
        facts=query_dicts(con,'SELECT * FROM fact_brand WHERE month=? ORDER BY plan_key,brand',[month])
        # Include all listing categories, then fill a deterministic sample.
        selected=[]
        for status in ['Unknown','Unlisted','Listed']:
            candidates=[r for r in facts if r['listing']==status]
            if candidates:selected.append(candidates[0])
        random.Random(2026).shuffle(facts)
        for r in facts:
            if r not in selected:selected.append(r)
            if len(selected)>=10:break
        for row in selected:
            original_plan=plan_lookup[row['plan_key']]
            fid,brand=original_plan['FORMULARY_ID'],row['brand']
            strengths=[mg for mg in BRANDS[brand]['strengths'] if (fid,brand,mg) in groups]
            unknown=original_plan['PLAN_SUPPRESSED_YN'].upper() not in ['N','0'] or fid not in fids
            expected='Unknown' if unknown else ('Listed' if strengths else 'Unlisted')
            expected_n=0 if unknown else len(strengths)
            # listed_strengths is zero for unknown because no observed access can be assigned.
            ok=row['listing']==expected and row['listed_strengths']==expected_n and row['formulary_id']==fid
            result.append({'month':month,'plan':row['plan_key'],'brand':brand,'formulary':fid,'source_plan_row':row['plan_source_row'],
                           'expected_listing':expected,'actual_listing':row['listing'],'expected_strengths':expected_n,
                           'actual_strengths':row['listed_strengths'],'status':'PASS' if ok else 'FAIL'})
    rows_csv(base/'outputs/source-audit.csv',result)
    if not all(r['status']=='PASS' for r in result):raise AssertionError('Independent source audit failed')
    return {'cases':len(result),'passed':sum(r['status']=='PASS' for r in result)}


def excel_check(base,con):
    import win32com.client
    path=(base/'excel/Payer-Access-Intelligence.xlsx').resolve()
    app=win32com.client.DispatchEx('Excel.Application')
    app.Visible=False;app.DisplayAlerts=False;app.AutomationSecurity=3
    book=None;results=[]
    latest=con.execute('SELECT max(month) FROM dim_snapshot').fetchone()[0]
    first=con.execute('SELECT min(month) FROM dim_snapshot').fetchone()[0]
    regions=[r[0] for r in con.execute('SELECT DISTINCT region FROM dim_plan ORDER BY 1').fetchall()]
    scenarios=[('BELSOMRA','Any strength','All regions',latest,0),('DAYVIGO','Any strength','All regions',latest,0),
               ('QUVIVIQ','All strengths','All regions',first,0),('BELSOMRA','10 mg','All regions',latest,0),
               ('BELSOMRA','Any strength',regions[0],latest,0),('BELSOMRA','Any strength','All regions',latest,10000),
               ('DAYVIGO','20 mg','All regions',latest,0),('BELSOMRA','All strengths','All regions',first,0)]
    try:
        book=app.Workbooks.Open(str(path),UpdateLinks=0,ReadOnly=False)
        ws=book.Worksheets('Analysis')
        for brand,view,region,month,minimum in scenarios:
            for cell,val in [('C6',brand),('C7',view),('C8',region),('F6',month),('F7',minimum)]:ws.Range(cell).Value=val
            app.CalculateFullRebuild()
            table='fact_brand' if view in ['Any strength','All strengths'] else 'fact_strength'
            data=query_dicts(con,f'SELECT * FROM {table} WHERE month=? AND brand=?',[month,brand])
            if table=='fact_strength':data=[r for r in data if f"{r['strength_mg']} mg"==view]
            data=[r for r in data if (region=='All regions' or r['region']==region) and (r['enrollment'] or 0)>=minimum]
            def listed(r):return r['listing']=='Listed' if view!='All strengths' else r['all_strengths_listed']==1
            known=[r for r in data if r['listing']!='Unknown']
            den=sum(r['enrollment'] or 0 for r in known)
            expected={'C12':len(data),'F12':sum(listed(r) for r in data),
                      'C16':sum(listed(r) for r in data)/len(known) if known else None,
                      'F16':sum((r['enrollment'] or 0) for r in known if listed(r))/den if den else None,
                      'C20':sum(r['enrollment'] or 0 for r in data),'F20':sum(r['enrollment'] is None for r in data),
                      'C24':len(data)-len(known),'F24':sum(listed(r) and r['pa']=='Mixed' for r in data)}
            actual={cell:ws.Range(cell).Value for cell in expected}
            for cell,value in expected.items():
                got=actual[cell]
                if value is None:
                    if got not in [None,'']:raise AssertionError((brand,view,cell,got,value))
                elif not isinstance(got,(int,float)) or abs(got-value)>1e-8*max(1,abs(value)):
                    raise AssertionError((brand,view,cell,got,value))
            results.append({'brand':brand,'view':view,'region':region,'month':month,'minimum':minimum,'status':'PASS','actual':actual})
        for cell,val in [('C6','BELSOMRA'),('C7','Any strength'),('C8','All regions'),('F6',latest),('F7',0)]:ws.Range(cell).Value=val
        app.CalculateFullRebuild();book.Save()
        ws.ExportAsFixedFormat(0,str((base/'outputs/Excel-Executive-Summary.pdf').resolve()))
    finally:
        if book is not None:book.Close(SaveChanges=False)
        app.Quit()
    return results


def verify(preview=False):
    base=ROOT/'outputs/preview' if preview else ROOT
    con=duckdb.connect(str(base/'data/warehouse/access.duckdb'),read_only=True)
    receipt={'mode':'preview' if preview else 'real','source_audit':source_audit(base,con)}
    try:
        receipt['excel']=excel_check(base,con)
        receipt['status']='passed'
    except Exception as e:
        receipt['status']='failed';receipt['error']=str(e)
        dump_json(base/'outputs/verification.json',receipt)
        raise
    finally:con.close()
    dump_json(base/'outputs/verification.json',receipt)
    print(json.dumps(receipt,indent=2))
