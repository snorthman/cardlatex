from cardlatex import version as cardlatex_version
from setup import version


def test_version():
    assert version == cardlatex_version
    