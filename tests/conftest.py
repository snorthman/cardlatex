import shutil
from pathlib import Path

import pytest
from click import BaseCommand
from click.testing import CliRunner

from cardlatex.__main__ import build_


@pytest.fixture()
def test_dir(request):
    input_dir = Path('tests/input')
    output_dir = Path('tests/output') / request.node.name

    shutil.rmtree(output_dir, ignore_errors=True)
    shutil.copytree(input_dir, output_dir)

    yield output_dir


@pytest.fixture()
def click():
    def f(*args, **kwargs):
        expected_exception = None
        func: BaseCommand = build_

        arguments = list(args)
        for key, value in kwargs.items():
            arguments.append(f'--{key}')
            if value:
                arguments.append(value)

        runner = CliRunner()
        result = runner.invoke(func, arguments + ['--debug'])
        if result.exit_code != 0:
            exception = result.exc_info[0]
            if exception != expected_exception:
                raise result.exception
        else:
            assert expected_exception is None

    yield f
