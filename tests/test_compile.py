from pathlib import Path

import pytest
from click.testing import CliRunner

from cardlatex.__main__ import compile, xml


def test_basic():
    runner = CliRunner()
    result = runner.invoke(compile, './tests/input/basic.tex')
    if result.exit_code != 0:
        raise result.exception
