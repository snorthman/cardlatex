import shutil
import traceback
import os
from itertools import combinations, chain
from pathlib import Path
from typing import Callable, Tuple

import pytest
from click import BaseCommand
from click.testing import CliRunner

from cardlatex.__main__ import build
from cardlatex.tex import Tex


args_build = [['all'], ['mirror'], ['combine'], ['print'], ['quality', '25']]


@pytest.fixture(params=chain(*[combinations(args_build, n) for n in range(len(args_build) + 1)]))
def kwargs_build(request):
    return {args[0]: args[1] if len(args) == 2 else None for args in request.param}


@pytest.fixture(params=[
    ('default', 'default', None),
    ('back', 'default', None),
    (['back', 'combine'], 'default', None),
    ('default', 'invalid_sheet', ValueError)
])
def output(request):
    tex_files, xlsx_file, expected_error = request.param
    if isinstance(tex_files, str):
        tex_files = [tex_files]

    root = Path('./tests/')
    root_input = root / 'input'
    root_output = root / 'output'

    if root_output.exists():
        shutil.rmtree(root_output)
    root_output.mkdir()

    shutil.copytree(root_input / 'art', root_output / 'art', copy_function=shutil.copy)
    shutil.copy(root_input / 'copyme.tex', root_output / 'copyme.tex')
    shutil.copy(root_input / 'copymenot.tex', root_output / 'copymenot.tex')

    tex_paths = []
    for i, tex_file in enumerate(tex_files):
        if xlsx_file:
            shutil.copy(root_input / f'{xlsx_file}.xlsx', root_output / f'test_{i}.xlsx')
        shutil.copy(root_input / f'{tex_file}.tex', tex := root_output / f'test_{i}.tex')
        tex_paths.append(tex.as_posix())
        cache_dir = Tex.get_cache_dir(tex)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

    return tex_paths, xlsx_file, expected_error


def run(func: Callable | BaseCommand, expected_exception: Exception | None, *args, **kwargs):
    arguments = list(args)
    for key, value in kwargs.items():
        arguments.append(f'--{key}')
        if value:
            arguments.append(value)

    runner = CliRunner()
    result = runner.invoke(func, arguments)
    if result.exit_code != 0:
        exception = result.exc_info[0]
        if exception != expected_exception:
            raise exception(''.join([' '.join(arguments)] + ['\n'] + traceback.format_exception(result.exception)))


def test_build(output: Tuple[list[str], str, Exception], kwargs_build: dict):
    tex_files, _, expected_exception = output
    run(build, expected_exception,*tex_files, **kwargs_build)


def test_cache(output: Tuple[list[str], str, Exception]):
    tex_files, _, expected_exception = output
    if expected_exception:
        pytest.skip()

    run(build, expected_exception,*tex_files)

    stats = {}
    for cache in [Tex.get_cache_dir(tex_file) / 'art' for tex_file in tex_files]:
        for directory, _, filenames in os.walk(cache):
            for fn in filenames:
                file = Path(directory) / fn
                if file.suffix:
                    stats[file] = file.stat().st_mtime_ns

    run(build, expected_exception, *tex_files)

    for cache in [Tex.get_cache_dir(tex_file) / 'art' for tex_file in tex_files]:
        for directory, _, filenames in os.walk(cache):
            for fn in filenames:
                file = Path(directory) / fn
                if file.suffix:
                    assert file.stat().st_mtime_ns == stats[file]


def test_build_specific(output: Tuple[list[str], str, Exception], kwargs_build: dict):
    tex_files, xlsx_file, expected_exception = output
    if len(tex_files) > 1 and xlsx_file == 'default' and kwargs_build == {'combine': None, 'print': None}:
        run(build, expected_exception, *tex_files, **kwargs_build)
    else:
        pytest.skip()
