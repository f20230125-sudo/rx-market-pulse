"""Four-page Power BI report, with explicit filters and non-additive enrollment."""
import json

from . import pbi_core as core
from .io import query_dicts


def generate(base, con, preview=False):
    pbi=base/'powerbi'
    core.PBI=pbi;core.DATA=pbi/'data';core.MODEL=pbi/'PayerAccess.SemanticModel';core.REPORT=pbi/'PayerAccess.Report'
    names=['dim_snapshot','dim_brand','dim_plan','fact_brand','fact_strength','fact_change','fact_brand_change','mart_review_queue','mart_quality','mart_source_counts']
    tables=[]
    for name in names:
        desc=con.execute(f'DESCRIBE {name}').fetchall()
        cols=[(x[0], 'int64' if any(t in x[1] for t in ['INT','BOOLEAN']) else 'double' if any(t in x[1] for t in ['DOUBLE','FLOAT','DECIMAL']) else 'string') for x in desc]
        rows=con.execute(f'SELECT * FROM {name} ORDER BY ALL').fetchall()
        tables.append(core.Table(name,cols,rows))
    by={t.name:t for t in tables}
    common='VAR m=SELECTEDVALUE(dim_snapshot[month],MAXX(ALL(dim_snapshot),dim_snapshot[month])) VAR b=SELECTEDVALUE(dim_brand[brand],"BELSOMRA") RETURN '
    def calc(expr):return common+f'CALCULATE({expr},dim_snapshot[month]=m,dim_brand[brand]=b)'
    measures=[
        ('Selected brand','SELECTEDVALUE(dim_brand[brand],"BELSOMRA")','@'),
        ('Selected snapshot','SELECTEDVALUE(dim_snapshot[month],MAXX(ALL(dim_snapshot),dim_snapshot[month]))','@'),
        ('Plans',calc('COUNTROWS(fact_brand)'),'#,0'),
        ('Known access plans',calc('CALCULATE(COUNTROWS(fact_brand),fact_brand[listing]<>"Unknown")'),'#,0'),
        ('Listed plans',calc('CALCULATE(COUNTROWS(fact_brand),fact_brand[listing]="Listed")'),'#,0'),
        ('All strengths listed',calc('CALCULATE(COUNTROWS(fact_brand),fact_brand[all_strengths_listed]=1)'),'#,0'),
        ('Unknown access plans','[Plans]-[Known access plans]','#,0'),
        ('Plan listing rate','DIVIDE([Listed plans],[Known access plans])','0.0%'),
        ('Reported enrollment',calc('SUM(fact_brand[enrollment])'),'#,0'),
        ('Known access enrollment',calc('CALCULATE(SUM(fact_brand[enrollment]),fact_brand[listing]<>"Unknown")'),'#,0'),
        ('Listed enrollment',calc('CALCULATE(SUM(fact_brand[enrollment]),fact_brand[listing]="Listed")'),'#,0'),
        ('Enrollment weighted listing','DIVIDE(COALESCE([Listed enrollment],0),[Known access enrollment])','0.0%'),
        ('Plans with enrollment',calc('COUNT(fact_brand[enrollment])'),'#,0'),
        ('Enrollment completeness','DIVIDE([Plans with enrollment],[Plans])','0.0%'),
        ('No PA or ST plans',calc('CALCULATE(COUNTROWS(fact_brand),fact_brand[any_no_pa_st]=1)'),'#,0'),
        ('PA applies across listed strengths',calc('CALCULATE(COUNTROWS(fact_brand),fact_brand[listing]="Listed",fact_brand[pa]="Yes")'),'#,0'),
    ]
    by['fact_brand'].measures=measures
    changes=[
        ('Plans losing a strength','COALESCE(CALCULATE(DISTINCTCOUNT(fact_change[plan_key]),fact_change[listing_change]="Listing lost"),0)'),
        ('Plans gaining a strength','COALESCE(CALCULATE(DISTINCTCOUNT(fact_change[plan_key]),fact_change[listing_change]="Listing gained"),0)'),
        ('Plans with added PA','COALESCE(CALCULATE(DISTINCTCOUNT(fact_change[plan_key]),fact_change[pa_added]=1),0)'),
        ('Plans with added ST','COALESCE(CALCULATE(DISTINCTCOUNT(fact_change[plan_key]),fact_change[st_added]=1),0)'),
        ('Comparable plans','CALCULATE(DISTINCTCOUNT(fact_change[plan_key]),fact_change[comparable]=1)'),
        ('Comparable reported enrollment','SUMX(VALUES(fact_change[plan_key]),CALCULATE(MAX(fact_change[latest_enrollment]),fact_change[comparable]=1))'),
        ('Enrollment with listing lost','COALESCE(SUMX(VALUES(fact_change[plan_key]),CALCULATE(MAX(fact_change[latest_enrollment]),fact_change[listing_change]="Listing lost")),0)'),
    ]
    by['fact_change'].measures=[(name,'VAR b=SELECTEDVALUE(dim_brand[brand],"BELSOMRA") RETURN CALCULATE('+expr+',dim_brand[brand]=b)','#,0') for name,expr in changes]
    by['fact_brand_change'].measures=[
        ('Paired plans','COUNTROWS(fact_brand_change)','#,0'),
        ('Fixed enrollment denominator','SUM(fact_brand_change[latest_enrollment])','#,0'),
        ('January with August weights','DIVIDE(CALCULATE(SUM(fact_brand_change[latest_enrollment]),fact_brand_change[baseline_listing]="Listed"),[Fixed enrollment denominator])','0.0%'),
        ('August with August weights','DIVIDE(CALCULATE(SUM(fact_brand_change[latest_enrollment]),fact_brand_change[latest_listing]="Listed"),[Fixed enrollment denominator])','0.0%'),
    ]
    by['mart_review_queue'].measures=[('Investigation plans','DISTINCTCOUNT(mart_review_queue[plan_key])','#,0'),
                                      ('Associated enrollment','SUM(mart_review_queue[enrollment])','#,0')]
    core.RELATIONSHIPS=[]
    for fact in ['fact_brand','fact_strength']:
        core.RELATIONSHIPS.extend([(fact,'month','dim_snapshot','month'),(fact,'brand','dim_brand','brand'),(fact,'plan_key','dim_plan','plan_key')])
    core.RELATIONSHIPS.extend([('fact_change','brand','dim_brand','brand'),('fact_change','plan_key','dim_plan','plan_key'),('mart_review_queue','plan_key','dim_plan','plan_key')])
    core.RELATIONSHIPS.extend([('fact_brand_change','brand','dim_brand','brand'),('fact_brand_change','plan_key','dim_plan','plan_key')])
    V,C,M=core.V,core.C,core.Mz
    def header(title,subtitle):
        mark='FICTIONAL PREVIEW  /  ' if preview else 'PUBLIC CMS DATA  /  '
        return [V('textbox',28,12,1200,26,text=[(mark+'PAYER ACCESS INTELLIGENCE','10pt','bold')]),
                V('textbox',28,42,1210,44,text=[(title,'25pt','bold')]),
                V('textbox',28,90,1210,32,text=[(subtitle,'11pt','normal')])]
    def slicer(table,col,x,y,width,title,pick=None):
        return V('slicer',x,y,width,72,{'Values':[C(table,col,True)]},title=title,
                 objects={'data':[{'properties':{'mode':core.lit("'Dropdown'")}}],
                          'selection':[{'properties':{'singleSelect':core.lit('true')}}]},pick=(table,col,pick) if pick else None)
    def footer(text='Enrollment describes plan members, not drug users or denied prescriptions.'):
        return V('textbox',28,680,1220,28,text=[(text,'10pt','normal')])
    def card(measure,x,title,table='fact_brand'):
        return V('card',x,224,286,112,{'Values':[M(table,measure)]},title=title)
    latest=con.execute('SELECT max(month) FROM dim_snapshot').fetchone()[0]
    pages=[]
    pages.append(('overview','01 Executive overview',header('Where does BELSOMRA stand on payer access?',
                'Compare published listings across standalone Medicare PDPs. Default: latest snapshot; BELSOMRA.')+[
        slicer('dim_snapshot','month',28,136,240,'Source snapshot',latest),
        slicer('dim_brand','brand',292,136,260,'Selected brand','BELSOMRA'),
        slicer('dim_plan','region',580,136,350,'PDP region'),
        card('Enrollment weighted listing',28,'Enrollment-weighted listing'),
        card('Plan listing rate',338,'Share of plans listing brand'),
        card('All strengths listed',648,'Plans listing every strength'),
        card('Enrollment completeness',958,'Plans with published enrollment'),
        V('clusteredBarChart',28,360,600,294,{'Category':[C('dim_brand','brand',True)],'Y':[M('fact_brand','Plan listing rate'),M('fact_brand','Enrollment weighted listing')]},
          title='Competitive comparison: plan share and enrollment share',ignore=(4,)),
        V('tableEx',650,360,602,294,{'Values':[*core.cols('dim_brand','brand'),M('fact_brand','Plans'),M('fact_brand','Listed plans'),M('fact_brand','Unknown access plans'),M('fact_brand','Reported enrollment')]},
          title='What sits behind the percentages',ignore=(4,)),footer()]))
    pages.append(('landscape','02 Competitive landscape',header('Inspect plan access before drawing a conclusion',
                'Any-strength listing can hide strength differences. Tier numbers have meaning within each plan.')+[
        slicer('dim_snapshot','month',28,136,240,'Source snapshot',latest),
        slicer('dim_brand','brand',292,136,260,'Brand','BELSOMRA'),
        slicer('dim_plan','region',580,136,350,'PDP region'),
        V('tableEx',28,224,1224,180,{'Values':[*core.cols('dim_plan','plan_key','plan_name','region'),*core.cols('fact_brand','brand','listing','listed_strengths','catalog_strengths','pa','st','ql','enrollment')]},
          title='Plan-brand access: select a row to inspect strengths below'),
        V('tableEx',28,426,1224,228,{'Values':[*core.cols('fact_strength','plan_key','brand','strength_mg','listing','pa','st','ql','tiers','quantity_limit_details','rxcuis','first_drug_source_row','indication_note')]},
          title='Strength detail and original drug-file row references'),footer()]))
    pages.append(('changes','03 Access changes',header('Separate access changes from changes in enrollment',
                'January vs August 2026. Matched known plans only for comparison; exposure uses August enrollment.')+[
        slicer('dim_brand','brand',28,136,240,'Brand','BELSOMRA'),
        slicer('dim_plan','region',292,136,350,'PDP region'),
        card('Plans losing a strength',28,'Plans losing ≥1 strength','fact_change'),
        card('Plans gaining a strength',338,'Plans gaining ≥1 strength','fact_change'),
        card('Plans with added PA',648,'Plans with PA added','fact_change'),
        card('Enrollment with listing lost',958,'August enrollment in loss plans','fact_change'),
        V('tableEx',28,360,1224,176,{'Values':[*core.cols('fact_change','plan_key','brand','strength_mg','listing_change','baseline_pa','latest_pa','baseline_st','latest_st','latest_enrollment','baseline_formulary_id','latest_formulary_id')]},
          title='Change evidence: one row per plan and strength'),footer('Enrollment totals deduplicate plans. Different strengths and months must not be added together.')]))
    pages[-1][2].insert(-1,V('tableEx',28,552,1224,104,{'Values':[*core.cols('dim_brand','brand'),*[M('fact_brand_change',v) for v in ['Paired plans','Fixed enrollment denominator','January with August weights','August with August weights']]]},title='Same August weights at both dates: isolate listing change'))
    pages.append(('review','04 Investigation & quality',header('Turn differences into a reviewable investigation list',
                'Priority: strength loss → added PA/ST → competitor-only listing. Within each category, inspect enrollment.')+[
        slicer('dim_plan','region',28,136,350,'PDP region'),
        V('card',410,136,300,72,{'Values':[M('mart_review_queue','Investigation plans')]},title='BELSOMRA plans to investigate'),
        V('card',760,136,350,72,{'Values':[M('mart_review_queue','Associated enrollment')]},title='Associated reported enrollment'),
        V('tableEx',28,230,1224,244,{'Values':[*core.cols('mart_review_queue','review_rank','plan_key','organization','region','investigation','enrollment','listed_competitors','lost_strengths','next_step')]},
          title='Investigate the payer document and criteria; this is not a sales opportunity estimate',sort=(core.col_ref('mart_review_queue','review_rank'),'Ascending')),
        V('tableEx',28,496,1224,158,{'Values':[*core.cols('mart_quality','check_id','check_name','status','detail')]},title='Source and model quality gates'),footer()]))
    core.pages=lambda:pages
    for table in tables:core.write_csv(table)
    core.write_model(tables);core.write_report()
    pbi.mkdir(parents=True,exist_ok=True)
    (pbi/'PayerAccess.pbip').write_text(json.dumps({'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json','version':'1.0','artifacts':[{'report':{'path':'PayerAccess.Report'}}],'settings':{'enableAutoRecovery':True}},indent=2),encoding='utf-8')
    return {'tables':len(tables),'measures':sum(len(t.measures) for t in tables),'pages':len(pages)}
