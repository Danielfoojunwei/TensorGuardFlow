
import tarfile
import os
import io

def deterministic_filter(tarinfo):
    """Normalize tar info for determinism."""
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = 0
    
    # Simple permissions
    if tarinfo.isdir():
        tarinfo.mode = 0o755
    else:
        # Preserve executable bit if needed? 
        # For simplicity and max determinism, force 644 unless marked executable
        if tarinfo.mode & 0o100:
             tarinfo.mode = 0o755
        else:
             tarinfo.mode = 0o644
             
    # Remove extended attributes if possible (pax headers handled by format=gnu/ustar)
    return tarinfo

def create_deterministic_tar(source_dir: str, output_path: str = None) -> bytes:
    """
    Create a deterministic tarball of a directory.
    If output_path provided, writes to file.
    Returns bytes if output_path is None.
    """
    
    # We write to a BytesIO first to ensure hashing stability before encryption
    # Or write strictly to disk.
    
    bio = io.BytesIO() if output_path is None else open(output_path, "wb")
    
    try:
        # Use simple USTAR format for compatibility
        with tarfile.open(fileobj=bio if output_path is None else None, name=output_path if output_path else None, mode="w:gz", format=tarfile.USTAR_FORMAT) as tar:
            # Walk directory sorted
            for root, dirs, files in os.walk(source_dir):
                dirs.sort() # Sort directories in-place for recursion
                files.sort()
                
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_dir)
                    # Normalize path separators
                    arcname = rel_path.replace(os.sep, "/")
                    
                    tar.add(full_path, arcname=arcname, recursive=False, filter=deterministic_filter)
                    
    finally:
        if output_path:
            bio.close()
            
    if output_path is None:
        return bio.getvalue()
    return b""
