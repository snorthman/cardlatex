import hashlib
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from . import tempdir
from .config import Config
from .image import Image, is_relative
from .template import template as template_tex


def sha256(encode: str) -> str:
    obj = hashlib.sha1()
    obj.update(encode.encode('utf-8'))
    return obj.hexdigest()


def prepare_template(template: str, config: Config):
    """
    Apply config options to the static resources/template.tex
    """
    for r in re.finditer(r'<\$(\w+)\$>', template):
        value = getattr(config, r.group(1))
        template = template.replace(r.group(), value)
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
        self._template = self.template()

        with open(self._path, 'r') as f:
            self._tex = f.read()

        self._config = Config(self._tex)
        self._variables = sorted(
            list(({r.group(1) for r in re.finditer(r'<\$(\w+)\$>', self._config.front + self._config.back)})))
        self._cache_dir = self.get_cache_dir(self._path)
        self._cache_output_pdf = (self.cache_dir / self._path.name).with_suffix('.pdf')
        self._completed = False

    @staticmethod
    def template() -> str:
        return template_tex
        # with resources.open_text(cardlatex.resources, 'template.tex') as f:
        #     return f.read()
        # template_path = pkg_resources.resource_filename('cardlatex.resources', 'template.tex')
        # with open(template_path) as f:
        #     return f.read()

    @staticmethod
    def get_cache_dir(tex: Path | str):
        return tempdir / sha256(Path(tex).resolve().as_posix())

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @property
    def has_back(self) -> bool:
        return 'back' in self._config

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

        template = prepare_template(self._template, self._config)
        tex = prepare_inputs(self._tex, self._path.parent)

        # \begin{tikzcard}[dpi]{width}{height}{
        tikz = '\n\\begin{tikzcard}[' + self._config.dpi + ']{' + self._config.width + '}{' + self._config.height + '}%\n\n'
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
                        # add any unique <$variables$> to 'toggles', in case we use \if<$variable$>
                        toggles.add(key)
                        edge_toggles.append((r'\toggletrue{' if bool(value) else r'\togglefalse{') + key + '}')

                    edge = edge.replace(f'\\if<${key}$>', r'\ifvar{' + key + '}')
                    edge = edge.replace(f'<${key}$>', str(value))

                # any toggles, \begin{tikzcard}...{content}\end{tikzcard}
                content.append('\n'.join(edge_toggles) + tikz + edge + '\n\\end{tikzcard}%\n')

        content = '\n'.join(content)
        toggles = '\n'.join([r'\newtoggle{' + value + '}' for value in toggles])

        graphicpaths = r"""
            \makeatletter
            \typeout{cardlatex@graphicpaths}
            \typeout{\Ginput@path}
            \makeatother
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

    @staticmethod
    def _xelatex(tex_file: Path, tex_log: Path, cache_log: Path):
        cmd = f'xelatex.exe -interaction=nonstopmode "{tex_file.stem}".tex'
        result = subprocess.run(cmd, cwd=tex_file.parent,
                                capture_output=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        def error():                     # stderr may have a specific and irrelevant error
            if result.returncode == 0 or (result.stderr and len(result.stderr) == 124):
                logging.info(result)
                return
            else:
                logging.error(result)
                shutil.copy(cache_log, tex_log)
                raise subprocess.SubprocessError(f'XeLaTeX compilation error(s), see {tex_log.resolve()}')

        return error

    def build(self, **kwargs) -> 'Tex':
        if self.completed:
            return self

        self.cache_dir.mkdir(exist_ok=True, parents=True)

        data = self._load_or_generate_xlsx()
        logging.info(f'{self._path}: xlsx loaded:\n\n{data.to_string()}\n')
        tex = self._prepare_tex(data, **kwargs)
        logging.info(f'{self._path}: tex content:\n\n{tex}\n')

        path_log = self._path.with_suffix('.log')
        cache_tex = self.cache_dir / self._path.name
        cache_log = cache_tex.with_suffix('.log')

        logging.info(f'{self._path}: resampled missing images')
        if kwargs.get('draft', False):
            with open(cache_tex, 'w') as f:
                f.write(tex)
            logging.info(f'{self._path}: wrote tex contents to {cache_tex}')

            # resample existing images
            for directory, _, filenames in os.walk(self._cache_dir):
                if (root := Path(directory)) != self._cache_dir:
                    for file in filenames:
                        img = Image(self._path.parent, self.cache_dir)
                        try:
                            img.find_source_from_cache(root / file)
                            img.resample()
                        except FileNotFoundError as e:
                            logging.error(f'{self._path}: {e}')
            logging.info(f'{self._path}: resampled existing images')

            xelatex_error_func = self._xelatex(cache_tex, path_log, cache_log)
            with open(cache_log, 'r') as f:
                log = f.read()
            logging.info(f'{self._path}: reading log contents at {cache_log}')

            # gather \graphicspath items from log
            graphicspaths = [self._path.parent]
            tex_graphicspaths = re.search(r'cardlatex@graphicpaths\n(.+?)\n', log).group(1)
            for path in tex_graphicspaths[1:-1].split('}{'):
                if is_relative(path):
                    graphicspaths.append(graphicspaths[0] / path)

            # gather missing images from log
            not_found = []
            for pattern in [r'! LaTeX Error: File `(.+)\' not found', r'LaTeX Warning: File `(.+)\' not found']:
                not_found.extend(r.group(1) for r in re.finditer(pattern, log))

            # resample missing images
            if not_found:
                for file in not_found:
                    img = Image(self._path.parent, self.cache_dir)
                    img.find_source_from_directories(file, *graphicspaths)
                    img.resample()
                logging.info(f'{self._path}: resampled missing images')

                xelatex_error_func = self._xelatex(cache_tex, path_log, cache_log)

            xelatex_error_func()
        else:
            with open(path_tex := self._path.with_suffix('.cardlatex.tex'), 'w') as f:
                f.write(tex)
            xelatex_error_func = self._xelatex(path_tex, path_log, cache_log)

            # delete, copy or move output to cache_dir to prepare for self.release()
            for suffix, action, args in [('.synctex.gz', os.remove, ()),
                                         ('.aux', os.remove, ()),
                                         ('.log', shutil.move, (cache_log,)),
                                         ('.pdf', shutil.move, (self._cache_output_pdf,)),
                                         ('.tex', shutil.copy, (cache_tex,))]:
                path = path_tex.with_suffix(suffix)
                if path.exists():
                    action(*(path, *args))
            logging.info(f'{self._path}: moved output files to cache at {self._cache_dir}')

            xelatex_error_func()

        self._completed = True
        return self

    def release(self):
        if self.completed:
            output = self.cache_dir / self._path.name
            log, pdf = output.with_suffix('.log'), output.with_suffix('.pdf')

            shutil.copy(output.with_suffix('.tex'), path_tex := self._path.with_suffix('.cardlatex.tex'))
            logging.info(f'{self._path}: copied tex to {path_tex}')
            if log.exists():
                shutil.copy(output.with_suffix('.log'), path_log := self._path.with_suffix('.log'))
                logging.info(f'{self._path}: copied tex to {path_log}')
            if pdf.exists():
                shutil.move(output.with_suffix('.pdf'), path_pdf := self._path.with_suffix('.pdf'))
                logging.info(f'{self._path}: copied tex to {path_pdf}')

            logging.info(f'{self._path}: released')
