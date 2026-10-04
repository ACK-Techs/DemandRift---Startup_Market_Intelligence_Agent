"""Remove only old, incomplete scratch files; canonical captures/receipts are retained."""
import os
from pathlib import Path
import re
import stat
import time

_SCRATCH=re.compile(r'(?:\.[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|\.tmp-[0-9a-f]{32})\Z')

def cleanup(root, *, now=None, max_files=1000):
    root=Path(root)
    if not root.is_absolute() or root.resolve(strict=True)!=root: raise ValueError('Canonical retention root required')
    now=time.time() if now is None else now
    removed=0
    for directory,children,names in os.walk(root,followlinks=False):
        children[:]=[name for name in children if not (Path(directory)/name).is_symlink()]
        if len(Path(directory).relative_to(root).parts)>5:
            children[:]=[];continue
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for name in names:
                if not _SCRATCH.fullmatch(name): continue
                info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077 or info.st_uid!=os.geteuid() or now-info.st_mtime<86400: continue
                os.unlink(name,dir_fd=fd);removed+=1
                if removed>=max_files: return removed
        finally: os.close(fd)
    return removed
