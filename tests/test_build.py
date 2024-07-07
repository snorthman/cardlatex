import os
from pathlib import Path
from typing import Callable

import freezegun
import pytest

args_build_params = [['all'], ['combine'], ['print'], ['draft']]


@freezegun.freeze_time("2024-01-01")
# @pytest.mark.parametrize('xml', ['test_draft_print.xml'])
@pytest.mark.parametrize('xml', ['test_draft.xml', 'test_print.xml', 'test_draft_print.xml'])
def test_cardlatex(test_dir: Path, click: Callable, xml: str):
    click((test_dir / xml).as_posix())
    [os.remove(_) for _ in test_dir.iterdir() if _.suffix == '.xml' and _ != xml]
    expected_dir = Path('tests/output_expected') / test_dir.name
    with open(expected_dir / (xml + '.log')) as fe, open(test_dir / (xml + '.log')) as ft:
        assert fe.read() == ft.read()
