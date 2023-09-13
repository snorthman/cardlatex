import tempfile
from typing import Tuple
from pathlib import Path

import click

from . import PaperEnum
from .tex import Tex


@click.group()
def cli():
    pass


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('-c', '--combine', is_flag=True, help='Combine source tex files into a single PDF file.')
@click.option('-a', '--all', is_flag=True, help=r'Override the \cardlatex[include] configuration to be undefined.')
@click.option('-p', '--print', 'paper', type=click.Choice([p.value for p in PaperEnum]), default=PaperEnum.A4.value)
@click.option('-q', '--quality', type=click.IntRange(1, 100))
def compile(tex: Tuple[Path, ...], combine: bool, all: bool, paper: PaperEnum, quality: int):
    root = pwd()
    for path in tex:
        path = Path(path)
        t = Tex(path)
        t.build(root / path.name)


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('--orphan', is_flag=True, default=True, help='Set aside orphaned columns.')
def xml(tex: Tuple[Path, ...], orphan: bool):
    """
    Copy XML files from source to destination.
    """
    for path in tex:
        path = Path(path)
        t = Tex(path)
        t.generate()


def pwd():
    path = Path(tempfile.gettempdir()) / 'cardlatex'
    path.mkdir(exist_ok=True)
    return path


if __name__ == '__main__':
    cli()
