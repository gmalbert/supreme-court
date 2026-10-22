"""Compile project Python sources without importing or executing application code."""
from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', 'venv', 'venv_mac', 'node_modules', 'dist', '.wrangler', '__pycache__', '.pytest_cache'}


def main():
    sources = []
    # Prune dependency directories before descending into them.
    for directory, folders, filenames in ROOT.walk():
        folders[:] = [name for name in folders if name not in EXCLUDED]
        sources.extend(directory / name for name in filenames if name.endswith('.py'))
    output = ROOT / '.pytest_cache' / 'py_compile'
    failures = []
    for path in sorted(sources):
        relative = path.relative_to(ROOT)
        target = output / relative.with_suffix('.pyc')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            py_compile.compile(str(path), cfile=str(target), doraise=True)
        except py_compile.PyCompileError as error:
            failures.append((relative, str(error)))
    for path, error in failures:
        print(f'{path}: {error}', file=sys.stderr)
    print(f'py_compile: {len(sources) - len(failures)}/{len(sources)} Python files passed.')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
