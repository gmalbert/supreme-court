"""Check that a static release preserves source records and Cloudflare limits."""
import importlib.util
import json
from pathlib import Path
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'web/public/data'
spec=importlib.util.spec_from_file_location('web_export',ROOT/'scripts/export_web_data.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_export_helpers_are_timezone_safe_and_strip_html():
    assert module.date_iso(-445888800)=='1955-11-15'
    assert module.date_iso(-2208988800)=='1900-01-01'
    assert module.text('<p>Free &amp; fair</p>')=='Free & fair'
    assert module.clean(float('nan')) is None


def test_static_catalog_extraction_keeps_dict_rows_without_running_pages():
    content=module.constants('pages/History.py')
    assert len(content['CONFIRMATIONS'])>20
    assert content['CJ_ERAS'][0]['cj']=='Jay'


@pytest.mark.skipif(not (DATA/'manifest.json').exists(),reason='Generate the static release first')
def test_release_has_no_lost_cases_or_broken_argument_links():
    cases=json.loads((DATA/'cases.json').read_text(encoding='utf-8'))
    manifest=json.loads((DATA/'manifest.json').read_text())
    assert len(cases)==len(pd.read_parquet(ROOT/'data/cases_by_term.parquet'))==manifest['cases']
    assert len({c['id'] for c in cases})==len(cases)
    files=list(DATA.rglob('*.json'))
    assert len(files)<20000
    assert max(p.stat().st_size for p in files)<25*1024**2
    for case in cases:
        if case['detail']:
            detail=json.loads((DATA/'cases'/(case['id']+'.json')).read_text(encoding='utf-8'))
            assert detail['id']==case['id']
            if manifest['transcriptsIncluded']:
                for argument in detail['arguments']:
                    if not argument.get('transcriptAvailable'):
                        continue
                    assert (DATA/'arguments'/(argument['id']+'.json')).exists(),argument
