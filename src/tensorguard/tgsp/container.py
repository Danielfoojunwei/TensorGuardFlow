import zipfile
import os
import io
from typing import List, Dict
from .crypto import get_sha256

MAX_FILE_SIZE = 100 * 1024 * 1024 # 100MB safety limit

class TGSPContainer:
    def __init__(self, path: str, mode: str = 'r'):
        self.path = path
        self.mode = mode
        self.zip = zipfile.ZipFile(path, mode=mode)

    def write_file(self, arcname: str, data: bytes):
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File {arcname} exceeds safety limit of {MAX_FILE_SIZE} bytes")
        self.zip.writestr(arcname, data)

    def read_file(self, arcname: str) -> bytes:
        info = self.zip.getinfo(arcname)
        if info.file_size > MAX_FILE_SIZE:
             raise ValueError(f"File {arcname} exceeds safety limit of {MAX_FILE_SIZE} bytes")
        return self.zip.read(arcname)

    def list_files(self) -> List[str]:
        return self.zip.namelist()

    def get_inventory_hashes(self) -> Dict[str, str]:
        import hashlib
        hashes = {}
        for info in self.zip.infolist():
            name = info.filename
            if name.endswith("/") or name.startswith("META/"):
                continue
            
            if info.file_size > MAX_FILE_SIZE:
                 raise ValueError(f"File {name} exceeds safety limit of {MAX_FILE_SIZE} bytes")

            h = hashlib.sha256()
            with self.zip.open(name) as f:
                total_read = 0
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    total_read += len(chunk)
                    if total_read > MAX_FILE_SIZE:
                         raise ValueError(f"File {name} stream exceeded limit during hash")
                    h.update(chunk)
            hashes[name] = h.hexdigest()
        return hashes

    def close(self):
        self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def extract_safely(zf: zipfile.ZipFile, name: str, out_dir: str):
    """Secure extraction helper with path traversal and size protection."""
    info = zf.getinfo(name)
    if info.file_size > MAX_FILE_SIZE:
        raise ValueError(f"Security: {name} is too large ({info.file_size} bytes)")

    # Normalize paths for strict comparison
    abs_out_dir = os.path.abspath(out_dir)
    target_path = os.path.normpath(os.path.join(abs_out_dir, name))
    
    if not target_path.startswith(abs_out_dir + os.sep) and target_path != abs_out_dir:
        raise ValueError(f"Zip-Slip attempt detected: {name}")
    
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with zf.open(name) as source, open(target_path, 'wb') as target:
        import shutil
        shutil.copyfileobj(source, target)
