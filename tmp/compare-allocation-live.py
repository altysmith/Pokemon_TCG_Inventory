import subprocess,difflib
from pathlib import Path
for name in ['app.py','deck_checker.py']:
 base=subprocess.check_output(['git','show','HEAD:'+name]).decode().splitlines()
 live=Path('tmp/allocation-live',name).read_text(encoding="utf-8").splitlines()
 print(name, 'baseline matches live:',base==live)
 if base!=live:
  print('\n'.join(difflib.unified_diff(base,live,fromfile='git',tofile='live')))

