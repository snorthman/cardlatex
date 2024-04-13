import hashlib
import logging
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pexpect
import pexpect.popen_spawn
from wand.image import Image as WandImage

from . import tempdir
from .config import Config
from .template import template as template_tex


def sha256(encode: str) -> str:
    obj = hashlib.sha1()
    obj.update(encode.encode('utf-8'))
    return obj.hexdigest()


def prepare_template(template: str, config: Config, draft: bool):
    """
    Apply config options to the static resources/template.tex
    """
    for r in re.finditer(r'<\$(\w+)\$>', template):
        value = getattr(config, r.group(1))
        template = template.replace(r.group(), value)
    if not draft and (m := re.search(r'\\node.+arabic\{cardlatex}', template)):
        template = template[:m.start()] + '%' + template[m.start():]
    return template


def prepare_inputs(tex: str, tex_dir: Path):
    r"""
    Insert recursively any \input{} directives into the document
    """
    while matches := list(re.finditer(r'^(.*)(\\input\{([\w.]+)})', tex, re.M)):
        for r in matches:
            input_tex = r.group(2)
            input_path = (tex_dir / r.group(3)).with_suffix('.tex')
            if '%' in r.group(1) or not input_path.exists():
                tex = tex.replace(input_tex, '')
            else:
                with open(input_path, 'r') as f:
                    tex = tex.replace(input_tex, f.read())
    return tex


