import os, json
root = os.path.join(os.getcwd(), 'data_files', 'oyez_data', 'oral_arguments')
if not os.path.isdir(root):
    print('NO_ORAL_DIR')
    raise SystemExit(1)
years = set()
for fn in os.listdir(root):
    if not fn.endswith('.json'):
        continue
    path = os.path.join(root, fn)
    try:
        with open(path, encoding='utf-8') as f:
            j = json.load(f)
    except Exception:
        continue
    for key in ('decision_date', 'case_date', 'date', 'argument_date', 'oral_argument_date', 'argument_dates'):
        val = j.get(key)
        if isinstance(val, str) and len(val) >= 4 and val[:4].isdigit():
            years.add(int(val[:4]))
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str) and len(v) >= 4 and v[:4].isdigit():
                    years.add(int(v[:4]))
print('count', len(years))
if years:
    print('min', min(years), 'max', max(years))
else:
    print('no years')
