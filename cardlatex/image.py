import os
from pathlib import Path

from wand.image import Image as WandImage


def is_relative(file: str):
    return not file.startswith('/') or bool(Path(file).drive)


suffixes = '.pdf,.ai,.png,.jpg,.jpeg,.jp2,.jpf,.bmp,.ps,.eps,.mps'.split(',')
DRAFT_TARGET_SIZE = 51200  # in bytes


class Image:
    def __init__(self, tex_dir: Path, cache_dir: Path):
        self._tex_dir = tex_dir
        self._tex_path: Path | None = None
        self._cache_dir = cache_dir
        self._cache_path: Path | None = None

    def _set_source_from_path(self, file: Path):
        self._tex_path = file
        if self._tex_path.is_relative_to(self._tex_dir):
            self._cache_path = self._cache_dir / self._tex_path.relative_to(self._tex_dir)

    def find_source_from_directories(self, file: str, *directories: Path):
        if directories:
            for directory in directories:
                path = directory / file
                if path.suffix:
                    if path.exists():
                        return self._set_source_from_path(path)
                else:
                    for suffix in suffixes:
                        if path.with_suffix(suffix).exists():
                            return self._set_source_from_path(path.with_suffix(suffix))
        raise FileNotFoundError(f'{file} not found in any directory: {directories}')

    def find_source_from_cache(self, file: Path):
        file_info = file.with_suffix('')
        if file_info.exists():
            with open(file_info, 'r') as f:
                self._tex_path = Path(f.read())
            self._cache_path = file.with_suffix(self._tex_path.suffix)
        else:
            raise FileNotFoundError(f'{file_info} cache object not found')

    @property
    def _cache_info(self) -> Path:
        return self._cache_path.with_suffix('')

    def resample(self):
        if self._tex_path is not None and self._tex_path.exists() and self._cache_path is not None:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            if self._cache_info.exists():
                if self._cache_info.stat().st_mtime_ns == self._tex_path.stat().st_mtime_ns:
                    return
            else:
                with open(self._cache_info, 'w', encoding='utf-8') as f:
                    f.write(str(self._tex_path.resolve().as_posix()))

            graphics_stat = self._tex_path.stat()
            with WandImage(filename=self._tex_path.as_posix()) as source:
                with source.convert(self._tex_path.suffix[1:]) as target:
                    st_size = graphics_stat.st_size
                    if st_size > 0 and st_size > DRAFT_TARGET_SIZE:
                        target.transform(resize=f'{round(100 * DRAFT_TARGET_SIZE / st_size)}%')
                    target.save(filename=self._cache_path)

            os.utime(self._cache_info, ns=(graphics_stat.st_atime_ns, graphics_stat.st_mtime_ns))
        elif self._cache_path.exists() and not self._tex_path.exists():
            os.remove(self._cache_path)
            os.remove(self._cache_info)
