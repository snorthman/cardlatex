import pathlib
import tempfile

from cardlatex.__version__ import version

tempdir = pathlib.Path(tempfile.gettempdir()) / 'cardlatex'
tempdir.mkdir(exist_ok=True, parents=True)
