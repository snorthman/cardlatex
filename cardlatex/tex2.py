import logging
import os
import re
import subprocess
import signal
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime

import pexpect
import pexpect.popen_spawn
from wand.image import Image as WandImage

# from .cache import Cache

graphicpaths = r"""
\typeout{cardlatex@graphicpaths}
\makeatletter\typein{\Ginput@path}\makeatother
"""


def as_length(value: str) -> str:
    value = str(value).strip()
    assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
        ValueError(f'invalid measurement value "{value}"'))
    return value


def expand(text: str) -> list[tuple[str, str, str | None]]:
    results = []
    matches: list[re.Match] = list(re.finditer(r'^([^\\\n]*?)\\([a-z]+)(\[\w+])?\{', text, re.M))
    for m, match in enumerate(matches):
        opt = match.group(3)[1:-1] if match.group(3) else ''
        if '%' in match.group(1) or '%' in opt:
            continue

        # find the end of this expansion
        b = 1
        rb: re.Match | None = None
        for rb in re.finditer(r'(?<!\\)[{}]', text[match.end():]):
            b = b + (1 if rb.group() == '{' else -1)
            if b == 0:
                break
        assert b == 0 and rb, (
            ValueError(f'no closing bracket found for "{match.group(2)}"'))
        results.append((match.group(2), text[match.end():match.end() + rb.end() - 1], opt if opt else None))
    return results


# def expand_unique(text: str, default: str = None) -> tuple[str, str | None] | None:
#     results = expand(text)
#     if default is None:
#         assert len(results) > 0, rf'Missing \{cmd} command'
#     assert len(results) == 1, rf'Duplicate \{cmd} commands detected, only one \{cmd} should be present'
#     return results[0] if results else (default, None)


class Tex:
    def __init__(self, file: Path):
        tempdir = Path(tempfile.gettempdir()) / 'cardlatex'
        cachedir = hashlib.sha1(file.resolve().as_posix().encode('utf-8')).hexdigest()

        self.cache_dir = tempdir / cachedir
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        self.cardlatex_tex_path = file.with_suffix('.cardlatex.tex')
        self.cardlatex_log_path = file.with_suffix('.cardlatex.tex.log')

        with open(file) as f:
            self._tex = f.read()
        self._attr = {}

    def __str__(self):
        return f'{self.cardlatex_tex_path.as_posix()} | {self.cache_dir.as_posix()}'

    def __getitem__(self, item):
        return self._attr[item]

    def __setitem__(self, key, value):
        self._attr[key] = value

    @property
    def has_back(self) -> bool:
        return self['back'] is not None or 'back' not in self._attr

    @property
    def output_name(self) -> str:
        return self.cardlatex_tex_path.with_suffix('.pdf').name

    def parse(self):
        self._attr = {'back': None, 'dpi': '150', 'bleed': '0', 'cards': []}

        text = [text for cmd, text, _ in expand(self._tex) if cmd == 'cardlatex']
        assert len(text) > 0, rf'Missing \cardlatex command, consider cardlatex.exe --help'
        assert len(text) == 1, rf'Duplicate \cardlatex commands detected, only one \cardltex should be present per TeX file'

        cards = []
        for cmd, inner, opt in expand(text[0]):
            if cmd in ['width', 'height', 'bleed']:
                self[cmd] = as_length(inner)
            if cmd in ['dpi', 'front', 'back']:
                self[cmd] = inner
            if cmd == 'card':
                try:
                    copies = int(opt) if opt else 1
                except ValueError:
                    raise ValueError(f'could not parse number of copies: "{opt}"')
                cards.append((inner, copies))

        for cmd in ['width', 'height', 'front']:
            assert cmd in self._attr, f'"{cmd}" definition is required but missing.'

        variables = {m.group(1) for m in re.finditer(r'<\$(\w+)\$>', self['front'] + (self['back'] if self.has_back else ''))}
        for content, copies in cards:
            v = {_: '' for _ in variables}
            for cmd, inner, _ in expand(content):
                if cmd in v:
                    v[cmd] = inner
            self['cards'].extend([v] * copies)
            