import os
import shutil
import traceback
from itertools import combinations, chain
from pathlib import Path
from typing import Callable

import pytest
from click import BaseCommand
from click.testing import CliRunner
from pikepdf import Pdf

from cardlatex.__main__ import build
from cardlatex.tex import Tex

args_build_params = [['all'], ['combine'], ['print'], ['draft']]


@pytest.fixture(params=chain(*[combinations(args_build_params, n) for n in range(len(args_build_params) + 1)]))
def kwargs_build(request):
    return {args[0]: args[1] if len(args) == 2 else None for args in request.param}


@pytest.fixture(params=[
    (['default'], 'default'),
    (['back'], 'default'),
    (['back', 'combine'], 'default')
])
def args_build(request) -> tuple[list[str], str]:
    return request.param


@pytest.fixture(params=[
    (['missing'], 'default', ValueError),
    (['default'], 'invalid', ValueError)
])
def args_build_fail(request) -> tuple[list[str], str, Exception]:
    return request.param


def prepare(xlsx_name: str, *tex_files) -> list[str]:
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
        if xlsx_name:
            shutil.copy(root_input / f'{xlsx_name}.xlsx', root_output / f'test_{i}.xlsx')
        shutil.copy(root_input / f'{tex_file}.tex', tex := root_output / f'test_{i}.tex')
        tex_paths.append(tex.as_posix())
        cache_dir = Tex.get_cache_dir(tex)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

    return tex_paths


def run(func: Callable | BaseCommand, expected_exception: Exception | None, *args, **kwargs):
    arguments = list(args)
    for key, value in kwargs.items():
        arguments.append(f'--{key}')
        if value:
            arguments.append(value)

    if len(args) < 2 and 'combine' in kwargs:
        pytest.skip()

    runner = CliRunner()
    result = runner.invoke(func, arguments + ['--debug'])
    if result.exit_code != 0:
        exception = result.exc_info[0]
        if exception != expected_exception:
            raise result.exception
    else:
        assert expected_exception is None


def test_build(args_build: tuple[str, str], kwargs_build: dict):
    tex_files, xlsx_name = args_build
    run(build, None, *prepare(xlsx_name, *tex_files), **kwargs_build)
    output_dir = Path('./tests/output')
    outputs = [output_dir / 'test_0.pdf']

    expected = -1
    if len(tex_files) == 1:
        if 'default' in tex_files:
            expected = 3
            if 'all' in kwargs_build:
                expected = 4
            if 'print' in kwargs_build:
                expected = 1
        elif 'back' in tex_files:
            expected = 8
            if 'print' in kwargs_build:
                expected = 2
    elif len(tex_files):
        outputs.append(output_dir / 'test_1.pdf')
        expected = 12
        if 'combine' in kwargs_build:
            outputs.pop()
        if 'print' in kwargs_build:
            expected = 4 if 'mirror' in kwargs_build else 3

    actual = 0
    for output in outputs:
        with Pdf.open(output) as pdf:
            actual += len(pdf.pages)
    assert actual == expected


def test_build_expected_exception(args_build_fail: tuple[str, str, Exception]):
    tex_files, xlsx_name, expected_exception = args_build_fail
    run(build, expected_exception, *prepare(xlsx_name, *tex_files))


def test_cache(args_build: tuple[str, str]):
    tex_files, xlsx_name = args_build

    run(build, None, *(tex_files_prepared := prepare(xlsx_name, *tex_files)))

    stats = {}
    for cache in [Tex.get_cache_dir(tex_file) / 'art' for tex_file in tex_files_prepared]:
        for directory, _, filenames in os.walk(cache):
            for fn in filenames:
                file = Path(directory) / fn
                if file.suffix:
                    stats[file] = file.stat().st_mtime_ns

    run(build, None, *tex_files_prepared)

    for cache in [Tex.get_cache_dir(tex_file) / 'art' for tex_file in tex_files_prepared]:
        for directory, _, filenames in os.walk(cache):
            for fn in filenames:
                file = Path(directory) / fn
                if file.suffix:
                    assert file.stat().st_mtime_ns == stats[file]


def test_build_specific():
    run(build, None, *prepare('default', *['default']), **{'draft': ''})


temp = Path('./tests/input/temp')


@pytest.mark.skipif(temp.exists() and len(list(temp.iterdir())) == 0, reason='No temp files found')
def test_build_temp():
    run(build, None, './tests/input/temp/hero_card.tex', '--draft')
