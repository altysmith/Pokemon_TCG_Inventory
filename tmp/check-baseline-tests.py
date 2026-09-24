import subprocess, types, sys, unittest
from pathlib import Path
root=Path.cwd()
module=types.ModuleType('app')
module.__file__=str(root/'app.py')
sys.modules['app']=module
exec(compile(subprocess.check_output(['git','show','HEAD:app.py']).decode('utf-8'), module.__file__, 'exec'), module.__dict__)
sys.path.insert(0,str(root/'tests'))
from test_app import AppTests
names=['test_catalog_validated_repair_handles_dark_badges','test_low_confidence_alternate_can_supply_unique_exact_dark_badge','test_partial_tef_badge_requires_retained_prefix_and_both_numbers']
unittest.TextTestRunner().run(unittest.TestSuite(AppTests(name) for name in names))
