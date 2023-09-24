from cardlatex import version as cardlatex_version
from setup import version as setup_version


def test_version():
    assert setup_version == cardlatex_version
    