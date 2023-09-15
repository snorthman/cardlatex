from pathlib import Path
import shutil

import pytest
from click.testing import CliRunner

from cardlatex.__main__ import build, generate


@pytest.fixture
def tex():
    root = Path('./tests/')
    root_output = root / 'output'
    if root_output.exists():
        shutil.rmtree(root_output)
    root_output.mkdir()

    shutil.copy(root / 'input/basic.tex', root_output_tex := root_output / 'basic.tex')
    return root_output_tex.as_posix()


@pytest.fixture
def xlsx():
    root = Path('./tests/')
    shutil.copy(root / 'input/basic.xlsx', root_output_xlsx := root / 'output/basic.xlsx')
    return root_output_xlsx.as_posix()


def test_build(tex: str):
    runner = CliRunner()
    result = runner.invoke(build, tex)
    if result.exit_code != 0:
        raise result.exception


def test_build_with_xlsx(tex: str, xlsx: str):
    runner = CliRunner()
    result = runner.invoke(build, tex)
    if result.exit_code != 0:
        raise result.exception


def test_generate():
    runner = CliRunner()
    result = runner.invoke(generate, tex)
    if result.exit_code != 0:
        raise result.exception
