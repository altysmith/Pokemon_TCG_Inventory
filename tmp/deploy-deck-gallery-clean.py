from pathlib import Path
import hashlib, os, shutil, subprocess, tarfile, urllib.request
root = Path('/home/ealtenho/pokemon-collection')
release = Path('/home/ealtenho/pokemon-collection-releases/deck-gallery-clean-20260919')
files = ['deck.js', 'style.css']
assert not (root / '.git').exists()
release.mkdir(parents=True, exist_ok=True)
backup = subprocess.check_output(['python3', str(root/'deploy/backup.py')], text=True)
(release/'database-backup.txt').write_text(backup)
print(backup.strip())
with tarfile.open(release/'app-before.tar.gz', 'w:gz') as archive:
    for entry in root.iterdir():
        if entry.name not in ('user_data', 'data', '.venv', 'venv', '__pycache__'):
            archive.add(entry, arcname=entry.name)
previous = release/'previous'
previous.mkdir(exist_ok=True)
for name in files:
    shutil.copy2(root/'web'/name, previous/name)
rollback = '#!/bin/sh\nset -eu\nsudo systemctl stop pokemon-collection.service\n'
for name in files:
    rollback += f'cp "{previous/name}" "{root / "web" / name}"\n'
rollback += 'sudo systemctl start pokemon-collection.service\n'
(release/'rollback.sh').write_text(rollback)
(release/'rollback.sh').chmod(0o700)
subprocess.run(['sudo','systemctl','stop','pokemon-collection.service'],check=True)
try:
    for name in files:
        destination = root/'web'/name
        temporary = destination.with_suffix(destination.suffix+'.next')
        shutil.copy2(release/'staged'/name, temporary)
        temporary.chmod(destination.stat().st_mode)
        os.replace(temporary, destination)
finally:
    subprocess.run(['sudo','systemctl','start','pokemon-collection.service'],check=True)
print('Activated; rollback:', release/'rollback.sh')

