import hashlib
import importlib.resources
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Set

import numpy as np
import pandas as pd

from .config import Config
from .image import Image


def cardlatexprop(prop: str = ''):
    return rf'\cardlatex configuration object' + (f'"{prop}"' if prop else '')


def sha256(encode: str) -> str:
    obj = hashlib.sha1()
    obj.update(encode.encode('utf-8'))
    return obj.hexdigest()


class Tex:
    def __init__(self, tex: Path):
        self._path = tex
        self._path_xlsx = self._path.with_suffix('.xlsx')
        self._template = self.template()

        # with open(tex.parent / tex.with_suffix('.xml')) as f:
        #     self._xml = f.read()
        with open(tex, 'r') as f:
            self._tex = f.read()

        self._config = Config(self._tex)
        self._variables = frozenset({r.group(1) for r in re.finditer(r'<\$(\w+)\$>', self._config.front + self._config.back)})
        self._cache_dir = Path(tempfile.gettempdir()) / 'cardlatex' / sha256(self._path.resolve().as_posix())

    @staticmethod
    def template() -> str:
        with importlib.resources.open_text('cardlatex.resources', 'template.tex') as f:
            return f.read()

    def generate(self):
        data = {key: [] for key in self._variables}
        pd.DataFrame(data).to_excel(self._path_xlsx, index=False, sheet_name='cardlatex')

    def _load_xslx(self):
        if self._path_xlsx.exists():
            xlsx = pd.read_excel(self._path_xlsx, sheet_name='cardlatex')
            unknowns = self._variables.symmetric_difference(xlsx)
            if unknowns:
                print(f'unknown columns [{", ".join(unknowns)}] are ignored')

            if self._config.include:
                rows = len(xlsx)
                rows_expected = max(self._config.include) + 1
                if rows_expected - rows > 0:
                    rows_extra = pd.DataFrame(np.nan, columns=xlsx.columns, index=range(rows, rows_expected))
                    xlsx = pd.concat([xlsx, rows_extra])

            return xlsx
        return pd.DataFrame()

    def _prepare_tex(self, data: pd.DataFrame, **kwargs):
        mirror = kwargs.get('mirror', False)
        build_all = kwargs.get('build_all', False)

        content = ['']
        toggles = set()

        tikz = r'\begin{tikzcard}[' + self._config.dpi + ']{' + self._config.width + '}{' + self._config.height + '}%\n'
        edges = [self._config.front]
        if mirror or 'back' in self._config:
            edges.append(self._config.back)

        for row in range(len(data)) if build_all else self._config.include:
            card = ['']
            for edge in edges:
                for key in self._variables:
                    item = data[key][row]
                    value = '' if pd.isna(item) else item

                    if re.search(r'\\if<\$' + key + r'\$>', edge):
                        toggles.add(key)
                        card[0] += (r'\toggletrue{' if bool(value) else r'\togglefalse{') + key + '}\n'

                    edge = edge.replace(f'\\if<${key}$>', r'\ifvar{' + key + '}')
                    edge = edge.replace(f'<${key}$>', value)

                card.append(tikz + edge + '\n\\end{tikzcard}%\n')
            content.extend(card)

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

    def _resample_images(self, tex: str, **kwargs):
        quality = kwargs.get('quality') or self._config.quality
        if quality == 100:
            return

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

        self._cache_dir.mkdir(exist_ok=True, parents=True)
        images: Set[Image] = set({Image(self._cache_dir, Path(r.group(1))) for r in re.finditer(r'\\includegraphics.*?{([^}]+)}', tex[begin_document.end():])})
        for img in images:
            for graphics_dir in graphics_dirs:
                img.resample(graphics_dir, quality)
            if not img.resampled:
                raise FileNotFoundError(img.path.as_posix())

    def build(self, **kwargs):
        data = self._load_xslx()
        tex = self._prepare_tex(data, **kwargs)
        self._resample_images(tex, **kwargs)

        with open(tex_generated := self._cache_dir / self._path.name, 'w') as f:
            f.write(tex)
        with open(self._path.with_suffix('.cardlatex.tex'), 'w') as f:
            f.write(tex)

        def delete_auxiliary(suffix: str):
            aux = tex_generated.with_suffix(suffix)
            if aux.exists():
                os.remove(aux)

        cmd = f'xelatex.exe -interaction=nonstopmode "{tex_generated.stem}".tex'
        try:
            result = subprocess.run(cmd, cwd=tex_generated.parent, capture_output=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise subprocess.SubprocessError(f'xelatex failed for {tex_generated.name}')
        except subprocess.SubprocessError as e:
            shutil.move(tex_generated.with_suffix('.log'), self._path.with_suffix('.log'))
            raise e
        else:
            delete_auxiliary('.log')
            shutil.move(tex_generated.with_suffix('.pdf'), self._path.with_suffix('.pdf'))
        finally:
            delete_auxiliary('.aux')