class Tex:
    def __init__(self, tex: Path | str):
        self._path = Path(tex)
        self._cache_dir = self.get_cache_dir(self._path)
        self._template = self.template()

        with open(self._path, 'r') as f:
            self._tex = f.read()

        self._config = Config(self._tex)
        self._variables = sorted(
            list(({r.group(1) for r in re.finditer(r'<\$(\w+)\$>', self._config.front + self._config.back)})))
        self._completed = False

    @staticmethod
    def template() -> str:
        return template_tex

    @staticmethod
    def get_cache_dir(tex: Path | str):
        # change this to the resolved filepath, so we can check for each filepath whether any should be removed (after all important actions are performed)
        return tempdir / sha256(Path(tex).resolve().as_posix())

    @property
    def has_back(self) -> bool:
        return 'back' in self._config

    @property
    def build_pdf_path(self) -> Path:
        return self.path('.pdf', cache=True)

    @property
    def completed(self) -> bool:
        return self._completed

    def path(self, suffix: str = None, cache: bool = False):
        if suffix is not None:
            return (self._cache_dir / self._path.name).with_suffix(suffix) if cache else self._path.with_suffix(suffix)
        else:
            return self._cache_dir if cache else self._path.parent

    def _load_or_generate_xlsx(self):
        if self._variables:
            path_xlsx = self._path.with_suffix('.xlsx')
            if path_xlsx.exists():
                try:
                    data_existing = pd.read_excel(path_xlsx, sheet_name='cardlatex', dtype=str, na_filter=False)
                except ValueError as e:
                    raise ValueError(f'{e}, ensure your .xlsx file contains a worksheet named \'cardlatex\'')

                data_columns = pd.Index(
                    [*data_existing.columns] + [c for c in self._variables if c not in data_existing])
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
        """
        Prepare contents of the cardlatex.tex document
        """
        build_all = kwargs.get('build_all', False)

        template = prepare_template(self._template, self._config, kwargs.get('draft', False))
        tex = prepare_inputs(self._tex, self._path.parent)

        # \begin{tikzcard}[dpi]{width}{height}{
        environment = r'\begin{tikzcard}[' + self._config.dpi + ']{' + self._config.width + '}{' + self._config.height + '}'
        texts = [self._config.front] + ([self._config.back] if self.has_back else [])

        if len(data) == 0:
            data = pd.DataFrame(index=[None], columns=[None])

        content = []
        toggles = set()
        for row in range(len(data)) if build_all or self._config.include is None else self._config.include:
            try:
                copies = int(data['copies'][row])
            except (KeyError, ValueError):
                copies = 1

            row_content = []
            for i, text in enumerate(texts):
                text_toggles = ['']
                for key in self._variables:
                    item = data[key][row]
                    value = '' if pd.isna(item) else item

                    if re.search(r'\\if<\$' + key + r'\$>', text):
                        # add any unique <$variables$> to 'toggles', in case we use \if<$variable$>
                        toggles.add(key)
                        text_toggles.append((r'\toggletrue{' if bool(value) else r'\togglefalse{') + key + '}')

                    text_lines = text.split('\n')
                    text = []
                    line_replace = lambda t: t.replace(f'\\if<${key}$>', r'\ifvar{' + key + '}').replace(f'<${key}$>',
                                                                                                         str(value))
                    for line in text_lines:
                        if m := re.search(r'(?:^|[^\\])(%).*', line):
                            l, _ = m.span(1)
                            text.append(line_replace(line[:l]) + line[l:])
                        else:
                            text.append(line_replace(line))
                    text = '\n'.join(text)

                prefix = f'\n% ROW {row} ' + ('FRONT' if i == 0 else 'BACK') + '\n'
                row_content.append('\n'.join(text_toggles) + prefix + environment + text + '\\end{tikzcard}%\n')
            content.append('\\stepcounter{cardlatex}')
            for _ in range(copies):
                content.extend(row_content)

        content = '\n'.join(content)
        toggles = '\n'.join([r'\newtoggle{' + value + '}' for value in toggles])

        graphicpaths = r"""
\typeout{cardlatex@graphicpaths}
\makeatletter\typein{\Ginput@path}\makeatother
        """

        tex_blocks = [
            (None, template),
            ('user tex input', tex),
            ('newtoggles', toggles),
            ('graphicspaths', graphicpaths),
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

    def _xelatex(self, cardtex_path: Path, tex: str):
        draft = cardtex_path.is_relative_to(self._cache_dir)

        with open(cardtex_path, 'w') as t:
            t.write(tex)
        _tex_ = ('\n' + tex).split('\n')

        with open(self.path('.tex')) as t:
            cardtex = t.read()
        _cardtex_ = ('\n' + cardtex).split('\n')

        ln_ww = max([len(str(len(x))) for x in [_cardtex_, _tex_]])
        ln_w = lambda l: str(l).ljust(ln_ww, ' ')

        cardtex_fb = {}
        for m in re.finditer(r'^[^%\n]*\\cardlatex\[(front|back)]\{', cardtex, re.MULTILINE):
            cardtex_fb[m.group(1)] = len(cardtex[:m.end()].split('\n'))

        cardtex_rows: list[tuple[int, str | None, str | None]] = [(0, 'preamble', None)]
        for m in re.finditer(r'% ROW (\d+) (FRONT|BACK)\n', tex):
            cardtex_rows.append((len(tex[:m.end()].split('\n')), f'row {m.group(1)}', m.group(2).lower()))
        cardtex_rows.append((len(_tex_) + 1, None, None))

        if (pdf_path := cardtex_path.with_suffix('.pdf')).exists():
            os.remove(pdf_path)
        cmd = f'xelatex.exe -interaction=errorstopmode -file-line-error "{cardtex_path.stem}".tex 2&>1'
        print(f'running XeLaTeX on {self.path(".tex")} ({cmd})')

        try:
            directories = None
            errors = 0
            expects = [r'cardlatex@graphicpaths\r\n(.*?)\r',
                       r'includegraphics@(.+?)\r',
                       cardtex_path.name.replace('.', r'\.') + r':(\d+):(.*)l\.\1',
                       pexpect.EOF]
            if os.name == 'nt':
                process = pexpect.popen_spawn.PopenSpawn(cmd, cwd=cardtex_path.parent.as_posix())
            else:
                process = pexpect.spawn(cmd, cwd=cardtex_path.parent.as_posix(), echo=False)

            while True:
                p = process.expect(expects)
                if p == 0:  # r'cardlatex@graphicpaths\r\n(.*?)\r'
                    directories = [m.group(1) for m in re.finditer(r'\{(.+?)}', process.match.group().decode())]
                if p == 1:  # r'includegraphics@(.+?)\r'
                    assert directories is not None

                    fn: str = process.match.group(1).decode()
                    files = [self.path() / path / fn for path in directories]
                    exists = [path.exists() for path in files]
                    if any(exists):
                        if draft:
                            file = files[file_index := exists.index(True)]
                            file_draft = [self.path(cache=True) / path / fn for path in directories][file_index]

                            if not file_draft.exists():
                                self._resample(file, file_draft)
                            else:
                                if file.lstat().st_mtime_ns != file_draft.lstat().st_mtime_ns:
                                    self._resample(file, file_draft)
                if p == 2:  # tex_path.name + r':(\d+):(.*)l\.\1'
                    ln, err = int(process.match.group(1)), process.match.group(2).decode().strip('\r\n ')
                    ln_row, loc, fb = cardtex_rows[[ln >= r for r, _, _ in cardtex_rows].index(False) - 1]
                    if fb is None:
                        print('\n\t'.join([f'Error in preamble',
                                           f'\n\tln. {ln} of compiled',
                                           *[ln_w(l) + ' >> ' + _tex_[l] for l in range(ln - 2, ln + 3)],
                                           '\n\tTeX error message was',
                                           *[ln_w('') + ' >> ' + t for t in err.split('\n')]]) + '\n')
                    else:
                        ln_cardtex = cardtex_fb[fb] + ln - ln_row
                        print('\n\t'.join([f'Error in {loc} [{fb}]',
                                           f'\n\tln. {ln_cardtex} of template',
                                           *[ln_w(l) + ' >> ' + _cardtex_[l] for l in
                                             range(ln_cardtex - 2, ln_cardtex + 3)],
                                           f'\n\tln. {ln} of compiled',
                                           *[ln_w(l) + ' >> ' + _tex_[l] for l in range(ln - 2, ln + 3)],
                                           f'\n\tTeX error message was',
                                           *[ln_w('') + ' >> ' + t for t in err.split('\n')]]) + '\n')
                    errors += 1
                if p == 3:  # EOF
                    with open(log_path := cardtex_path.with_suffix('.log')) as f:
                        log = f.read()

                    names = ['.cardlatex.log', '.cardlatex.tex']
                    if errors == 0:
                        for name in names:
                            if (path := self.path(name)).exists():
                                os.remove(path)

                        shutil.move(cardtex_path.with_suffix('.pdf'), self.path('.pdf', cache=True))
                        m = re.search(r'Output written on (.+)pdf \((\d+)', log)
                        print(self.path('.tex').name + f' completed! ({m.group(2)} pages)')
                    else:
                        for path, name in zip([log_path, cardtex_path], names):
                            shutil.copy(path, self.path(name))

                        print(self.path('.tex').name + f' failed! ({errors} error{"s" if errors > 1 else ""})')
                    return 0 if errors == 0 else 1

                process.sendline('')
        except pexpect.TIMEOUT as e:
            raise e
        except Exception as e:
            raise e

    def build(self, **kwargs) -> 'Tex':
        if not self.completed:
            self._cache_dir.mkdir(exist_ok=True, parents=True)
            data = self._load_or_generate_xlsx()
            logging.info(f'{self._path}: xlsx loaded:\n\n{data.to_string()}\n')
            tex = self._prepare_tex(data, **kwargs)
            logging.info(f'{self._path}: tex content:\n\n{tex}\n')
            exitcode = self._xelatex(self.path('.cardlatex.tex', cache=kwargs.get('draft')), tex)
            self._completed = exitcode == 0
            logging.info(f'{self._path}: xelatex exitcode {exitcode}\n')

        cache = self.path('', cache=True)
        cache = cache.with_stem('.' + cache.stem).with_suffix('.cardlatex')
        with open(cache, 'w') as f:
            f.write(self._path.resolve().as_posix())
        return self

    def release(self):
        if self.completed:
            shutil.move(self.path('.pdf', cache=True), self.path('.pdf'))
            logging.info(f'{self._path}: released')
        else:
            raise RuntimeError(f'Error: {self.build_pdf_path} has failed to build!')

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