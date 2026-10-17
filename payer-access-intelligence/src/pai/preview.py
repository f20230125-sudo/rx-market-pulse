"""Deliberately fictional acceptance fixtures. Never written into real data/outputs."""
import csv
from .config import BRANDS, MONTHS, ROOT
from .io import dump_json


def write(path, rows, fields, delimiter='|'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=delimiter)
        w.writeheader()
        w.writerows(rows)


def seed(base=None):
    base=base or ROOT/'outputs'/'preview'
    raw=base/'data'/'raw'
    catalog=[]
    for brand,cfg in BRANDS.items():
        for mg in cfg['strengths']:
            catalog.append({'brand':brand,'ingredient':cfg['ingredient'],'strength_mg':mg,
                            'rxcui':f'FIXTURE-{brand}-{mg}','name':f'FICTIONAL {brand} {mg} mg','setid':cfg['setid']})
    dump_json(raw/'products'/'catalog.json',catalog)
    pfields=['CONTRACT_ID','PLAN_ID','SEGMENT_ID','CONTRACT_NAME','PLAN_NAME','FORMULARY_ID','PDP_REGION_CODE','PLAN_SUPPRESSED_YN']
    dfields=['FORMULARY_ID','FORMULARY_VERSION','CONTRACT_YEAR','RXCUI','NDC','TIER_LEVEL_VALUE','QUANTITY_LIMIT_YN','QUANTITY_LIMIT_AMOUNT','QUANTITY_LIMIT_DAYS','PRIOR_AUTHORIZATION_YN','STEP_THERAPY_YN']
    for mi,month in enumerate(MONTHS):
        plans=[]
        # Shared formulary, suppressed plan, missing formulary, unknown enrollment, entry and exit.
        ids=list(range(1,13))
        ids.remove(12 if mi==0 else 11)
        for i in ids:
            plans.append(dict(zip(pfields,[f'S{i:04d}','001','000',f'Fictional payer {(i-1)//3+1}',f'FIXTURE plan {i}',
                                          '00000001' if i==2 else f'{i:08d}',str([3,11,22,32][(i-1)%4]),'Y' if i==5 else 'N'])))
        drugs=[]
        for fid in range(1,13):
            if fid==6: # no records at all: missing source, not unlisted
                continue
            # A non-target product proves that the formulary is present even if every selected brand is unlisted.
            drugs.append(dict(zip(dfields,[f'{fid:08d}','1','2026','NOT-IN-CATALOG','00000000001','1','N','','','N','N'])))
            for j,item in enumerate(catalog):
                brand=item['brand']
                if brand=='BELSOMRA' and (fid in [3,8] or (fid==1 and mi==1) or (fid==4 and item['strength_mg']==20)):
                    continue
                if brand=='QUVIVIQ' and fid%3==0:
                    continue
                pa='Y' if fid in [7,9] or (fid==4 and mi==1) else 'N'
                st='Y' if fid==10 else 'N'
                ql='Y'
                drugs.append(dict(zip(dfields,[f'{fid:08d}','1','2026',item['rxcui'],f'{fid:05d}{j:04d}01','3',ql,'30','30',pa,st])))
                if fid==9 and brand=='DAYVIGO':
                    row=drugs[-1].copy();row['NDC']=f'{fid:05d}{j:04d}02';row['PRIOR_AUTHORIZATION_YN']='N';drugs.append(row)
        ens=[{'Contract Number':p['CONTRACT_ID'],'Plan ID':p['PLAN_ID'],'Enrollment':'*' if p['CONTRACT_ID']=='S0007' else str(int(p['CONTRACT_ID'][1:])*1000+mi*100)} for p in plans]
        write(raw/month/'plans.txt',plans,pfields)
        write(raw/month/'formulary.txt',drugs,dfields)
        write(raw/month/'enrollment.csv',ens,['Contract Number','Plan ID','Enrollment'],',')
    dump_json(raw/'manifest.json',{'mode':'preview','status':'complete','sources':[],
                                 'snapshots':[{'month':m,'members':{}} for m in MONTHS],
                                 'notice':'FICTIONAL ACCEPTANCE FIXTURES. No observed CMS findings.'})
    return base
