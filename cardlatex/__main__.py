import logging
import sys
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
    context = click.get_current_context()

    logger = logging.getLogger()
    handler = logging.FileHandler(filename=(tempdir / 'cardlatex.log').as_posix(), mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    try:
        kwargs = {key: value for key, value in locals().items() if key in context.params and key != 'tex'}
        builds: list[Tex] = [Tex(path).build(**kwargs) for path in tex]

        if paper:
            [grid_pdf(b.output, b.has_back) for b in builds]

        if combine and len(builds) > 1:
            if not all([b.completed for b in builds]):
                raise RuntimeError('Not all .tex files have succesfully compiled.')
            combine_pdf(*[b.output for b in builds])
            builds[0].release()
        else:
            [b.release() for b in builds]
    except Exception as e:
        print(e, file=sys.stderr)
        logging.info(f'cardlatex {version}\t{context.params}')
        logging.exception(e)
        if debug:
            raise e
        else:
            exit(1)


if __name__ == '__main__':
    build()
