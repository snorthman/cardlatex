import tempfile
from typing import Tuple
from pathlib import Path

import click

from . import PaperEnum


@click.group()
def cli():
    pass


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('-c', '--combine', is_flag=True, help='Combine source tex files into a single PDF file.')
@click.option('-p', '--print', 'paper', type=click.Choice([p.value for p in PaperEnum]), default=PaperEnum.A4.value)
@click.option('-q', '--quality', type=click.IntRange(1, 100))
def compile(tex: Tuple[Path, ...], combine: bool, paper: PaperEnum, quality: int):
    pwd = Path(tempfile.gettempdir()) / 'cardlatex'
    pwd.mkdir(exist_ok=True)


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('--only-new', is_flag=True, help='Copy only new files.')
def xml(tex: Tuple[Path, ...], only_new):
    """
    Copy XML files from source to destination.
    """
    pass


if __name__ == '__main__':
    cli()
