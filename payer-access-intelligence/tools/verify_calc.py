"""Run the Excel workbook through LibreOffice Calc, separately from Excel COM.

This tests eight filter scenarios in an independent spreadsheet engine. It is
not an assertion that Microsoft Excel or Power BI Desktop has been validated.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import duckdb
import openpyxl

from pai.config import ROOT
from pai.io import dump_json,query_dicts


def main():
    exe=shutil.which('libreoffice') or shutil.which('soffice')
    if not exe:raise RuntimeError('LibreOffice Calc is not installed')
    con=duckdb.connect(str(ROOT/'data/warehouse/access.duckdb'),read_only=True)
    out=ROOT/'outputs/calc-validation';out.mkdir(parents=True,exist_ok=True)
    latest,first=con.execute('SELECT max(month),min(month) FROM dim_snapshot').fetchone()
    region=con.execute('SELECT region FROM dim_plan ORDER BY region LIMIT 1').fetchone()[0]
    scenarios=[('BELSOMRA','Any strength','All regions',latest,0),('DAYVIGO','Any strength','All regions',latest,0),
               ('QUVIVIQ','All strengths','All regions',first,0),('BELSOMRA','10 mg','All regions',latest,0),
               ('BELSOMRA','Any strength',region,latest,0),('BELSOMRA','Any strength','All regions',latest,10000),
               ('DAYVIGO','20 mg','All regions',latest,0),('BELSOMRA','All strengths','All regions',first,0)]
    receipts=[]
    for i,(brand,view,region,month,minimum) in enumerate(scenarios):
        src=out/f'input-{i}.xlsx'
        book=openpyxl.load_workbook(ROOT/'excel/Payer-Access-Intelligence.xlsx');sheet=book['Analysis']
        for cell,val in [('C6',brand),('C7',view),('C8',region),('F6',month),('F7',minimum)]:sheet[cell]=val
        book.save(src);book.close()
        dest=out/f'output-{i}';dest.mkdir(exist_ok=True)
        subprocess.run([exe,'-env:UserInstallation=file://'+str((out/f'profile-{i}').resolve()),'--headless','--convert-to','xlsx','--outdir',str(dest),str(src)],check=True,timeout=120,capture_output=True)
        calc=openpyxl.load_workbook(dest/src.name,data_only=True);sheet=calc['Analysis']
        table='fact_brand' if view in ['Any strength','All strengths'] else 'fact_strength'
        rows=query_dicts(con,f'SELECT * FROM {table} WHERE month=? AND brand=?',[month,brand])
        if table=='fact_strength':rows=[r for r in rows if f"{r['strength_mg']} mg"==view]
        rows=[r for r in rows if (region=='All regions' or r['region']==region) and (r['enrollment'] or 0)>=minimum]
        def listed(r):return r['all_strengths_listed']==1 if view=='All strengths' else r['listing']=='Listed'
        known=[r for r in rows if r['listing']!='Unknown'];den=sum(r['enrollment'] or 0 for r in known)
        expected={'C12':len(rows),'F12':sum(listed(r) for r in rows),
                  'C16':sum(listed(r) for r in rows)/len(known) if known else None,
                  'F16':sum(r['enrollment'] or 0 for r in known if listed(r))/den if den else None,
                  'C20':sum(r['enrollment'] or 0 for r in rows),'F20':sum(r['enrollment'] is None for r in rows),
                  'C24':len(rows)-len(known),'F24':sum(listed(r) and r['pa']=='Mixed' for r in rows)}
        actual={cell:sheet[cell].value for cell in expected};calc.close()
        ok=all((actual[k] in [None,''] if v is None else isinstance(actual[k],(float,int)) and abs(actual[k]-v)<1e-8*max(1,abs(v))) for k,v in expected.items())
        receipts.append({'scenario':i,'brand':brand,'view':view,'region':region,'month':month,'minimum_enrollment':minimum,'expected':expected,'actual':actual,'status':'PASS' if ok else 'FAIL'})
    result={'engine':'LibreOffice Calc','microsoft_excel_validated':False,'status':'passed' if all(r['status']=='PASS' for r in receipts) else 'failed','scenarios':receipts}
    dump_json(ROOT/'outputs/calc-validation.json',result)
    con.close()
    if result['status']!='passed':raise AssertionError(json.dumps(result,indent=2))
    print('Eight scenarios / 64 headline values passed independent spreadsheet-engine validation')


if __name__=='__main__':main()
