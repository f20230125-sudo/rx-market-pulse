"""Standalone vector PDF reports rendered from the same verified analytical marts.

These are Python-generated analytical reports, not Power BI Desktop screenshots.
"""
import json
from pathlib import Path

import duckdb
import pymupdf as fitz

from .config import ROOT
from .io import dump_json, query_dicts

INK=(.063,.169,.275);TEAL=(.031,.498,.549);SLATE=(.376,.459,.541);AMBER=(.722,.471,.133)
PAPER=(.969,.973,.980);PALE=(.902,.953,.957);RULE=(.839,.878,.918)


def text(page,rect,value,size=11,color=INK,bold=False):
    r=fitz.Rect(rect)
    result=-1
    actual=size
    while result<0 and actual>=size*.78:
        result=page.insert_textbox(r,str(value),fontsize=actual,fontname='hebo' if bold else 'helv',color=color,lineheight=1.15)
        actual-=.5
    if result<0:raise ValueError(f'Text overflow: {str(value)[:100]} in {rect}')


def line(page,y,width=760):
    page.draw_line((30,y),(width-30,y),color=RULE,width=.7)


def page_header(doc,kicker,title,subtitle,index,preview=False):
    page=doc.new_page(width=842,height=595)
    page.draw_rect(page.rect,color=None,fill=PAPER)
    page.draw_rect(fitz.Rect(0,0,842,9),color=None,fill=TEAL)
    text(page,(30,23,812,43),('FICTIONAL PREVIEW | ' if preview else '')+kicker,9,TEAL,True)
    text(page,(30,50,812,90),title,23,INK,True)
    text(page,(30,94,812,130),subtitle,10,SLATE)
    text(page,(30,561,775,585),'Independent public-data portfolio | January / August 2026 | Plan membership is not drug users.',8,SLATE)
    text(page,(790,561,825,585),str(index),8,SLATE)
    return page


def table(page,x,y,width,headers,rows,col_weights=None,font=9,row_height=28):
    weights=col_weights or [1]*len(headers)
    widths=[width*w/sum(weights) for w in weights]
    page.draw_rect(fitz.Rect(x,y,x+width,y+row_height),color=None,fill=INK)
    cur=x
    for h,w in zip(headers,widths):text(page,(cur+7,y+7,cur+w-6,y+row_height),h,font,(1,1,1),True);cur+=w
    y+=row_height
    for i,row in enumerate(rows):
        if i%2==0:page.draw_rect(fitz.Rect(x,y,x+width,y+row_height),color=None,fill=(1,1,1))
        cur=x
        for val,w in zip(row,widths):text(page,(cur+7,y+7,cur+w-6,y+row_height),val,font,INK);cur+=w
        y+=row_height
    return y


def cards(page,items,y=143):
    width=180;gap=20
    for i,(value,label) in enumerate(items):
        x=30+i*(width+gap)
        page.draw_rect(fitz.Rect(x,y,x+width,y+87),color=None,fill=(1,1,1))
        text(page,(x+12,y+11,x+width-8,y+49),value,26,TEAL,True)
        text(page,(x+12,y+56,x+width-8,y+83),label,9,SLATE)


