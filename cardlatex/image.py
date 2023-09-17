import os
from pathlib import Path

from wand.image import Image as WandImage


class Image:
    def __init__(self, cache_dir: Path, file_path: Path):
        self._cache_path = cache_dir / file_path
        self._cache_info = self._cache_path.with_suffix('')
        self._file_path = file_path
        self._resampled = False

    @property
    def resampled(self) -> bool:
        return self._resampled

    @property
    def path(self) -> Path:
        return self._file_path

    def __hash__(self):
        return hash(self._cache_path)

    def __eq__(self, other):
        if not isinstance(other, Image):
            return False
        return other._cache_path == self._cache_path

    def resample(self, graphics_dir: Path, quality: int):
        if self.resampled:
            return

        graphics_path = graphics_dir / self._file_path
        if not graphics_path.exists():
            return

        if self._cache_info.exists():
            equal_stat = self._cache_info.stat().st_mtime_ns == graphics_path.stat().st_mtime_ns
            with open(self._cache_info, 'r') as f:
                cache_quality = int(f.read())
            if equal_stat and cache_quality == quality:
                self._resampled = True

        with WandImage(filename=graphics_path.resolve().as_posix()) as source:
            with source.convert(graphics_path.suffix[1:]) as target:
                if quality < 100:
                    target.transform(resize=f'{quality}%')
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                target.save(filename=self._cache_path)

        with open(self._cache_info, 'w') as f:
            f.write(str(quality))

        graphics_stat = graphics_path.stat()
        os.utime(self._cache_info, ns=(graphics_stat.st_atime_ns, graphics_stat.st_mtime_ns))
        self._resampled = True
