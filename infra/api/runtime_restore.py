"""Administrator restore rehearsal into a new database and a separate private folder."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
from uuid import uuid4
from runtime_release import BASE, COMMAND_ENVIRONMENT, ReleaseError, private_file, archive_hash, locked


def checked_archive(folder, record):
    if set(record)!={'archive','sha256','bytes'} or not re.fullmatch(r'[A-Za-z0-9._-]+',record['archive']): raise ReleaseError('Invalid backup archive record')
    path=folder/record['archive'];private_file(path)
    if path.stat().st_size!=record['bytes'] or record['bytes']>1024**3: raise ReleaseError('Backup size differs')
    with path.open('rb') as source:
        if archive_hash(source)!=record['sha256']: raise ReleaseError('Backup hash differs')
    return path


def restore(manifest, *, command=subprocess.run):
    manifest=Path(manifest)
    if manifest.parent!=BASE/'backups': raise ReleaseError('Managed backup manifest required')
    private_file(manifest)
    if manifest.stat().st_size>4096: raise ReleaseError('Bounded backup manifest required')
    data=json.loads(manifest.read_text())
    database=checked_archive(manifest.parent,{key:data[key] for key in ('archive','sha256','bytes')})
    raw=checked_archive(manifest.parent,data['artifacts'])
    name='demandrift_restore_'+uuid4().hex
    folder=BASE/'restore-checks'/name
    folder.mkdir(mode=0o700,parents=True)
    # Never extract links, devices, absolute paths or traversal from an archive.
    count=total=0
    with tarfile.open(raw) as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            count+=1;total+=member.size
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='artifacts' or count>100000 or total>1024**3:
                raise ReleaseError('Unsafe artifact archive')
            target=folder.joinpath(*path.parts)
            if member.isdir(): target.mkdir(mode=0o700,parents=True,exist_ok=True)
            elif member.isfile() and member.size<=2_000_000:
                target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'wb') as destination, archive.extractfile(member) as source:
                    destination.write(source.read(2_000_001))
            else: raise ReleaseError('Unsafe artifact member')
    prefix=['docker','compose','-p','demandrift-api','-f',str(BASE/'runtime.compose.yml'),'exec','-T','postgres','sh','-eu','-c']
    env=dict(COMMAND_ENVIRONMENT,APP_REVISION=data['revision'])
    setup='IFS= read -r PGPASSWORD < /run/secrets/postgres-password || [ -n "$PGPASSWORD" ]; export PGPASSWORD; '
    command([*prefix,setup+f'exec createdb -U demandrift_admin {name}'],check=True,capture_output=True,timeout=30,env=env)
    with database.open('rb') as source:
        command([*prefix,setup+f'exec pg_restore --exit-on-error -U demandrift_admin -d {name}'],stdin=source,check=True,capture_output=True,timeout=180,env=env)
    return name,folder


def main():
    try:
        if os.getuid()!=0 or len(sys.argv)!=2: raise ReleaseError('Administrator manifest operation required')
        with locked(BASE/'deploy.lock'): name,folder=restore(sys.argv[1])
        print('Private restore rehearsal complete:',name)
        return 0
    except Exception:
        print('Restore rehearsal unavailable; production database and volumes were preserved.',file=sys.stderr)
        return 1

if __name__=='__main__': raise SystemExit(main())
