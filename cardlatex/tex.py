import logging
import os
import re
import shutil
from pathlib import Path

import pexpect
import pexpect.popen_spawn
from wand.image import Image as WandImage

from .cache import Cache
from .template import template_tex

graphicpaths = r"""
\typeout{cardlatex@graphicpaths}
\makeatletter\typein{\Ginput@path}\makeatother
"""


class Tex:
    class Keywords:
        def __init__(self, **kwargs):
            self._m: bool = kwargs['@multiline']
            self._skip: str | None = kwargs.get('@skip-character', None)
            self._keywords = {kw['@key']: kw['@value'] for kw in kwargs['keyword']}

        def _apply(self, string: str):
            replace: dict[tuple[int, int], str] = {}
            reserved: set[int] = set()
            for key, word in self._keywords.items():
                for m in re.finditer(key, string):
                    if string == '':
                        return word

                    w = word
                    while mm := re.search(r'#(\d)', w):
                        l, r = mm.span()
                        w = w[:l] + m.group(int(mm.group(1))) + w[r:]

                    reservation = set(range(*m.span()))
                    if not reserved.intersection(reservation):
                        replace[(min(reservation), max(reservation))] = w
                        reserved.update(reservation)

            # guaranteed no overlap in replace keys now
            c, result = 0, ''
            for l, r in sorted(replace, key=lambda a: a[0]):
                result += string[c:l] + replace[(l, r)]
                c = r + 1

            return result + string[c:]

        def apply(self, string: str):
            string = [string] if self._m else string.split('\n')
            for s in range(len(string)):
                if self._skip is not None and string[s].startswith(self._skip):
                    continue
                else:
                    string[s] = self._apply(string[s])
            return '\n'.join(string)

    def __init__(self, cache: Cache, file: Path):
        assert cache.working_directory() == file.parent, f'{file} should be in the same directory as the .xml file'
        self._working_file = file.resolve()
        self._cache_file = (cache.cache_directory() / file.name).with_suffix('.cardlatex.tex')

        with open(file, 'r') as f:
            self._tex = f.read()
        self._attr = {}

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

        test = []
        for t in attributes.get('@test', '').split(','):
            if m := re.search(r'(\d+)(?:-(\d+)|\.{2,}(\d+))', t):
                l, r = m.group(1), m.group(2) if m.group(2) else m.group(3)
            else:
                l, r = t, t
            test.extend(range(int(l), int(r) + 1))

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
            'test': test,
            'props': props,
            'variables': {m.group(1) for m in re.finditer(r'<\$(\w+)\$>', props['front'] + (props['back'] if props['back'] else ''))}
        }

    def __getitem__(self, item):
        return self._attr[item]

    def write(self, keywords: list, is_draft: bool, is_print: bool):
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

        variables: dict[str, str | None] = {v: None for v in self['variables']}

        keywords = [self.Keywords(**kwargs) for kwargs in keywords]
        for c, card in enumerate(self['cards'], start=1):
            if not is_print and len(self['test']) > 0 and c not in self['test']:
                continue

            for v in self['variables']:
                if v in card:
                    variables[v] = card[v]['$']
                    # manage keywords here, default=False though


            tex['@cards'] += '\n'.join([r'\toggle' + ('false' if t is None else 'true') + '{' + v + '}' for v, t in variables.items()])

            for i in range(card['@copies'] if not is_draft else 1):
                for prop in ('front', 'back'):
                    text = self['props'][prop]
                    if not text:
                        continue

                    for var in self['variables']:
                        text = text.replace(fr'\if<${var}$>', r'\ifvar{' + var + '}')
                        if variables[var] is None:
                            value = ''
                        else:
                            value = variables[var].replace('\t', ' ').strip('\n\t ')
                            for kw in keywords:
                                value = kw.apply(value)
                            # apply keywords to value here

                        text = text.replace(f'<${var}$>', value)

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
        with open(self._cache_file) as cf, open(self._working_file) as wf:
            cache_tex = cf.read()
            cache_tex_ln = ('\n' + cache_tex).split('\n')
            working_tex = wf.read()
            working_tex_ln = ('\n' + working_tex).split('\n')

        ln_ww = max([len(str(len(x))) for x in [working_tex_ln, cache_tex_ln]])
        ln_w = lambda _: str(_).ljust(ln_ww, ' ')

        working_tex_content_start = {}
        for m in re.finditer(r'^[^%\n]*\\cardlatex\[(front|back)]\{', working_tex, re.MULTILINE):
            working_tex_content_start[m.group(1)] = len(working_tex[:m.end()].split('\n'))

        cache_tex_content_start: list[tuple[int, str | None, str | None]] = [(0, 'preamble', None)]
        for m in re.finditer(r'% CARD (\d+), COPY \d+, (FRONT|BACK)\n', cache_tex):
            cache_tex_content_start.append((len(cache_tex[:m.end()].split('\n')), f'row {m.group(1)}', m.group(2).lower()))
        cache_tex_content_start.append((len(cache_tex_ln) + 1, None, None))

        if (pdf_path := self._cache_file.with_suffix('.pdf')).exists():
            os.remove(pdf_path)
        cmd = f'xelatex.exe -interaction=errorstopmode -file-line-error "{self._cache_file.stem}".tex 2&>1'

        try:
            if os.name == 'nt':
                process = pexpect.popen_spawn.PopenSpawn(cmd, cwd=cache_dir.as_posix())
            else:
                process = pexpect.spawn(cmd, cwd=cache_dir.as_posix(), echo=False)

            directories = None
            errors = 0
            expects = [r'cardlatex@graphicpaths\r\n(.*?)\r',
                       r'includegraphics@(.+?)\r',
                       self._working_file.name.replace('.', r'\.') + r':(\d+):(.*)l\.\1',
                       pexpect.EOF]
            while True:
                p = process.expect(expects)
                if p == 0:  # r'cardlatex@graphicpaths\r\n(.*?)\r'
                    directories = sorted(['.'] + [m.group(1) for m in re.finditer(r'\{(.+?)}', process.match.group().decode())])
                elif p == 1:  # r'includegraphics@(.+?)\r'
                    assert directories is not None
                    fn: str = process.match.group(1).decode()
                    files = []
                    for d in directories + [None]:
                        if d is None:
                            # immediately exit process, missing image errors take long to process
                            process.kill(15)
                            raise FileNotFoundError(f'Could not find image "{fn}", searched in:\n>\t' + '\n>\t'.join(files))

                        if (file := working_dir / d / fn).exists():
                            if is_draft:
                                if not (file_resampled := cache_dir / d / fn).exists():
                                    self._resample(file, file_resampled)
                                elif file.lstat().st_mtime_ns != file_resampled.lstat().st_mtime_ns:
                                    self._resample(file, file_resampled)
                            break
                        files.append(file.as_posix())
                elif p == 2:  # tex_path.name + r':(\d+):(.*)l\.\1'
                    ln = int(process.match.group(1))
                    error = process.match.group(2).decode().strip('\n ').replace('\r', '')
                    ln_row, loc, frontback = cache_tex_content_start[[ln >= r for r, _, _ in cache_tex_content_start].index(False) - 1]
                    if frontback is None:
                        logging.error('\n\t'.join([f'Error in preamble',
                                           f'\n\tln. {ln} of compiled',
                                           *[ln_w(l) + ' >> ' + cache_tex_ln[l] for l in range(ln - 2, ln + 3)],
                                           '\n\tTeX error message was',
                                           *[ln_w('') + ' >> ' + t for t in error.split('\n')]]) + '\n')
                    else:
                        ln_cardtex = working_tex_content_start[frontback] + ln - ln_row
                        logging.error('\n\t'.join([f'Error in {loc} [{frontback}]',
                                           f'\n\tln. {ln_cardtex} of template',
                                           *[ln_w(l) + ' >> ' + working_tex_ln[l] for l in
                                             range(ln_cardtex - 2, ln_cardtex + 3)],
                                           f'\n\tln. {ln} of compiled',
                                           *[ln_w(l) + ' >> ' + cache_tex_ln[l] for l in range(ln - 2, ln + 3)],
                                           f'\n\tTeX error message was',
                                           *[ln_w('') + ' >> ' + t for t in error.split('\n')]]) + '\n')
                    errors += 1
                elif p == 3:  # EOF
                    with open(log_path := self._cache_file.with_suffix('.log')) as f:
                        log = f.read()

                    names = ['.cardlatex.log', '.cardlatex.tex']
                    if errors == 0:
                        # remove existing .cardlatex. files caused by errors from a prior run
                        [os.remove(self._working_file.with_suffix(name)) for name in names if self._working_file.with_suffix(name).exists()]

                        shutil.move(self._cache_file.with_suffix('.pdf'), self._working_file.with_suffix('.pdf'))
                        m = re.search(r'Output written on (.+)pdf \((\d+)', log)
                        logging.info(self._working_file.name + f' completed! ({m.group(2)} pages)')
                    else:
                        for path, name in zip([log_path, self._cache_file], names):
                            shutil.copy(path, self._working_file.with_suffix(name))
                        logging.info(self._working_file.name + f' failed! ({errors} error{"s" if errors > 1 else ""})')
                    return 0 if errors == 0 else 1

                process.sendline('')
        except pexpect.TIMEOUT as e:
            raise e
        except Exception as e:
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
