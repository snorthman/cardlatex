import logging
import sys
import shutil
from datetime import datetime

import click

from .__version__ import version
from .cache import Cache
from .xml import XML


class CustomFormatter(logging.Formatter):
    prefix = '                          | '

    def format(self, record):
        return f'{self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")} {record.levelname:<5} | ' + f'\n{self.prefix}'.join(record.msg.split('\n'))


@click.command()
@click.argument('xml', nargs=1, type=click.Path(exists=True))
@click.option('--test', type=click.Path(exists=True), required=False,
              help='Specify a .tex file within the given XML to compile individually. This option allows you to target and compile a single .tex file from the XML for testing purposes.')
@click.option('--debug', is_flag=True, hidden=True, default=False)
def cardlatex(xml: str, test: str, debug: bool):
    c = Cache(xml)

    start = datetime.now()

    logging_file = (c.cache_directory / 'cardlatex.log').as_posix(), c.working_directory / (c.file_xml.name + '.log')
    logger = logging.getLogger()
    handlers = [
        logging.FileHandler(filename=logging_file[0], mode='w'),
        logging.StreamHandler()
    ]
    for handler in handlers:
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    logging_test = f' --test {test}' if test else ''
    logging_debug = f' --debug' if debug else ''
    logging.info(f'cardlatex ({version}) {xml}{logging_test}{logging_debug}')

    logging_result = ''
    try:
        x = XML(c, debug)
        x.validate()
        x.build(test=test)
    except Exception as e:
        logging.error(str(e))
        logging_result = ' with errors'
        if debug:
            raise e
        else:
            print(f'cardlatex has failed, see {logging_file[1]} for details\nE > {type(e).__name__}: {e}', file=sys.stderr)
        logging.info(f'tempfiles are stored at\n{c.cache_directory.resolve()}')
    finally:
        logging.info(f'cardlatex ended in {datetime.now() - start}{logging_result}')
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

        shutil.move(logging_file[0], logging_file[1])


if __name__ == '__main__':
    cardlatex()
