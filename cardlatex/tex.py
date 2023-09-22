import hashlib
import importlib.resources
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Set, List

import numpy as np
import pandas as pd

from . import tempdir
from .config import Config
from .image import Image


def sha256(encode: str) -> str:
    obj = hashlib.sha1()
    obj.update(encode.encode('utf-8'))
    return obj.hexdigest()


class Tex:
    def __init__(self, tex: Path | str):
        self._path = Path(tex)
        self._template = self.template()

        with open(self._path, 'r') as f:
            self._tex = f.read()

        self._config = Config(self._tex)
        self._variables = sorted(list(({r.group(1) for r in re.finditer(r'<\$(\w+)\$>', self._config.front + self._config.back)})))
        self._cache_dir = self.get_cache_dir(self._path)
        self._cache_output_pdf = (self.cache_dir / self._path.name).with_suffix('.pdf')
        self._completed = False
        self._mirror = False

    @staticmethod
    def template() -> str:
        with importlib.resources.open_text('cardlatex.resources', 'template.tex') as f:
            return f.read()

    @staticmethod
    def get_cache_dir(tex: Path | str):
        return tempdir / sha256(Path(tex).resolve().as_posix())

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @property
    def has_back(self) -> bool:
        return 'back' in self._config or self._mirror

    @property
    def output(self) -> Path:
        return self._cache_output_pdf

    @property
    def completed(self) -> bool:
        return self._completed

    def _load_or_generate_xlsx(self):
        if self._variables:
            path_xlsx = self._path.with_suffix('.xlsx')
            if path_xlsx.exists():
                try:
                    data_existing = pd.read_excel(path_xlsx, sheet_name='cardlatex')
                except ValueError as e:
                    raise ValueError(f'{e}, ensure your .xlsx file contains a worksheet named \'cardlatex\'')

                data_columns = pd.Index([*data_existing.columns] + [c for c in self._variables if c not in data_existing])
                data_existing = data_existing.reindex(columns=data_columns)
            else:
                data_columns = pd.Index([*sorted(self._variables)])
                data_existing = pd.DataFrame().reindex(columns=data_columns)

            if self._config.include:
                rows = len(data_existing)
                rows_expected = max(self._config.include) + 1
                if rows_expected - rows > 0:
                    rows_extra = pd.DataFrame(np.nan, columns=data_existing.columns, index=range(rows, rows_expected))
                    data_existing = pd.concat([data_existing, rows_extra])

            try:
                pd.DataFrame(data_existing).to_excel(path_xlsx, index=False, sheet_name='cardlatex')
            except PermissionError:
                pass

            return data_existing
        else:
            return pd.DataFrame()

    def _prepare_tex(self, data: pd.DataFrame, **kwargs):
        self._mirror = kwargs.get('mirror', False)
        build_all = kwargs.get('build_all', False)

        tikz = '\n\\begin{tikzcard}[' + self._config.dpi + ']{' + self._config.width + '}{' + self._config.height + '}%\n'
        edges = [self._config.front]
        if self.has_back:
            edges.append(self._config.back)

        content = []
        toggles = set()
        for row in range(len(data)) if build_all or self._config.include is None else self._config.include:
            for edge in edges:
                edge_toggles = ['']
                for key in self._variables:
                    item = data[key][row]
                    value = '' if pd.isna(item) else item

                    if re.search(r'\\if<\$' + key + r'\$>', edge):
                        toggles.add(key)
                        edge_toggles.append((r'\toggletrue{' if bool(value) else r'\togglefalse{') + key + '}')

                    edge = edge.replace(f'\\if<${key}$>', r'\ifvar{' + key + '}')
                    edge = edge.replace(f'<${key}$>', value)

                content.append('\n'.join(edge_toggles) + tikz + edge + '\n\\end{tikzcard}%\n')

        content = '\n'.join(content)
        toggles = '\n'.join([r'\newtoggle{' + value + '}' for value in toggles])

        template = self._template
        for r in re.finditer(r'<\$(\w+)\$>', self._template):
            value = getattr(self._config, r.group(1))
            template = template.replace(r.group(), value)

        tex_blocks = [
            (None, template),
            ('user tex', self._tex),
            ('newtoggles', toggles),
            ('document', '\\begin{document}\n'),
            (None, content.replace('\n', '\n\t')),
            (None, '\n\\end{document}')
        ]

        tex = ''
        for header, block in tex_blocks:
            if header:
                tex += '\n\n' + '%' * 68 + '\n% ' + header.upper() + '\n\n'
            tex += block

        return tex

    def _resample_images(self, tex: str, quality: int):
        begin_document = re.search(r'\\begin{document}', tex)
        assert begin_document, r'no \begin{document}?'

        # untested
        graphics_dirs = [self._path.parent]
        for r in re.finditer(r'\\graphicspath{(.+)}', tex):
            for p in re.finditer(r'{.+}', r.group(1)):
                path = p.group()
                if path.startswith('.'):  # relative path
                    graphics_dirs.append(graphics_dirs[0] / path)
                else:
                    graphics_dirs.append(Path(path))

        images: Set[Image] = set({Image(self.cache_dir, Path(r.group(1))) for r in re.finditer(r'\\includegraphics.*?{([^}]+)}', tex[begin_document.end():])})
        for img in images:
            for graphics_dir in graphics_dirs:
                img.resample(graphics_dir, quality)
            if not img.resampled:
                raise FileNotFoundError(f'Could not find {img.path.as_posix()}')

    def _copy_inputs(self, tex: str):
        matches: List[re.Match] = list(re.finditer(r'^(.*)\\input\{(\w+)}', tex, re.M))
        for match in matches:
            if '%' in match.group(1):
                continue

            name = match.group(2) + '.tex'
            path = self._path.parent / name
            if path.exists():
                shutil.copy(path, self.cache_dir / name)

    def build(self, **kwargs) -> 'Tex':
        if self.completed:
            return self

        self.cache_dir.mkdir(exist_ok=True, parents=True)

        data = self._load_or_generate_xlsx()
        tex = self._prepare_tex(data, **kwargs)

        quality = kwargs.get('quality') or self._config.quality
        if quality < 100:
            self._resample_images(tex, quality)
        else:
            tex = tex.replace(r'%\graphicspath{{}}', r'\graphicspath{{' + self._path.parent.resolve().as_posix() + '}}')

        self._copy_inputs(tex)
        with open(tex_out := self.cache_dir / self._path.name, 'w') as f:
            f.write(tex)

        cmd = f'xelatex.exe -interaction=nonstopmode "{tex_out.stem}".tex'
        result = subprocess.run(cmd, cwd=tex_out.parent, capture_output=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if (aux := tex_out.with_suffix('.aux')).exists():
            os.remove(aux)

        if result.returncode != 0:
            shutil.copy(tex_out.with_suffix('.log'), self._path.with_suffix('.log'))
            raise subprocess.SubprocessError(f'xelatex.exe failed for {tex_out.resolve()}, see .log file')

        self._completed = True
        return self

    def release(self):
        if self.completed:
            output = self.cache_dir / self._path.name
            log, pdf = output.with_suffix('.log'), output.with_suffix('.pdf')

            shutil.copy(output.with_suffix('.tex'), self._path.with_suffix('.cardlatex.tex'))
            if log.exists():
                shutil.copy(output.with_suffix('.log'), self._path.with_suffix('.log'))
            if pdf.exists():
                shutil.move(output.with_suffix('.pdf'), self._path.with_suffix('.pdf'))
