import os
from pathlib import Path
from typing import Callable

import freezegun
import pytest


@freezegun.freeze_time("2024-01-01")
@pytest.mark.parametrize('xml', ['test_draft.xml', 'test_print.xml', 'test_draft_print.xml'])
def test_cardlatex(click: Callable, test_dir: Path, xml: str):
    click((test_dir / xml).as_posix())
    [os.remove(_) for _ in test_dir.iterdir() if _.suffix == '.xml' and _ != xml]
    expected_dir = Path('tests/output_expected') / test_dir.name
    with open(expected_dir / (xml + '.log')) as fe, open(test_dir / (xml + '.log')) as ft:
        log = fe.read(), ft.read()
        assert log[0][:log[0].index('cardlatex ended in 0:00:00')] == log[1][:log[1].index('cardlatex ended in 0:00:00')]


@pytest.mark.parametrize('target', ['front_back'])
def test_cardlatex_target(click: Callable, target: str):
    click(Path(f'./tests/input/{target}.tex').as_posix())


def test_cardlatex_path(click: Callable):
    click(Path(r'C:\Repos\monster\tex\hero_ability.tex').as_posix())
