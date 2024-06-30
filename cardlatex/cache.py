import tempfile
import hashlib
from pathlib import Path


class Cache:
    def __init__(self, file: Path):
        self._wd = file.parent

        tempdir = Path(tempfile.gettempdir()) / 'cardlatex'
        cachedir = hashlib.sha1(Path(file).resolve().as_posix().encode('utf-8')).hexdigest()

        self._cache = tempdir / cachedir
        self._cache.mkdir(exist_ok=True, parents=True)

    def working_directory(self) -> Path:
        return self._wd

    def cache_directory(self) -> Path:
        return self._cache
