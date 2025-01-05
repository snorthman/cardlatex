import hashlib
import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click

from .__version__ import version
from .tex import write
from .xelatex import xelatex


class FileFormatter(logging.Formatter):
    prefix = '                          | '

    def format(self, record):
        return f'{self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")} {record.levelname:<5} | ' + f'\n{self.prefix}'.join(record.msg.split('\n'))


class StreamFormatter(logging.Formatter):
    def format(self, record):
        return f'{record.levelname[0]} > ' + f'\n    '.join(record.msg.split('\n'))


@click.command()
@click.argument('tex', nargs=1, type=click.Path(exists=True))
@click.option('--override_draft', is_flag=True, default=None)
# @click.option('--grid', default=None)
@click.option('--debug', is_flag=True, hidden=True, default=False)
def cardlatex(tex: Path, override_draft: bool | None, debug: bool):
    start = datetime.now()
    file = Path(tex)

    cache_dir = Path(tempfile.gettempdir()) / 'cardlatex' / hashlib.sha1(file.resolve().as_posix().encode('utf-8')).hexdigest()
    cache_dir.mkdir(exist_ok=True, parents=True)

    logging_file = file.with_suffix('.cardlatex.tex.log').as_posix()

    handler_file = logging.FileHandler(filename=logging_file, mode='w')
    handler_file.setFormatter(FileFormatter())
    handler_file.setLevel(logging.DEBUG)

    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(StreamFormatter())
    handler_stream.setLevel(logging.DEBUG if debug else logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    [logger.addHandler(_) for _ in (handler_file, handler_stream)]

    logging.info(f'cardlatex ({version})')
    logging_result = ''

    try:
        out_file, is_draft, has_back = write(file)
        xelatex(out_file, cache_dir, override_draft if override_draft is not None else is_draft)
    except Exception as e:
        logging.error(str(e))
        logging_result = ' with errors'
        if debug:
            raise e
        else:
            for _ in f'cardlatex has failed, see {logging_file[1]} for details\nE > {type(e).__name__}: {e}\n'.split('\n'):
                logging.error(_, file=sys.stderr)
    finally:
        logging.info(f'cardlatex ended in {datetime.now() - start}{logging_result}')
        logging.info(f'tempfiles are stored at\n{cache_dir.resolve()}')
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)


if __name__ == '__main__':
    cardlatex()
