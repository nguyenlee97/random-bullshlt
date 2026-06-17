import ast, sys

files = [
    'router.py',
    'handlers/email.py',
    'handlers/report.py',
    'main.py',
]

ok = True
for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'ERR {f}: {e}')
        ok = False

sys.exit(0 if ok else 1)
