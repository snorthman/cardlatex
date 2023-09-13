from pathlib import Path
import shutil

import pytest
from click.testing import CliRunner

from cardlatex.__main__ import compile, xml


@pytest.fixture
def tex():
    shutil.rmtree('./tests/output')
    shutil.copy('./tests/input/basic.tex', './tests/output/basic.tex')
    return './tests/output/basic.tex'


def test_compile(tex: str):
    runner = CliRunner()
    result = runner.invoke(compile, tex)
    if result.exit_code != 0:
        raise result.exception


def test_generate():
    runner = CliRunner()
    result = runner.invoke(xml, tex)
    if result.exit_code != 0:
        raise result.exception
