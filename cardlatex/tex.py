import logging
import os
import re
import subprocess
import signal
from pathlib import Path

import pexpect
import pexpect.popen_spawn
from wand.image import Image as WandImage

from .cache import Cache
from .keywords import Keywords
from .template import template_tex

graphicpaths = r"""
\typeout{cardlatex@graphicpaths}
\makeatletter\typein{\Ginput@path}\makeatother
"""


class Tex:
    def __init__(self, cache: Cache, file: Path):
        assert cache.working_directory == file.parent, f'{file} should be in the same directory as the .xml file'
        self._xml_file = cache.file_xml
        self._working_file = file.resolve()
        self._cache_file = (cache.cache_directory / file.name).with_suffix('.cardlatex.tex')

        with open(file, 'r') as f:
            self._tex = f.read()
        self._attr = {}
        self._resampled = set()

    def __str__(self):
        return f'{self._working_file.as_posix()} | {self._cache_file.as_posix()}'

    @property
    def name(self) -> Path:
        return Path(self._working_file.name)

    @property
    def resampled(self) -> frozenset[Path]:
        return frozenset(self._resampled)

    @property
    def has_back(self) -> bool:
        return self._attr['props']['back'] is not None

    @property
    def output_name(self) -> str:
        return self._working_file.with_suffix('.cardlatex.pdf').name

    def set_attributes(self, attributes: dict):
        props = {'front': None, 'back': None}
        prop_name = lambda a: r'\cardlatex configuration object' + (f'" {a}"' if a else '')
        matches: list[re.Match] = list(re.finditer(r'^(.*)\\cardlatex\[(\w+)]\{', self._tex, re.M))
        for m, match in enumerate(matches):
            if '%' in match.group(1):
                continue

            prop = match.group(2)
            assert prop in props.keys(), (
                KeyError(rf'unknown {prop_name(prop)}'))
            assert props[prop] is None, (
                KeyError(rf'duplicate {prop_name(prop)}'))

            b = 1
            rb: re.Match | None = None
            for rb in re.finditer(r'(?<!\\)[{}]', self._tex[match.end():]):
                b = b + (1 if rb.group() == '{' else -1)
                if b == 0:
                    break
            assert b == 0 and rb, (
                ValueError(rf'no closing bracket found for {prop_name(prop)}'))

            endpos = match.end() + rb.end() - 1
            if m < len(matches) - 1:
                assert endpos < matches[m + 1].start(), (
                    ValueError(rf'{prop_name("")} found inside {prop_name(prop)}'))

            props[prop] = self._tex[match.end():endpos]

        if props['front'] is None:
            raise ValueError(prop_name('front') + ' missing')

        test = attributes.get('@test', '')
        test_pages = []
        if test:
            for t in attributes.get('@test', '').split(','):
                if m := re.search(r'(\d+)(?:-(\d+)|\.{2,}(\d+))', t):
                    l, r = m.group(1), m.group(2) if m.group(2) else m.group(3)
                else:
                    l, r = t, t
                test_pages.extend(range(int(l), int(r) + 1))

        def as_length(value: str):
            value = str(value).strip()
            assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
                ValueError(f'invalid measurement value "{value}"'))
            return value

        self._attr = {
            'width': as_length(attributes['@width']),
            'height': as_length(attributes['@height']),
            'bleed': as_length(attributes['@bleed']),
            'spacing': as_length(attributes['@spacing']),
            'dpi': attributes['@dpi'],
            'cards': attributes.get('card', []),
            'test': test_pages,
            'props': props,
            'variables': {m.group(1) for m in re.finditer(r'<\$(\w+)\$>', props['front'] + (props['back'] if props['back'] else ''))}
        }

    def __getitem__(self, item):
        return self._attr[item]

    def write(self, keywords: list, is_draft: bool):
        tex = {}

        t, rr = '', 0
        for m in re.finditer(r'<\$(\w+)\$>', template_tex):
            l, r = m.span()
            key = m.group(1)

            if key == 'bleed':
                value = self['bleed']
            elif key == 'counter':  # and self._draft is true
                value = r'\node[anchor=north west,white,xshift=-\bleed,yshift=\bleed] at (TL) {\texttt{\arabic{cardlatex}}};'
            else:
                raise SystemError(f'template.tex has an unknown key {key}')

            t += template_tex[rr:l] + value
            rr = r
        t += template_tex[rr:]
        tex['@template'] = t

        t, rr = '', 0
        for m in re.finditer(r'^(.*)(\\input\{([\w.]+)})', self._tex):
            l, r = m.span(2)

            input_path = (self._working_file.parent / m.group(3)).with_suffix('.tex')
            if '%' in m.group(1) or not input_path.exists():
                value = ''
            else:
                with open(input_path, 'r') as f:
                    value = f.read()

            t += self._tex[rr:l] + value
            rr = r
        t += self._tex[rr:]
        tex['user tex input'] = t

        tex['graphicpaths'] = graphicpaths
        tex['toggles'] = '\n'.join([r'\newtoggle{' + value + '}' for value in self['variables']])
        tex['document'] = '\\begin{document}\n\n'
        tex['@cards'] = ''

        variables: dict[str, list[str | bool]] = {v: ['', False] for v in self['variables']}
        keywords = [Keywords(**kwargs) for kwargs in keywords]
        for c, card in enumerate(self['cards'], start=1):
            if is_draft and len(self['test']) > 0 and c not in self['test']:
                continue

            for v in self['variables']:
                if v in card:
                    if '$' in card[v]:
                        variables[v][0] = card[v]['$'].replace('\t', ' ').strip('\n ')
                    if '@keywords' in card[v]:
                        variables[v][1] = card[v]['@keywords']

            tex['@cards'] += '\n'.join([r'\toggle' + ('true' if s else 'false') + '{' + v + '}' for v, s in variables.items()])

            for i in range(card['@copies'] if not is_draft else 1):
                for prop in ('front', 'back'):
                    text = self['props'][prop]
                    if not text:
                        continue

                    for v in self['variables']:
                        value = variables[v][0]
                        if variables[v][1]:
                            for kw in keywords:
                                value = kw.apply(value)
                        text = text.replace(fr'\if<${v}$>', r'\ifvar{' + v + '}').replace(f'<${v}$>', value)

                    tex['@cards'] += '\n'.join([
                        f'\n\n% CARD {c}, COPY {i + 1}, {prop.upper()}',
                        r'\begin{tikzcard}[' + self['dpi'] + ']{' + self['width'] + '}{' + self['height'] + '}',
                        text,
                        '\\end{tikzcard}%'
                    ])

            tex['@cards'] += '\n\\stepcounter{cardlatex}\n\n'
        tex['@cards'] = '\n\t' + tex['@cards'].replace('\n', '\n\t')

        tex['@documentend'] = '\n\\end{document}'

        with open(self._cache_file, 'w') as f:
            for key, value in tex.items():
                if not key.startswith('@'):
                    f.write('\n\n' + '%' * 68 + '\n% ' + key.upper() + '\n\n')
                f.write(value)

    def xelatex(self, is_draft: bool):
        working_dir = self._working_file.parent
        cache_dir = self._cache_file.parent
        with open(self._cache_file) as cf:
            cache_tex = cf.read()
            cache_tex_ln = ('\n' + cache_tex).split('\n')

        cache_cards = []
        for m in re.finditer(r'% CARD (\d+), COPY \d+, (FRONT|BACK)\n', cache_tex):
            cache_cards.append({
                'card': m.group(1),
                'side': m.group(2),
                'ln': len(cache_tex[:m.end()].split('\n'))
            })

        cmd = f'xelatex.exe -interaction=errorstopmode -file-line-error "{self._cache_file.stem}".tex'

        if os.name == 'nt':  # Windows
            process = pexpect.popen_spawn.PopenSpawn(cmd, cwd=cache_dir.as_posix())
        else:
            process = pexpect.spawn(cmd, cwd=cache_dir.as_posix(), echo=False)

        try:
            directories = None
            expects = [r'cardlatex@graphicpaths\r\n(.*?)\r',
                       r'includegraphics@(.+?)\r',
                       self._cache_file.name.replace('.', r'\.') + r':(\d+): (.*)l\.\1',
                       pexpect.EOF]
            while True:
                p = process.expect(expects)
                p_send = ''
                if p == 0:
                    directories = sorted(['.'] + [m.group(1) for m in re.finditer(r'\{(.+?)}', process.match.group().decode())])
                elif p == 1:
                    assert directories is not None
                    fn: str = process.match.group(1).decode()
                    files = []
                    for d in directories + [None]:
                        if d is None:
                            # immediately exit process, missing image errors take long to process
                            raise FileNotFoundError(f'Could not find image "{fn}", searched in:\n-\t' + '\n-\t'.join(files))

                        if (file := working_dir / d / fn).exists():
                            if is_draft:
                                if not (file_resampled := cache_dir / d / fn).exists():
                                    self._resample(file, file_resampled)
                                elif file.lstat().st_mtime_ns != file_resampled.lstat().st_mtime_ns:
                                    self._resample(file, file_resampled)
                                self._resampled.add(file_resampled)
                            else:
                                p_send = working_dir.as_posix() + '/'
                            break
                        files.append(file.as_posix())
                elif p == 2:
                    xelatex_error = process.match.group(2).decode().replace('\r', '').strip('\n ')
                    cache_error_ln = int(process.match.group(1)) - 1  # somehow, the line number is always off by +1

                    cache_error_lns = [f'  >> {cache_tex_ln[_]}' for _ in range(cache_error_ln - 2, cache_error_ln) if _ >= 0]
                    cache_error_lns.append(f'  >> {cache_tex_ln[cache_error_ln]}')
                    cache_error_lns.extend(
                        [f'  >> {cache_tex_ln[_]}' for _ in range(cache_error_ln + 1, cache_error_ln + 3) if _ < len(cache_tex_ln)])

                    cache_card = -1
                    for c, card in enumerate(cache_cards):
                        if cache_error_ln >= card['ln']:
                            cache_card = c
                            if c == len(cache_cards) - 1 or cache_error_ln < cache_cards[c + 1]['ln']:
                                break

                    loc = 'Preamble'
                    if cache_card > -1:
                        card, side, _ = tuple(cache_cards[cache_card].values())
                        loc = f'Card {card}, {side}'
                    msg = '\n'.join([f'Error in {self.name}: {loc}',
                                     *cache_error_lns,
                                     'Error message was',
                                     *[f'  >> {_}' for _ in xelatex_error.split('\n')]])
                    raise RuntimeError(msg)
                elif p == 3:  # EOF
                    with open(self._cache_file.with_suffix('.log')) as f:
                        log = f.read()
                    m = re.search(r'Output written on (.+)pdf \((\d+)', log)
                    logging.info(self._working_file.name + f' completed! ({m.group(2)} pages)')
                    return

                process.sendline(p_send)
        except Exception as e:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/F'])
            else:
                os.kill(process.pid, signal.SIGTERM)
            process.kill(15)
            raise e

    @staticmethod
    def _resample(source: Path, target: Path):
        lstat = source.lstat()
        with WandImage(filename=source.resolve().as_posix()) as src:
            with src.convert(source.suffix[1:]) as tar:
                if lstat.st_size > 0 and lstat.st_size > 51200:  # in bytes
                    tar.transform(resize=f'{round(100 * 51200 / lstat.st_size)}%')
                target.parent.mkdir(parents=True, exist_ok=True)
                tar.save(filename=target.as_posix())
        os.utime(target, ns=(lstat.st_atime_ns, lstat.st_mtime_ns))
