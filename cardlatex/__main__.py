import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple

import click

from . import version, tempdir
from .pdf import grid_pdf, combine_pdf
from .tex import Tex


@click.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('-a', '--all', 'build_all', is_flag=True,
              help=r'Override the \cardlatex[include] configuration to be undefined.')
@click.option('-c', '--combine', is_flag=True,
              help='Combine source tex files into a single PDF file.')
@click.option('-p', '--print', 'paper', is_flag=True,  # type=click.Choice([p.value for p in PaperEnum]), default=None,
              help='Arranges all cards in grids in either A4 or A3 sizes.')
@click.option('-d', '--draft', is_flag=True,
              help=r'Resample all images to a much smaller size to improve compilation speeds.')
@click.option('--debug', is_flag=True, hidden=True)
@click.version_option(version)
def build(tex: Tuple[Path, ...], build_all: bool, combine: bool, paper: bool, draft: bool, debug: bool):
    start = datetime.now()
    context = click.get_current_context()
    logging.info(f'cardlatex {version}\t{context.params}')

    logger = logging.getLogger()
    [logger.removeHandler(handler) for handler in logger.handlers]
    handler = logging.FileHandler(filename=(tempdir / 'cardlatex.log').as_posix(), mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    try:
        kwargs = {key: value for key, value in locals().items() if key in context.params and key != 'tex'}
        builds: list[Tex] = [Tex(path).build(**kwargs) for path in tex]

        if paper:
            [grid_pdf(b.build_pdf_path, b.has_back) for b in builds]

        if combine and len(builds) > 1:
            if not all([b.completed for b in builds]):
                raise RuntimeError('Not all .tex files have successfully compiled.')
            combine_pdf(*[b.build_pdf_path for b in builds])
            builds[0].release()
        else:
            for b in builds:
                b.release()
    except Exception as e:
        print(e, file=sys.stderr)
        logging.exception(e)
        if debug:
            raise e
        else:
            exit(1)
    else:
        cleanup()
    finally:
        end = datetime.now() - start
        print(f'cardlatex v{version} ran for {end}')
        logging.info(f'process ended in {end}')


def cleanup():
    last_month = time.time_ns() - int(1e9 * 60**2 * 24 * 30)
    for directory in tempdir.iterdir():
        if directory.is_dir():
            for fn in directory.iterdir():
                if fn.stem.startswith('.') and fn.suffix == '.cardlatex':
                    if last_month > fn.lstat().st_mtime_ns:
                        shutil.rmtree(directory)


if __name__ == '__main__':
    build()
