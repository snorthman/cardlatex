import tempfile
from typing import Tuple
from pathlib import Path

import click

from . import PaperEnum, version
from .tex import Tex


@click.group()
@click.version_option(version)
def cli():
    pass


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('-c', '--combine', is_flag=True, help='Combine source tex files into a single PDF file.')
@click.option('-a', '--all', 'build_all', is_flag=True, help=r'Override the \cardlatex[include] configuration to be undefined.')
@click.option('-m', '--mirror', is_flag=True, help=r'If \cardlatex[back] is undefined, it mirrors \cardlatex[front] instead.')
@click.option('-p', '--print', 'paper', type=click.Choice([p.value for p in PaperEnum]), default=PaperEnum.A4.value)
@click.option('-q', '--quality', type=click.IntRange(1, 100))
def build(tex: Tuple[Path, ...], combine: bool, build_all: bool, mirror: bool, paper: PaperEnum, quality: int):
    args = ['combine', 'build_all', 'mirror', 'paper', 'quality']
    kwargs = {key: value for key, value in locals().items() if key in args}
    for path in tex:
        path = Path(path)
        t = Tex(path)
        t.build(**kwargs)


@cli.command()
@click.argument('tex', nargs=-1, type=click.Path(exists=True))
@click.option('--orphan', is_flag=True, default=True, help='Set aside orphaned columns.')
def generate(tex: Tuple[Path, ...], orphan: bool):
    """
    Copy XML files from source to destination.
    """
    for path in tex:
        path = Path(path)
        t = Tex(path)
        t.generate()


if __name__ == '__main__':
    cli()