def report(preview=False):
    base=ROOT/'outputs/preview' if preview else ROOT
    out=base/'outputs';out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(str(base/'data/warehouse/access.duckdb'),read_only=True)
    summary=query_dicts(con,'SELECT * FROM mart_summary ORDER BY month,brand')
    latest=max(x['month'] for x in summary);first=min(x['month'] for x in summary)
    current={x['brand']:x for x in summary if x['month']==latest}
    previous={x['brand']:x for x in summary if x['month']==first}
    b=current['BELSOMRA'];p=previous['BELSOMRA']
    queue=query_dicts(con,'SELECT organization,count(*) plan_count,sum(enrollment) members FROM mart_review_queue GROUP BY organization ORDER BY members DESC NULLS LAST')
    queue_n=con.execute('SELECT count(*) FROM mart_review_queue').fetchone()[0]
    queue_members=con.execute('SELECT coalesce(sum(enrollment),0) FROM mart_review_queue').fetchone()[0]
    change=query_dicts(con,'SELECT * FROM mart_change_summary ORDER BY brand')
    additions=con.execute('SELECT coalesce(sum(pa_added),0),coalesce(sum(st_added),0),coalesce(sum(ql_added),0) FROM fact_change').fetchone()
    loss=con.execute("SELECT count(DISTINCT plan_key) FROM fact_change WHERE brand='BELSOMRA' AND listing_change='Listing lost'").fetchone()[0]
    counts=query_dicts(con,'SELECT * FROM mart_source_counts ORDER BY month,source')
    full_rows=sum(int(x['source_rows']) for x in counts if x['source']=='formulary')
    source_manifest=json.loads((base/'data/raw/manifest.json').read_text())
    # Four-page static analytical report.
    doc=fitz.open()
    page=page_header(doc,'PAYER ACCESS INTELLIGENCE / EXECUTIVE OVERVIEW','Published access is strong, with a concentrated gap',
                     'BELSOMRA compared with DAYVIGO and QUVIVIQ across US standalone Medicare prescription drug plans.',1,preview)
    cards(page,[(str(b['plan_count']),'standalone PDPs'),(f"{b['enrollment_listing_rate']:.1%}",'BELSOMRA weighted listing'),(str(queue_n),'plans in investigation queue'),(f'{queue_members/1e6:.2f}M','associated plan members')])
    text(page,(30,251,800,277),'Plan coverage and member coverage answer different questions',14,INK,True)
    y=292
    for brand in ['BELSOMRA','DAYVIGO','QUVIVIQ']:
        r=current[brand]
        text(page,(30,y+3,155,y+26),brand,11,INK,True)
        page.draw_rect(fitz.Rect(165,y,165+500*r['enrollment_listing_rate'],y+16),color=None,fill=TEAL)
        page.draw_rect(fitz.Rect(165,y+20,165+500*r['plan_listing_rate'],y+28),color=None,fill=AMBER)
        text(page,(680,y-1,812,y+37),f"{r['enrollment_listing_rate']:.1%} members\n{r['plan_listing_rate']:.1%} plans",10,SLATE)
        y+=66
    text(page,(30,497,810,544),'Teal: enrollment-weighted listing. Amber: share of plans listing any catalogued strength. Coverage overlaps across brands; percentages must not be added. Listing is not a guarantee of claim payment.',10,SLATE)
    page=page_header(doc,'COMPETITIVE LANDSCAPE','Read listings and restrictions separately',
                     'Each brand has a complete strength catalogue. A plan is counted once per brand and snapshot.',2,preview)
    rows=[]
    for brand in current:
        r=current[brand]
        no_pa=r['no_pa_st_plans']
        ql=con.execute("SELECT count(*) FROM fact_brand WHERE month=? AND brand=? AND listing='Listed' AND ql='Yes'",[latest,brand]).fetchone()[0]
        rows.append([brand,f"{r['listed_plans']:,} / {r['known_plans']:,}",f"{r['listed_enrollment']/1e6:.2f}M",f"{no_pa:,}",f'{ql:,}'])
    table(page,30,151,782,['Brand','Listed / known plans','Members in listed plans','No PA / ST plans','QL plans'],rows,[1.1,1.4,1.5,1.2,.8],9,38)
    text(page,(30,339,402,365),'What the data supports',14,INK,True)
    text(page,(30,377,400,495),f"BELSOMRA is listed by {b['listed_plans']} of {b['known_plans']} plans, associated with {b['listed_enrollment']:,} members. Its member-weighted listing exceeds its plan listing rate by {(b['enrollment_listing_rate']-b['plan_listing_rate'])*100:.1f} percentage points.",12)
    text(page,(440,339,812,365),'What still needs investigation',14,INK,True)
    text(page,(440,377,812,510),'Quantity limits apply to every listed plan-brand in the real case study. A plan without prior authorization or step therapy can still have a quantity limit. Tier values describe a plan benefit design; they are not universal prices or clinical rankings.',12)
    page=page_header(doc,'PAIRED SNAPSHOT ANALYSIS','A higher weighted rate does not prove broader access',
                     f'Compare {first} with {latest}. August enrollment is held fixed in the paired-cohort comparison.',3,preview)
    table(page,30,151,782,['Brand','January actual weights','August actual weights','Jan with Aug weights','Aug with Aug weights'],
          [[r['brand'],f"{previous[r['brand']]['enrollment_listing_rate']:.2%}",f"{current[r['brand']]['enrollment_listing_rate']:.2%}",
            f"{r['baseline_rate_fixed_weights']:.2%}",f"{r['latest_rate_fixed_weights']:.2%}"] for r in change],[1,1.3,1.3,1.3,1.3],9,38)
    text(page,(30,338,810,369),f"BELSOMRA: {(b['enrollment_listing_rate']-p['enrollment_listing_rate'])*100:+.2f} percentage points with each month's enrollment",17,TEAL,True)
    stable=all(abs(r['baseline_rate_fixed_weights']-r['latest_rate_fixed_weights'])<1e-10 for r in change)
    finding='Listing sets are unchanged across the compared plans. With the same August weights at both dates, the listing rates are identical. The changing observed weighted rates therefore reflect enrollment composition within this cohort, not listing expansion.' if stable else 'Fixed-weight differences isolate observed listing changes within matched known plans. Plan entrants, exits and unknown access require separate interpretation.'
    text(page,(30,388,812,476),finding,13)
    text(page,(30,491,812,536),f'BELSOMRA strength-listing loss plans: {loss}. Added flags across compared strengths: PA {additions[0]}, ST {additions[1]}, QL {additions[2]}. No events is a valid analytical result.',11,SLATE)
    page=page_header(doc,'INVESTIGATION & QUALITY','Start with the largest documented access differences',
                     'The queue is a request for payer-document review. It does not estimate lost or recoverable sales.',4,preview)
    table(page,30,149,782,['Contract organization','Plans','Associated enrollment'],
          [[r['organization'],str(r['plan_count']),f"{r['members'] or 0:,}"] for r in queue[:4]],[4.7,.6,1.4],8,34)
    top2=sum(r['members'] or 0 for r in queue[:2])
    text(page,(30,342,812,376),f"Top two contract organizations account for {top2/queue_members:.1%} of queue enrollment." if queue_members else 'No investigation events in this selection.',17,TEAL,True)
    text(page,(30,393,812,466),f"1. Check current formulary documents and indication / utilization criteria.\n2. Review whether the difference persists across all strengths.\n3. Discuss access barriers using plan-level evidence; do not infer clinical suitability or sales impact.",11)
    text(page,(30,481,812,542),f"Provenance: {full_rows:,} original formulary rows scanned across two snapshots; archive and member-file SHA-256 hashes retained. Four unkeyed enrollment records were quarantined. The twenty-case source audit is saved separately. These pages are Python-generated, not Desktop screenshots.",10,SLATE)
    pdf=out/'Payer-Access-Analytical-Report.pdf';doc.save(pdf)
    for i,page in enumerate(doc):
        page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(str(out/f'Report-{i+1:02d}.png'))
    doc.close()
    # Two-page interview case study; uses the same numerical findings.
    memo=fitz.open()
    page=page_header(memo,'PORTFOLIO CASE STUDY / 1 OF 2','Payer Access Intelligence',
                     'Business question: which payer access differences should a Commercial Operations analyst investigate first?',1,preview)
    text(page,(30,147,812,179),'Why this project',15,INK,True)
    text(page,(30,187,812,249),'A spend dashboard shows where money moved. This analysis asks whether a product is listed, what restrictions apply, and whether a changing headline represents a real change in access. It demonstrates data harmonization, SQL analysis, Excel reporting and a Power BI semantic model.',12)
    findings=[f"BELSOMRA is listed by {b['listed_plans']} / {b['known_plans']} plans ({b['plan_listing_rate']:.1%}), associated with {b['listed_enrollment']:,} members ({b['enrollment_listing_rate']:.1%} of the observed cohort).",
              f"The member-weighted rate changed from {p['enrollment_listing_rate']:.1%} to {b['enrollment_listing_rate']:.1%}. Fixed August weights show {'no listing expansion' if stable else 'the matched-plan listing component separately'}; the headline must be interpreted with enrollment composition.",
              f"The review queue contains {queue_n} plans with {queue_members:,} reported members. The top two contract organizations contain {top2/queue_members:.1%} of queue enrollment; payer-document checks can begin there." if queue_members else 'The review queue contains no qualifying events.']
    text(page,(30,271,812,304),'Three findings to explain in an interview',15,INK,True)
    for i,value in enumerate(findings):
        text(page,(30,318+i*74,63,350+i*74),f'0{i+1}',18,TEAL,True)
        text(page,(76,317+i*74,812,382+i*74),value,12)
    page=page_header(memo,'PORTFOLIO CASE STUDY / 2 OF 2','A reproducible answer, with practical limits',
                     'Independent work using public US data. No MSD affiliation or internal data is claimed.',2,preview)
    text(page,(30,149,397,178),'Data and harmonization',15,INK,True)
    text(page,(30,187,397,346),f"Original CMS archives and NLM product references are downloaded and hashed. {full_rows:,} formulary records become a {b['plan_count']}-plan cohort with eight product strengths. Package records are reduced before enrollment joins. Shared formularies stay shared, missing source access stays unknown, and unkeyed enrollment rows are quarantined.",12)
    text(page,(439,149,812,178),'Business use',15,INK,True)
    text(page,(439,187,812,346),'Use the Power BI report to compare brands, inspect a region and trace a strength-level difference. Use Excel to change the brand, strength view, region, snapshot and enrollment threshold. Use the investigation queue to prepare payer questions supported by exact plan and formulary identifiers.',12)
    line(page,363,842)
    text(page,(30,382,812,412),'Validation and delivery status',15,INK,True)
    text(page,(30,421,812,520),'Delivered: source manifests, SQL marts, source audit, live-formula workbook, Power BI project and PDF report. Eight workbook scenarios passed LibreOffice Calc; 53 Power BI JSON files passed Microsoft schemas, and the model passed Microsoft TMDL parsing. Excel COM and Desktop rendering remain pending because an interactive logon session is unavailable. No Desktop-validated PBIX is claimed.',12)
    memo.save(out/'Payer-Access-Case-Study.pdf')
    for i,page in enumerate(memo):
        page.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(str(out/f'Case-Study-{i+1:02d}.png'))
    memo.close()
    md='# Payer Access Intelligence\n\n'+ '\n\n'.join(findings)+'\n\nThese are descriptive US standalone PDP findings. Enrollment is not drug users, and the queue is not a revenue estimate.\n'
    (out/'findings.md').write_text(md,encoding='utf-8')
    dump_json(out/'report-receipt.json',{'mode':'preview' if preview else 'real','pdf_pages':4,'case_study_pages':2,'renderer':'PyMuPDF','desktop_export':False})
    con.close();print('Generated vector reports and four page previews:',out)
