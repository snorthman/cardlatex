from pathlib import Path
from typing import Tuple

import click

from . import PaperEnum, version
from .tex import Tex


@click.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('-a', '--all', 'build_all', is_flag=True,
              help=r'Override the \cardlatex[include] configuration to be undefined.')
@click.option('-m', '--mirror', is_flag=True,
              help=r'If \cardlatex[back] is undefined, it mirrors \cardlatex[front] instead.')
@click.option('-c', '--combine', is_flag=True,
              help='Combine source tex files into a single PDF file.')
@click.option('-p', '--print', 'paper', type=click.Choice([p.value for p in PaperEnum]), default=PaperEnum.A4.value, show_default=True,
              help='Arranging all cards in a grid of pages for printing at specified paper size.')
@click.option('-q', '--quality', type=click.IntRange(1, 100), default=100, show_default=True,
              help='Resample all images to QUALITY%. Useful for debugging and faster compilation.')
@click.version_option(version)
def build(tex: Tuple[Path, ...], build_all: bool, mirror: bool, combine: bool,  paper: PaperEnum, quality: int):
    args = ['combine', 'build_all', 'mirror', 'paper', 'quality']
    kwargs = {key: value for key, value in locals().items() if key in args}
    for path in tex:
        path = Path(path)
        t = Tex(path)
        t.build(**kwargs)


if __name__ == '__main__':
    build()
