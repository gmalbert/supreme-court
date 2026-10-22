"""Build a complete, secret-free static release from the existing Oyez snapshots.

Run from any directory: python scripts/export_web_data.py
No Streamlit imports, live API calls, or retrieval-artifact prerequisites.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import math
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.local_data import infer_issue_area, infer_disposition


def clean(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, 'tolist'):
        return clean(value.tolist())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if hasattr(value, 'item'):
        return clean(value.item())
    return value


def decoded(value, default=None):
    value = clean(value)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return value if value is not None else default


def text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(clean(value) or '')))).strip()


def constants(path):
    # Interpret curated dict(...) rows without executing/importing Streamlit pages.
    def literal(node):
        if isinstance(node, ast.Name) and node.id == 'CURRENT_YEAR':
            return datetime.now(timezone.utc).year
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and not node.args:
            return {kw.arg: literal(kw.value) for kw in node.keywords if kw.arg}
        if isinstance(node, (ast.List, ast.Tuple)):
            return [literal(v) for v in node.elts]
        if isinstance(node, ast.Dict):
            return {literal(k): literal(v) for k, v in zip(node.keys, node.values)}
        return ast.literal_eval(node)
    result = {}
    for node in ast.walk(ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))):
        if isinstance(node, ast.Assign):
            try:
                value = literal(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and isinstance(value, (dict, list, tuple, str)):
                    result[target.id] = value
    return result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')


def case_key(href):
    return str(href).removeprefix('https://api.oyez.org/cases/')


def date_iso(value):
    try:
        return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=float(value))).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return ''


def build(output, transcripts=True, reuse_transcripts=False):
    output.mkdir(parents=True, exist_ok=True)
    details = pd.read_parquet(ROOT / 'data/case_detail.parquet')
    listed = pd.read_parquet(ROOT / 'data/cases_by_term.parquet')
    argument_ids = set()
    for path in sorted((ROOT / 'data').glob('transcripts_*.parquet')):
        argument_ids.update(str(v) for v in pd.read_parquet(path, columns=['argument_id']).argument_id.unique())
    catalog = {p: constants('pages/' + p + '.py') for p in ['History', 'Analysis', 'Topics', 'People', '8_Presidential_Legacy', '13_Historical_Data', '9_Predictions', '10_Research', '12_Geography']}
    catalog['legal'] = json.loads((ROOT / 'pages/legal_data.json').read_text(encoding='utf-8'))
    catalog['currentJustices'] = json.loads((ROOT / 'data_files/current_justices.json').read_text())
    catalog['advocates'] = pd.read_parquet(ROOT / 'data_files/advocate_stats.parquet').to_dict('records')
    justices, cases, documents, full, seen = {}, [], [], {}, set()
    circuit_data = pd.read_parquet(ROOT / 'data_files/circuit_stats.parquet').to_dict('records')
    circuit_by_case = {(int(r['term']), r['name']): r for r in circuit_data}
    history = catalog['History'].get('JUSTICES', [])
    leans = {j[0]: j[4] for j in history}
    for row in details.to_dict('records'):
        d = clean(row)
        for field in ['decisions', 'timeline', 'lower_court', 'citation', 'decided_by', 'heard_by', 'advocates', 'oral_argument_audio', 'written_opinion', 'related_cases', 'location']:
            d[field] = decoded(d.get(field), [] if field in ['decisions','timeline','heard_by','advocates','oral_argument_audio','written_opinion','related_cases'] else {})
            if isinstance(d[field], list):
                d[field] = [v for v in d[field] if isinstance(v, dict)]
        key, term = case_key(d['href']), int(d['term'])
        decisions = [v for v in d['decisions'] if isinstance(v, dict)]
        primary = max(enumerate(decisions), key=lambda v: (sum((x.get('vote') or '').lower() in ('dissent','minority') for x in (v[1].get('votes') or [])), len((v[1].get('votes') or [])), v[0]), default=(0, {}))[1]
        votes = []
        for v in (primary.get('votes') or []):
            member = v.get('member') or {}
            votes.append({'name': member.get('name', 'Unknown'), 'vote': v.get('vote',''), 'opinion': v.get('opinion_type','')})
        for member in (d.get('decided_by') or {}).get('members', []):
            name = member['name']
            record = {'id': str(member.get('ID', name)), 'name': name, 'roles': member.get('roles', []), 'image': (member.get('thumbnail') or {}).get('href', ''), 'lean': leans.get(name, 'Unclassified')}
            justices[name] = record
        timeline = {v.get('event','').lower(): date_iso((v.get('dates') or [None])[0]) for v in d['timeline']}
        loc = d.get('location') or {}
        circ = circuit_by_case.get((term, d['name']), {})
        majority = sum(v['vote'].lower() in ('majority', 'concurrence') for v in votes)
        dissent = sum(v['vote'].lower() in ('minority','dissent') for v in votes)
        c = {'id': key, 'name': text(d['name']), 'term': term, 'docket': text(d.get('docket_number')), 'issue': infer_issue_area(d), 'outcome': infer_disposition(d), 'circuit': circ.get('circuit','Other'), 'court': (d.get('lower_court') or {}).get('name','Unknown'), 'state': loc.get('province_name') or '', 'stateCode': loc.get('province') or '', 'argued': timeline.get('argued',''), 'decided': timeline.get('decided',''), 'split': f'{majority}-{dissent}' if votes else '', 'majority': majority, 'dissent': dissent, 'votes': votes, 'question': text(d.get('question')), 'snippet': text(d.get('facts_of_the_case'))[:360], 'citation': ' '.join(str((d.get('citation') or {}).get(k,'')) for k in ['volume','page']), 'party': text(d.get('first_party')), 'winner': text(primary.get('winning_party')), 'audio': len(d['oral_argument_audio']), 'detail': True}
        cases.append(c)
        seen.add(key)
        full[key] = {'id': key, 'name': c['name'], 'facts': text(d.get('facts_of_the_case')), 'question': c['question'], 'holding': text(d.get('conclusion')), 'description': text(d.get('description')), 'firstParty': d.get('first_party'), 'secondParty': d.get('second_party'), 'lowerCourt': d.get('lower_court'), 'timeline': d['timeline'], 'decisions': [{'description': text(v.get('description')), 'winner': v.get('winning_party'), 'votes': [{'name': (vv.get('member') or {}).get('name'), 'vote': vv.get('vote'), 'opinion': vv.get('opinion_type')} for vv in (v.get('votes') or [])]} for v in decisions], 'opinions': [{'title': v.get('title'), 'type': v.get('type'), 'author': text((v.get('author') or {}).get('name') if isinstance(v.get('author'),dict) else v.get('author') or v.get('judge_full_name')), 'url': v.get('justia_opinion_url')} for v in d['written_opinion']], 'advocates': [{'name': (v.get('advocate') or {}).get('name','Unknown'), 'description': text(v.get('advocate_description'))} for v in d['advocates']], 'arguments': [{'id': str(v.get('id')), 'title': text(v.get('title')), 'transcriptAvailable': str(v.get('id')) in argument_ids} for v in d['oral_argument_audio']], 'oyez': d['href'].replace('api.oyez.org','www.oyez.org'), 'justia': d.get('justia_url'), 'location': loc}
        documents.append(' '.join([c['name']] * 3 + [c['question']] * 2 + [full[key]['facts'], full[key]['holding']]))
    for row in listed.to_dict('records'):
        if case_key(row['href']) not in seen:
            cases.append({'id': case_key(row['href']), 'name': text(row['name']), 'term': int(row['term']), 'docket': text(row.get('docket_number')), 'issue':'Unknown','outcome':'Unknown','circuit':'Other','court':'Unknown','state':'','stateCode':'','argued':'','decided':'','split':'','majority':0,'dissent':0,'votes':[],'question':text(row.get('question')),'snippet':text(row.get('description')),'party':'','winner':'','audio':0,'detail':False})
            documents.append(' '.join([text(row['name'])]*3 + [text(row.get('question'))]))
    # A compact, reproducible inverted TF-IDF index; querying runs in a browser Worker.
    vectorizer = TfidfVectorizer(stop_words='english', strip_accents='unicode', sublinear_tf=True, min_df=1, max_df=.95, max_features=70000)
    matrix = vectorizer.fit_transform(documents).tocsc()
    postings = []
    for column in range(matrix.shape[1]):
        start, end = matrix.indptr[column:column+2]
        postings.append([matrix.indices[start:end].tolist(), [round(float(v),5) for v in matrix.data[start:end]]])
    write(output / 'search.json', {'terms': vectorizer.get_feature_names_out().tolist(), 'idf': [round(float(v),5) for v in vectorizer.idf_], 'postings': postings, 'ids': [c['id'] for c in cases], 'names': [c['name'] for c in cases], 'dockets': [c['docket'] for c in cases]})
    write(output / 'cases.json', cases)
    for key, d in full.items():
        write(output / 'cases' / (key + '.json'), d)
    for path in sorted((ROOT / 'data_files/oyez_data/justices').glob('people_*.json')):
        profile = json.loads(path.read_text(encoding='utf-8'))
        name = profile.get('name')
        if name in justices:
            justices[name]['biography'] = text(profile.get('biography'))
            justices[name]['roles'] = profile.get('roles') or justices[name]['roles']
    catalog['justices'] = sorted(justices.values(), key=lambda v: v['name'])
    write(output / 'catalog.json', catalog)
    if (ROOT / 'data/web_model.json').exists():
        shutil.copyfile(ROOT / 'data/web_model.json', output / 'model.json')
    argument_count = 0
    if transcripts and reuse_transcripts:
        missing = [key for key in argument_ids if not (output / 'arguments' / (key + '.json')).exists()]
        if missing:
            raise RuntimeError(f'Cannot reuse incomplete transcripts: {len(missing)} sessions missing. Run the full export.')
        argument_count = len(argument_ids)
    elif transcripts:
        for path in sorted((ROOT / 'data').glob('transcripts_*.parquet')):
            frame = pd.read_parquet(path)
            for argument, rows in frame.groupby('argument_id', sort=False):
                turns = [{'speaker': text(v['speaker_name']), 'start': round(float(v['start']),2), 'stop': round(float(v['stop']),2), 'text': text(v['text'])} for v in rows.sort_values(['section_idx','turn_idx']).to_dict('records')]
                write(output / 'arguments' / (str(argument) + '.json'), {'id': str(argument), 'title': str(rows.iloc[0]['argument_title']), 'turns': turns})
                argument_count += 1
            print(f'Exported {path.name}', flush=True)
    # Stamp the release from source content, not wall-clock time, for reproducible builds.
    digest = hashlib.sha256()
    inputs = sorted((ROOT / 'data').glob('*.parquet')) + sorted((ROOT / 'pages').glob('*.py')) + [ROOT/'pages/legal_data.json', ROOT/'data_files/current_justices.json', ROOT/'data_files/advocate_stats.parquet', ROOT/'data_files/circuit_stats.parquet', Path(__file__)]
    if (ROOT / 'data/web_model.json').exists():
        inputs.append(ROOT / 'data/web_model.json')
    inputs.extend(sorted((ROOT / 'data_files/oyez_data/justices').glob('people_*.json')))
    for p in inputs:
        digest.update(p.name.encode()); digest.update(p.read_bytes())
    updated = max(c['decided'] for c in cases if c['decided'])
    write(output / 'manifest.json', {'version':digest.hexdigest()[:16], 'cases':len(cases),'details':len(full),'arguments':argument_count,'terms':sorted({c['term'] for c in cases},reverse=True),'latestDecision':updated,'source':'Oyez snapshots','transcriptsIncluded':transcripts})
    public = output.parent
    shutil.copyfile(ROOT / 'data_files/logo.png', public / 'brand.png')
    atlas = ROOT / 'web/node_modules/us-atlas/states-10m.json'
    if atlas.exists():
        shutil.copyfile(atlas, public / 'states.json')
    files = list(output.rglob('*.json'))
    oversized = [str(p.relative_to(output)) for p in files if p.stat().st_size > 24 * 1024**2]
    if len(files) > 19000 or oversized:
        raise RuntimeError(f'Static asset limits exceeded: {len(files)} files; oversized={oversized}')
    print(f'Built {len(cases)} cases, {argument_count} arguments, {len(files)} files; {sum(p.stat().st_size for p in files)/1024**2:.1f} MiB', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'web/public/data')
    parser.add_argument('--skip-transcripts', action='store_true', help='Fast local builds only; production requires full transcripts')
    parser.add_argument('--reuse-transcripts', action='store_true', help='Reuse existing session exports after verifying every source argument ID is present')
    args = parser.parse_args()
    build(args.output, not args.skip_transcripts, args.reuse_transcripts)
