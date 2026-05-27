import os
root = os.path.join(os.getcwd(), 'data_files', 'oyez_data', 'oral_arguments')
if not os.path.isdir(root):
    print('NO_DIR')
    raise SystemExit(1)
files = [f for f in os.listdir(root) if f.endswith('.json')]
count = len(files)
total = sum(os.path.getsize(os.path.join(root, f)) for f in files)
print('count', count)
print('bytes', total)
print('MB', total / 1024 / 1024)
largest = sorted(files, key=lambda f: os.path.getsize(os.path.join(root,f)), reverse=True)[:10]
for f in largest:
    size = os.path.getsize(os.path.join(root, f))
    print(f'{f}\t{size}\t{size/1024:.1f} KB')
