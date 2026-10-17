import csv
import io
import json
import zipfile

import duckdb
import pytest

from pai.build import prepare
from pai.config import ROOT
from pai.fetch import formulary_url, unpack_tables
from pai.normalize import enrollment, flag, identifier, ndc11, text_encoding
from pai.preview import seed


@pytest.fixture
def warehouse(tmp_path):
    seed(tmp_path)
    prepare(tmp_path/'data/raw',tmp_path/'data/stage')
    con=duckdb.connect()
    for name in ['plans','drugs','enrollment','products','indications','source_counts','quarantine']:
        con.execute(f"CREATE TABLE raw_{name} AS SELECT * FROM read_csv(?,header=true,all_varchar=true)",[str(tmp_path/f'data/stage/{name}.csv')])
    con.execute((ROOT/'sql/model.sql').read_text())
    yield con
    con.close()


def test_ndc_segment_padding():
    assert ndc11('0006-0335-30')=='00006033530'
    assert ndc11('12345-123-01')=='12345012301'
    assert ndc11('12345-1234-1')=='12345123401'
    with pytest.raises(ValueError):ndc11('1234567890')


def test_unknown_values():
    assert enrollment('*') is None
    assert enrollment('1,234')==1234
    assert flag('') is None
    assert flag('0') is False
    assert identifier('1',3)=='001'
    with pytest.raises(ValueError):flag('maybe')


def test_shared_formulary_does_not_multiply_enrollment(warehouse):
    rows=warehouse.execute("SELECT plan_key,enrollment FROM fact_brand WHERE month='2026-01' AND brand='BELSOMRA' AND plan_key IN ('S0001-001','S0002-001') ORDER BY 1").fetchall()
    assert rows==[('S0001-001',1000),('S0002-001',2000)]
    assert warehouse.execute("SELECT count(*) FROM fact_brand WHERE month='2026-01'").fetchone()[0]==33


def test_unknown_is_not_unlisted(warehouse):
    assert warehouse.execute("SELECT DISTINCT listing FROM fact_brand WHERE plan_key IN ('S0005-001','S0006-001')").fetchall()==[('Unknown',)]
    assert warehouse.execute("SELECT enrollment FROM fact_brand WHERE plan_key='S0007-001' LIMIT 1").fetchone()[0] is None


def test_partial_strength_listing_and_mixed_flags(warehouse):
    assert warehouse.execute("SELECT listed_strengths,all_strengths_listed,any_strength_listed FROM fact_brand WHERE month='2026-01' AND plan_key='S0004-001' AND brand='BELSOMRA'").fetchone()==(3,0,1)
    assert warehouse.execute("SELECT DISTINCT pa FROM fact_strength WHERE plan_key='S0009-001' AND brand='DAYVIGO'").fetchall()==[('Mixed',)]


def test_listing_loss_entry_exit_and_restrictions(warehouse):
    assert warehouse.execute("SELECT count(*) FROM fact_change WHERE plan_key='S0001-001' AND brand='BELSOMRA' AND listing_change='Listing lost'").fetchone()[0]==4
    assert warehouse.execute("SELECT DISTINCT listing_change,comparable FROM fact_change WHERE plan_key='S0012-001'").fetchall()==[('Plan entered',0)]
    assert warehouse.execute("SELECT DISTINCT listing_change,comparable FROM fact_change WHERE plan_key='S0011-001'").fetchall()==[('Plan exited',0)]
    assert warehouse.execute("SELECT sum(pa_added) FROM fact_change WHERE plan_key='S0004-001' AND brand='BELSOMRA'").fetchone()[0]==3


def test_queue_unique_and_quality_gates(warehouse):
    assert warehouse.execute("SELECT count(*)=count(DISTINCT plan_key) FROM mart_review_queue").fetchone()[0]
    assert warehouse.execute("SELECT count(*) FROM mart_quality WHERE severity='error' AND status='FAIL'").fetchone()[0]==0


def test_wrong_contract_year_rejected(tmp_path):
    seed(tmp_path)
    p=tmp_path/'data/raw/2026-01/formulary.txt'
    p.write_text(p.read_text(encoding='utf-8-sig').replace('|2026|','|2027|'),encoding='utf-8-sig')
    with pytest.raises(ValueError,match='Wrong contract year'):prepare(tmp_path/'data/raw',tmp_path/'stage')


