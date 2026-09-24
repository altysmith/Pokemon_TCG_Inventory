from pathlib import Path
import hashlib, os, shutil, subprocess, tarfile, time, urllib.request
root=Path('/home/ealtenho/pokemon-collection')
release=Path('/home/ealtenho/pokemon-collection-releases/compact-allocation-badges-20260919')
files=['deck_allocations.py','web/inventory.js','web/style.css']
expected={}
for name,digest in expected.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, 'Live backend changed; stopping'
backup=subprocess.check_output(['python3',str(root/'deploy/backup.py')],text=True)
(release/'database-backup.txt').write_text(backup)
print(backup.strip())
with tarfile.open(release/'app-before.tar.gz','w:gz') as archive:
    for entry in root.iterdir():
        if entry.name not in ('user_data','data','.venv','venv','__pycache__'):
            archive.add(entry,arcname=entry.name)
rollback='#!/bin/sh\nset -eu\nsudo systemctl stop pokemon-collection.service\n'
for name in files:
    old=release/'previous'/name
    old.parent.mkdir(parents=True,exist_ok=True)
    if (root/name).exists():
        shutil.copy2(root/name,old)
        rollback+=f'cp "{old}" "{root/name}"\n'
    else:
        rollback+=f'rm -f "{root/name}"\n'
rollback+='sudo systemctl start pokemon-collection.service\n'
(release/'rollback.sh').write_text(rollback)
(release/'rollback.sh').chmod(0o700)
subprocess.run(['sudo','systemctl','stop','pokemon-collection.service'],check=True)
try:
    for name in files:
        destination=root/name
        temporary=destination.with_suffix(destination.suffix+'.next')
        shutil.copy2(release/'staged'/name,temporary)
        temporary.chmod(destination.stat().st_mode if destination.exists() else 0o644)
        os.replace(temporary,destination)
    subprocess.run(['sudo','systemctl','start','pokemon-collection.service'],check=True)
    for attempt in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8766/health',timeout=3) as response:
                assert response.status==200
                print(response.read().decode())
            break
        except Exception:
            if attempt==19: raise
            time.sleep(.5)
    for name in files:
        assert (root/name).read_bytes()==(release/'staged'/name).read_bytes()
except Exception:
    subprocess.run(['sh',str(release/'rollback.sh')],check=True)
    raise
print('Activated and verified 3 files. Rollback:',release/'rollback.sh')
