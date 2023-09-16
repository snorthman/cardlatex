import importlib.resources
import re
import os
import tempfile
import hashlib
from pathlib import Path
from typing import List, Set

import numpy as np
import pandas as pd

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
        self._config = dict()
        self._template = self.template()

        # with open(tex.parent / tex.with_suffix('.xml')) as f:
        #     self._xml = f.read()
        with open(tex, 'r') as f:
            self._tex = f.read()

    @staticmethod
    def template() -> str:
        with importlib.resources.open_text('cardlatex.resources', 'template.tex') as f:
            return f.read()

    def _set_length_prop(self, prop: str, value: str):
        value = str(value).strip()
        assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
            ValueError(f'invalid value "{value}" for {prop}'))
        self._config[prop] = value

    @property
    def width(self) -> str:
        return self._config['width']

    @width.setter
    def width(self, value: str):
        self._set_length_prop('width', value)

    @property
    def height(self) -> str:
        return self._config['height']

    @height.setter
    def height(self, value: str):
        self._set_length_prop('height', value)

    @property
    def bleed(self) -> str:
        return self._config.get('bleed', '0')

    @bleed.setter
    def bleed(self, value: str):
        self._set_length_prop('bleed', value)

    @property
    def dpi(self) -> str:
        return self._config.get('dpi', '0')

    @dpi.setter
    def dpi(self, value: str):
        self._config['dpi'] = str(float(value))

    @property
    def quality(self) -> str:
        return self._config.get('quality', 100)

    @quality.setter
    def quality(self, value: int):
        value = int(value)
        assert 100 >= value >= 1, ValueError(f'value must be between 1 and 100 ("{value}") for quality')
        self._config['quality'] = value

    @property
    def include(self) -> List[int]:
        return self._config.get('include', None)

    @include.setter
    def include(self, value: str):
        values = value.replace(' ', '').split(',')
        include = []
        for v in values:
            if r := re.match(r'(\d+)\.{2,3}(\d+)', v):
                left, right = int(r.group(1)), int(r.group(2))
                assert left <= right, ValueError(
                    rf'{left} is larger than {right} in {v} for {cardlatexprop("include")}')
                include.extend(range(left, right + 1))
            else:
                include.append(int(v))
        self._config['include'] = include

    @property
    def front(self) -> str:
        return self._config['front']

    @front.setter
    def front(self, value: str):
        self._config['front'] = value

    @property
    def back(self) -> str:
        return self._config.get('back', self.front)

    @back.setter
    def back(self, value: str):
        self._config['back'] = value

    def _find_variables(self) -> frozenset[str]:
        return frozenset({r.group(1) for r in re.finditer(r'<\$(\w+)\$>', self.front + self.back)})

    def _get_cachedir(self) -> Path:
        return Path(tempfile.gettempdir()) / 'cardlatex' / sha256(self._path.resolve().as_posix())

    def generate(self):
        self._load_config()
        data = {key: [] for key in self._find_variables()}
        pd.DataFrame(data).to_excel(self._path_xlsx, index=False, sheet_name='cardlatex')

    def _load_config(self):
        props = set()
        matches: List[re.Match] = list(re.finditer(r'\\cardlatex\[(\w+)]\{', self._tex))

        for m, match in enumerate(matches):
            assert hasattr(Tex, prop := match.group(1)), (
                KeyError(rf'unknown {cardlatexprop(prop)}'))
            assert prop not in props, (
                KeyError(rf'duplicate {cardlatexprop(prop)}'))
            props.add(prop)

            b = 1
            rb: re.Match = None
            for rb in re.finditer(r'(?<!\\)[{}]', self._tex[match.end():]):
                b = b + (1 if rb.group() == '{' else -1)
                if b == 0:
                    break
            assert b == 0 and rb, (
                ValueError(rf'no closing bracket found for {cardlatexprop(prop)}'))

            endpos = match.end() + rb.end() - 1
            if m < len(matches) - 1:
                assert endpos < matches[m + 1].start(), (
                    ValueError(rf'{cardlatexprop()} found inside {cardlatexprop(prop)}'))

            setattr(self, prop, self._tex[match.end():endpos])

    def _load_xslx(self):
        if self._path_xlsx.exists():
            xlsx = pd.read_excel(self._path_xlsx, sheet_name='cardlatex')
            unknowns = self._find_variables().symmetric_difference(xlsx)
            if unknowns:
                print(f'unknown columns [{", ".join(unknowns)}] are ignored')

            if self.include:
                rows = len(xlsx)
                rows_expected = max(self.include) + 1
                if rows_expected - rows > 0:
                    rows_extra = pd.DataFrame(np.nan, columns=xlsx.columns, index=range(rows, rows_expected))
                    xlsx = pd.concat([xlsx, rows_extra])

            return xlsx
        return pd.DataFrame()

    def _prepare_tex(self, data: pd.DataFrame, **kwargs):
        variables = self._find_variables()

        mirror = kwargs.get('mirror', False)
        build_all = kwargs.get('build_all', False)

        content = ['']
        toggles = set()

        tikz = r'\begin{tikzcard}[' + self.dpi + ']{' + self.width + '}{' + self.height + '}%\n'
        edges = [self.front]
        if mirror or 'back' in self._config:
            edges.append(self.back)

        for row in range(len(data)) if build_all else self.include:
            card = ['']
            for edge in edges:
                for key in variables:
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
            value = getattr(self, r.group(1))
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
        quality = kwargs.get('quality') or self.quality
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

        cache_dir = self._get_cachedir()
        cache_dir.mkdir(exist_ok=True, parents=True)

        images: Set[Image] = set({Image(cache_dir, Path(r.group(1))) for r in re.finditer(r'\\includegraphics.*?{([^}]+)}', tex[begin_document.end():])})
        for img in images:
            for graphics_dir in graphics_dirs:
                img.resample(graphics_dir, quality)
            if not img.resampled:
                raise FileNotFoundError(img.path.as_posix())

    def build(self, dest: Path, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)

        self._load_config()
        data = self._load_xslx()
        tex = self._prepare_tex(data, **kwargs)
        self._resample_images(tex, **kwargs)

        print(tex)