def test_source_discovery_rejects_year_and_ambiguity():
    ds={'title':'Monthly Prescription Drug Plan Formulary and Pharmacy Network Information','distribution':[{'downloadURL':'https://data.cms.gov/2027_20260122.zip'},{'downloadURL':'https://data.cms.gov/2026_20260122.zip'}]}
    assert formulary_url({'dataset':[ds]},'2026-01').endswith('2026_20260122.zip')
    ds['distribution'].append({'downloadURL':'https://data.cms.gov/2026_20260123.zip'})
    with pytest.raises(ValueError):formulary_url({'dataset':[ds]},'2026-01')


def test_nested_archive_selection(tmp_path):
    outer=tmp_path/'bundle.zip'
    with zipfile.ZipFile(outer,'w') as z:
        for name in ['plan information','basic drugs formulary']:
            b=io.BytesIO()
            with zipfile.ZipFile(b,'w') as inner:inner.writestr(name+'.txt','HEADER\nvalue\n')
            z.writestr(name+'.zip',b.getvalue())
        z.writestr('pharmacy network.txt','DO NOT EXTRACT')
    result=unpack_tables(outer,tmp_path/'out')
    assert set(result)=={'plans','formulary'}
    assert not (tmp_path/'out/pharmacy network.txt').exists()


def test_original_windows_encoding_is_preserved(tmp_path):
    p=tmp_path/'plans.txt';p.write_bytes('PLAN_NAME\nDÓCUMENT\n'.encode('cp1252'))
    assert text_encoding(p)=='cp1252'
    p.write_bytes('PLAN_NAME\nDÓCUMENT\n'.encode('utf-8-sig'))
    assert text_encoding(p)=='utf-8-sig'


def test_blank_plan_id_is_quarantined(tmp_path):
    seed(tmp_path)
    p=tmp_path/'data/raw/2026-01/enrollment.csv'
    with p.open('a',encoding='utf-8') as f:f.write('S9999,,*\n')
    prepare(tmp_path/'data/raw',tmp_path/'stage')
    rows=list(csv.DictReader((tmp_path/'stage/quarantine.csv').open(encoding='utf-8-sig')))
    assert len(rows)==1 and rows[0]['contract_id']=='S9999'
    assert 'Blank plan ID' in rows[0]['reason']


def test_conflicting_plan_assignment_rejected(tmp_path):
    seed(tmp_path)
    p=tmp_path/'data/raw/2026-01/plans.txt'
    rows=list(csv.DictReader(p.open(encoding='utf-8-sig'),delimiter='|'))
    with p.open('a',encoding='utf-8',newline='') as f:
        row=rows[0].copy();row['FORMULARY_ID']='99999999'
        csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='|').writerow(row)
    with pytest.raises(ValueError,match='Conflicting duplicate plan'):prepare(tmp_path/'data/raw',tmp_path/'stage')


def test_fixed_cohort_uses_latest_weights(warehouse):
    denominator=warehouse.execute('SELECT fixed_enrollment_denominator FROM mart_change_summary WHERE brand=\'BELSOMRA\'').fetchone()[0]
    # Plans 5 and 6 have unknown access, plan 7 unknown enrollment; entry and exit are excluded.
    assert denominator==sum(i*1000+100 for i in [1,2,3,4,8,9,10])
    before,after=warehouse.execute("SELECT baseline_rate_fixed_weights,latest_rate_fixed_weights FROM mart_change_summary WHERE brand='BELSOMRA'").fetchone()
    assert before>after


def test_tampered_transport_is_rejected(tmp_path):
    seed(tmp_path)
    p=tmp_path/'data/raw/manifest.json';m=json.loads(p.read_text())
    m.update(transport='filtered',ci_run_url='https://github.com/example/repo/actions/runs/1',
             transport_files=[{'path':'2026-01/plans.txt','sha256':'0'*64}])
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Transport integrity'):prepare(tmp_path/'data/raw',tmp_path/'stage')


def test_single_snapshot_has_no_change_events(tmp_path):
    seed(tmp_path)
    p=tmp_path/'data/raw/manifest.json';m=json.loads(p.read_text());m['snapshots']=m['snapshots'][:1];p.write_text(json.dumps(m))
    prepare(tmp_path/'data/raw',tmp_path/'stage')
    con=duckdb.connect()
    for n in ['plans','drugs','enrollment','products','indications','source_counts','quarantine']:
        con.execute(f'CREATE TABLE raw_{n} AS SELECT * FROM read_csv(?,header=true,all_varchar=true)',[str(tmp_path/f'stage/{n}.csv')])
    con.execute((ROOT/'sql/model.sql').read_text())
    assert con.execute('SELECT count(*) FROM fact_change').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM fact_brand_change').fetchone()[0]==0
    con.close()
