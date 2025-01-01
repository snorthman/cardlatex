import logging
import sys
import shutil
from datetime import datetime
from pathlib import Path

import click

from .__version__ import version
from .cache import Cache
from .xml import XML


class FileFormatter(logging.Formatter):
    prefix = '                          | '

    def format(self, record):
        return f'{self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")} {record.levelname:<5} | ' + f'\n{self.prefix}'.join(record.msg.split('\n'))


class StreamFormatter(logging.Formatter):
    def format(self, record):
        return f'{record.levelname[0]} > ' + f'\n    '.join(record.msg.split('\n'))


@click.command()
@click.argument('tex', nargs=1, type=click.Path(exists=True))
@click.option('--debug', is_flag=True, hidden=True, default=False)
def cardlatex(tex: Path, debug: bool):
    from .tex2 import Tex

    start = datetime.now()
    t = Tex(Path(tex))

    logging_file = t.cardlatex_log_path.as_posix()

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
        t.parse()
        pass
    except Exception as e:
        logging.error(str(e))
        logging_result = ' with errors'
        if debug:
            raise e
        else:
            print(f'\ncardlatex has failed, see {logging_file[1]} for details\nE > {type(e).__name__}: {e}\n', file=sys.stderr)
    finally:
        logging.info(f'cardlatex ended in {datetime.now() - start}{logging_result}')
        logging.info(f'tempfiles are stored at\n{t.cache_dir.resolve()}')
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)



# @click.command()
# @click.argument('xml', nargs=1, type=click.Path(exists=True))
# @click.option('--test', type=click.Path(exists=True), required=False,
#               help='Specify a .tex file within the given XML to compile individually. This option allows you to target and compile a single .tex file from the XML for testing purposes.')
# @click.option('--debug', is_flag=True, hidden=True, default=False)
# def cardlatex(xml: str, test: str, debug: bool):
#     c = Cache(xml)
#
#     start = datetime.now()
#
#     logging_file = (c.cache_directory / 'cardlatex.log').as_posix(), c.working_directory / (c.file_xml.name + '.log')
#
#     handler_file = logging.FileHandler(filename=logging_file[0], mode='w')
#     handler_file.setFormatter(FileFormatter())
#     handler_file.setLevel(logging.DEBUG)
#
#     handler_stream = logging.StreamHandler()
#     handler_stream.setFormatter(StreamFormatter())
#     handler_stream.setLevel(logging.DEBUG if debug else logging.INFO)
#
#     logger = logging.getLogger()
#     logger.setLevel(logging.DEBUG)
#     [logger.addHandler(_) for _ in (handler_file, handler_stream)]
#
#     logging_test = f' --test {test}' if test else ''
#     logging_debug = f' --debug' if debug else ''
#     logging.info(f'cardlatex ({version}) {xml}{logging_test}{logging_debug}')
#
#     logging_result = ''
#     try:
#         x = XML(c, debug)
#         x.validate()
#         x.build(test=test)
#     except Exception as e:
#         logging.error(str(e))
#         logging_result = ' with errors'
#         if debug:
#             raise e
#         else:
#             print(f'\ncardlatex has failed, see {logging_file[1]} for details\nE > {type(e).__name__}: {e}\n', file=sys.stderr)
#     finally:
#         logging.info(f'cardlatex ended in {datetime.now() - start}{logging_result}')
#         logging.info(f'tempfiles are stored at\n{c.cache_directory.resolve()}')
#         for handler in logger.handlers:
#             handler.close()
#             logger.removeHandler(handler)
#
#         shutil.move(logging_file[0], logging_file[1])


if __name__ == '__main__':
    cardlatex()
