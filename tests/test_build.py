import shutil
import traceback
from itertools import combinations, chain
from pathlib import Path
from typing import Callable, Tuple

import pytest
from click import BaseCommand
from click.testing import CliRunner

from cardlatex.__main__ import build
from cardlatex.tex import Tex


@pytest.fixture(params=[
    ('default', 'default', None)
])
def args(request):
    tex_file, xlsx_file, expected_error = request.param
    return tex_file, xlsx_file, expected_error


args_build = [['all'], ['mirror'], ['combine'], ['quality', '1'], ['quality', '100']]


@pytest.fixture(params=chain(*[combinations(args_build, n) for n in range(len(args_build))]))
def kwargs_build(request):
    return {args[0]: args[1] if len(args) == 2 else None for args in request.param}


@pytest.fixture
def output(request, args: Tuple[str, str, Exception]):
    root = Path('./tests/')
    root_input = root / 'input'
    root_output = root / 'output'

    if root_output.exists():
        shutil.rmtree(root_output)
    root_output.mkdir()

    shutil.copytree(root_input / 'art', root_output / 'art', copy_function=shutil.copy)

    tex_file, xlsx_file, expected_error = args

    shutil.copy(root_input / f'{tex_file}.tex', tex := root_output / 'test.tex')
    if xlsx_file:
        shutil.copy(root_input / f'{xlsx_file}.xlsx', root_output / 'test.xlsx')

    cache_dir = Tex(tex).cache_dir
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    return tex_file, xlsx_file, tex.as_posix()


def run(func: Callable | BaseCommand, *args, **kwargs):
    arguments = list(args)
    for key, value in kwargs.items():
        arguments.append(f'--{key}')
        if value:
            arguments.append(value)

    runner = CliRunner()
    result = runner.invoke(func, arguments)
    if result.exit_code != 0:
        raise result.exc_info[0](''.join([' '.join(arguments)] + ['\n'] + traceback.format_exception(result.exception)))


def test_build(output: Tuple[str, str, str], kwargs_build: dict):
    tex_file, xlsx_file, out_file = output
    run(build, out_file, **kwargs_build)
    # run again, timeit and see if its faster (to confirm caching works?)


def test_build_specific(output: Tuple[str, str, str], kwargs_build: dict):
    tex_file, xlsx_file, out_file = output
    if tex_file == 'default' and kwargs_build == {'quality': '1'}:
        run(build, out_file, **kwargs_build)
    else:
        pytest.skip()
