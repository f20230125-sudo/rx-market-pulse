"""Live Excel comparison, with every headline calculated from the Access table."""
import json
import xlsxwriter

from .config import BRANDS
from .io import query_dicts

NAVY='#102B46';TEAL='#087F8C';PAPER='#F7F8FA';SLATE='#60758A';AMBER='#B87822'


def workbook(base,con,preview=False):
    target=base/'excel'/'Payer-Access-Intelligence.xlsx'
    target.parent.mkdir(parents=True,exist_ok=True)
    wb=xlsxwriter.Workbook(target,{'strings_to_urls':False,'strings_to_formulas':False})
    wb.set_properties({'title':'Payer Access Intelligence','subject':'BELSOMRA vs DAYVIGO and QUVIVIQ','author':'Mohammad Uzair Khan',
                       'comments':'Independent public-source analysis. Enrollment is not drug users.'})
    title=wb.add_format({'font_name':'Aptos Display','font_size':25,'bold':True,'font_color':NAVY})
    sub=wb.add_format({'font_name':'Aptos','font_size':11,'font_color':SLATE,'text_wrap':True,'valign':'top'})
    label=wb.add_format({'font_name':'Aptos','font_size':11,'font_color':NAVY,'bold':True})
    inp=wb.add_format({'font_name':'Aptos','font_size':11,'font_color':TEAL,'bg_color':'#E7F3F4','border':1,'border_color':'#C7DFE3'})
    metric=wb.add_format({'font_name':'Aptos Display','font_size':24,'bold':True,'font_color':TEAL,'num_format':'#,##0'})
    pct=wb.add_format({'font_name':'Aptos Display','font_size':24,'bold':True,'font_color':TEAL,'num_format':'0.0%'} )
    note=wb.add_format({'font_name':'Aptos','font_size':10,'font_color':SLATE,'text_wrap':True,'valign':'top'})
    header=wb.add_format({'bold':True,'bg_color':NAVY,'font_color':'#FFFFFF','font_size':11,'font_name':'Aptos'})
    normal=wb.add_format({'font_name':'Aptos','font_size':10,'valign':'top'})
    warn=wb.add_format({'font_color':'#9C3C20','bg_color':'#FFF0DE','bold':True,'text_wrap':True})
    summary=wb.add_worksheet('Analysis');summary.hide_gridlines(2);summary.set_tab_color(TEAL)
    summary.set_column('A:A',3);summary.set_column('B:B',26);summary.set_column('C:C',27);summary.set_column('D:D',4)
    summary.set_column('E:E',29);summary.set_column('F:F',24);summary.set_column('G:H',12)
    summary.merge_range('B2:H3','Payer Access Intelligence',title)
    summary.merge_range('B4:H4','FICTIONAL PREVIEW — acceptance fixtures only' if preview else 'BELSOMRA · DAYVIGO · QUVIVIQ | Original public CMS sources',warn if preview else sub)
    summary.write('B6','Brand',label);summary.write('C6','BELSOMRA',inp)
    summary.write('B7','Strength view',label);summary.write('C7','Any strength',inp)
    summary.write('B8','PDP region',label);summary.write('C8','All regions',inp)
    months=[x[0] for x in con.execute('SELECT month FROM dim_snapshot ORDER BY month').fetchall()]
    summary.write('E6','Snapshot',label);summary.write('F6',months[-1],inp)
    summary.write('E7','Minimum reported enrollment',label);summary.write_number('F7',0,inp)
    summary.merge_range('E8:H9','A minimum of 0 retains plans with missing enrollment for plan counts. Weighted metrics use published enrollment only.',note)
    lists=wb.add_worksheet('Lists')
    opts={'A':['BELSOMRA','DAYVIGO','QUVIVIQ'],'B':['Any strength','All strengths','5 mg','10 mg','15 mg','20 mg','25 mg','50 mg'],
          'C':['All regions',*[x[0] for x in con.execute('SELECT DISTINCT region FROM dim_plan ORDER BY region').fetchall()]],'D':months}
    for col,values in opts.items():
        for i,v in enumerate(values,1):lists.write(f'{col}{i}',v)
    for cell,col in [('C6','A'),('C7','B'),('C8','C'),('F6','D')]:
        summary.data_validation(cell,{'validate':'list','source':f"=Lists!${col}$1:${col}${len(opts[col])}",'error_title':'Select a listed value','error_message':'Use the dropdown list.'})
    summary.data_validation('F7',{'validate':'integer','criteria':'>=','value':0})
    lists.hide()
    rows=[]
    for r in query_dicts(con,'SELECT * FROM fact_strength ORDER BY month,plan_key,brand,strength_mg'):
        rows.append({'Snapshot':r['month'],'Plan':r['plan_key'],'Organization':r['organization'],'Region':r['region'],'Brand':r['brand'],
                     'Strength view':f"{r['strength_mg']} mg",'Listing':r['listing'],'PA':r['pa'],'ST':r['st'],'QL':r['ql'],
                     'Enrollment':r['enrollment'],'Enrollment known':int(r['enrollment'] is not None),'Filter enrollment':r['enrollment'] or 0,
                     'Formulary':r['formulary_id'],'Plan source row':r['plan_source_row'],'Drug source row':r['first_drug_source_row'],
                     'Tier within plan':r['tiers'],'Source status':r['suppressed']})
    for r in query_dicts(con,'SELECT * FROM fact_brand ORDER BY month,plan_key,brand'):
        for view in ['Any strength','All strengths']:
            listing=r['listing'] if view=='Any strength' or r['listing']=='Unknown' else ('Listed' if r['all_strengths_listed']==1 else 'Unlisted')
            rows.append({'Snapshot':r['month'],'Plan':r['plan_key'],'Organization':r['organization'],'Region':r['region'],'Brand':r['brand'],
                         'Strength view':view,'Listing':listing,'PA':r['pa'],'ST':r['st'],'QL':r['ql'],
                         'Enrollment':r['enrollment'],'Enrollment known':int(r['enrollment'] is not None),'Filter enrollment':r['enrollment'] or 0,
                         'Formulary':r['formulary_id'],'Plan source row':r['plan_source_row'],'Drug source row':None,
                         'Tier within plan':'See strength rows','Source status':r['suppressed']})
    data=wb.add_worksheet('Access');data.freeze_panes(1,3);data.set_column(0,1,16);data.set_column(2,3,25);data.set_column(4,9,18);data.set_column(10,17,20)
    fields=list(rows[0])
    data.add_table(0,0,len(rows),len(fields)-1,{'name':'Access','style':'Table Style Medium 2','columns':[{'header':x} for x in fields],
                                             'data':[[r[x] for x in fields] for r in rows]})
    # Criteria keep every result at the selected snapshot, brand, view and region.
    criteria='Access[Snapshot],$F$6,Access[Brand],$C$6,Access[Strength view],$C$7,Access[Region],IF($C$8="All regions","*",$C$8),Access[Filter enrollment],">="&$F$7'
    formulas={
        'C12':f'=COUNTIFS({criteria})',
        'F12':f'=COUNTIFS({criteria},Access[Listing],"Listed")',
        'C16':f'=IFERROR(F12/COUNTIFS({criteria},Access[Listing],"<>Unknown"),"")',
        'F16':f'=IFERROR(SUMIFS(Access[Enrollment],{criteria},Access[Listing],"Listed")/SUMIFS(Access[Enrollment],{criteria},Access[Listing],"<>Unknown"),"")',
        'C20':f'=SUMIFS(Access[Enrollment],{criteria})',
        'F20':f'=COUNTIFS({criteria},Access[Enrollment known],0)',
        'C24':f'=COUNTIFS({criteria},Access[Listing],"Unknown")',
        'F24':f'=COUNTIFS({criteria},Access[Listing],"Listed",Access[PA],"Mixed")',
    }
    labels={'B11':'Plans in selected view','E11':'Plans listing selected view','B15':'Plan listing rate','E15':'Enrollment-weighted listing',
            'B19':'Reported enrollment','E19':'Plans missing enrollment','B23':'Plans with unknown access','E23':'Listed plans with mixed PA'}
    for cell,text in labels.items():summary.write(cell,text,label)
    for cell,formula in formulas.items():summary.write_formula(cell,formula,pct if cell in ['C16','F16'] else metric)
    # Accurate default caches make the initial view usable before Excel recalculates.
    default=con.execute("SELECT plan_count,listed_plans,plan_listing_rate,enrollment_listing_rate,reported_enrollment,plan_count-plans_with_enrollment,unknown_plans,mixed_pa_plans FROM mart_summary WHERE month=? AND brand='BELSOMRA'",[months[-1]]).fetchone()
    for cell,value in zip(['C12','F12','C16','F16','C20','F20','C24','F24'],default):
        summary.write_formula(cell,formulas[cell],pct if cell in ['C16','F16'] else metric,'' if value is None else value)
    summary.merge_range('B27:H29','Listing means inclusion in the published formulary snapshot. Any strength requires at least one listed strength; All strengths requires every strength in this project catalogue. PA, ST and QL are separate restrictions. Mixed means listed records disagree. A blank rate has no valid denominator.',note)
    summary.merge_range('B31:H33','Enrollment is the membership of a plan, not the number of patients using a medicine. The same members appear under each brand and strength view: do not sum across brands, strength views or months. Use Access filters for the exact rows behind each headline.',note)
    summary.set_landscape();summary.set_paper(9);summary.fit_to_pages(1,1);summary.print_area('A1:H34');summary.set_margins(.3,.3,.3,.3)
    for sheet_name,table in [('Plan comparison','fact_brand'),('Changes','fact_change'),('Fixed enrollment weights','mart_change_summary'),('Investigations','mart_review_queue'),('Quality','mart_quality'),('Quarantine','mart_quarantine'),('Source counts','mart_source_counts')]:
        ws=wb.add_worksheet(sheet_name);ws.hide_gridlines(2);ws.freeze_panes(2,2);ws.set_column(0,40,19)
        content=query_dicts(con,f'SELECT * FROM {table} ORDER BY ALL')
        columns=[x[0] for x in con.execute(f'SELECT * FROM {table} LIMIT 0').description]
        ws.merge_range(0,0,0,min(7,len(columns)-1),sheet_name+' | '+('FICTIONAL FIXTURES' if preview else 'Original CMS source analysis'),header)
        if content:
            ws.add_table(1,0,len(content)+1,len(columns)-1,{'name':table.replace('_','')+'Table','style':'Table Style Medium 2',
                'columns':[{'header':x} for x in columns],'data':[[str(r[x]) if isinstance(r[x],(list,dict)) else r[x] for x in columns] for r in content]})
        else:ws.write(2,0,'No qualifying records. This is an observed absence, not a missing chart.',note)
    sources=wb.add_worksheet('Sources & definitions');sources.hide_gridlines(2);sources.set_column('A:A',28);sources.set_column('B:B',110)
    manifest=json.loads((base/'data/raw/manifest.json').read_text())
    definitions=[('Mode','FICTIONAL PREVIEW' if preview else 'REAL PUBLIC SOURCES'),('Scope','Standalone Medicare PDPs (S contracts). Contract year 2026.'),
                 ('Period','January and August 2026; these are published snapshots, not live coverage.'),
                 ('Enrollment-weighted listing','Reported enrollment in known-access plans listing the selected view / reported enrollment in all known-access plans.'),
                 ('Unknown access','Suppressed plan file, unknown suppression flag, or assigned formulary absent from the full source.'),
                 ('Source encoding','Original CMS text can be Windows-1252; derivatives are UTF-8. Original bytes are hashed before conversion.'),
                 ('Price and outcomes','No individual copay, adherence, denied-claim, sales or clinical-effectiveness inference.'),
                 ('Transport receipt',manifest.get('ci_run_url','Local source acquisition'))]
    definitions.extend((s['path'],s['url']+' | SHA-256 '+s['sha256']) for s in manifest.get('sources',[]))
    for i,(key,val) in enumerate(definitions):sources.write(i,0,key,label);sources.write(i,1,val,note);sources.set_row(i,36)
    wb.close()
    return target
