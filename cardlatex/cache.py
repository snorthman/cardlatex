import tempfile
import hashlib
from pathlib import Path


class Cache:
    def __init__(self, file: Path | str):
        self._file = Path(file)
        self._wd = self.file_xml.parent

        tempdir = Path(tempfile.gettempdir()) / 'cardlatex'
        cachedir = hashlib.sha1(self.file_xml.resolve().as_posix().encode('utf-8')).hexdigest()

        self._cache = tempdir / cachedir
        self._cache.mkdir(exist_ok=True, parents=True)

    @property
    def file_xml(self) -> Path:
        return self._file

    def working_directory(self) -> Path:
        return self._wd

    def cache_directory(self) -> Path:
        return self._cache
