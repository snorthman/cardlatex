import logging
import os
import re
import subprocess
import signal
from pathlib import Path
from datetime import datetime

import pexpect
import pexpect.popen_spawn
from wand.image import Image as WandImage


def resample(source: Path, target: Path):
    lstat = source.lstat()
    with WandImage(filename=source.resolve().as_posix()) as src:
        with src.convert(source.suffix[1:]) as tar:
            if lstat.st_size > 0 and lstat.st_size > 51200:  # in bytes
                tar.transform(resize=f'{round(100 * 51200 / lstat.st_size)}%')
            target.parent.mkdir(parents=True, exist_ok=True)
            tar.save(filename=target.as_posix())
    os.utime(target, ns=(lstat.st_atime_ns, lstat.st_mtime_ns))


def xelatex(file: Path, cache_dir: Path, is_draft: bool):
    start = datetime.now()

    working_dir = file.parent.resolve()
    with open(file) as f:
        source = f.read()
        source_ln = ('\n' + source).split('\n')
    if is_draft:
        with open(cache_dir / file.name, 'w') as f:
            f.write(source)

    cards = []
    for m in re.finditer(r'% CARD (\d+),( COPY \d+,)? (FRONT|BACK)\n', source):
        cards.append({
            'card': m.group(1),
            'side': m.group(3),
            'ln': len(source[:m.end()].split('\n'))
        })

    cmd = f'xelatex.exe -interaction=errorstopmode -file-line-error "{file.stem}".tex'
    cwd = cache_dir.as_posix() if is_draft else working_dir.as_posix()
    if os.name == 'nt':  # Windows
        process = pexpect.popen_spawn.PopenSpawn(cmd, cwd=cwd)
    else:
        process = pexpect.spawn(cmd, cwd=cwd, echo=False)

    try:
        directories = None
        expects = [
            r'cardlatex@graphicpaths\r\n(.*?)\r',
            r'includegraphics@(.+?)\r',
            file.name.replace('.', r'\.') + r':(\d+): (.*)l\.\1',
            pexpect.EOF
        ]
        while True:
            p = process.expect(expects)
            p_send = ''
            if p == 0:
                directories = sorted(['.'] + [m.group(1) for m in re.finditer(r'\{(.+?)}', process.match.group().decode())])
            elif p == 1:
                assert directories is not None
                fn: str = process.match.group(1).decode()
                files = []
                for d in directories + [None]:
                    if d is None:
                        # immediately exit process, missing image errors take long to process
                        raise FileNotFoundError(f'Could not find image "{fn}", searched in:\n-\t' + '\n-\t'.join(files))

                    if (file := working_dir / d / fn).exists():
                        if is_draft:
                            if not (file_resampled := cache_dir / d / fn).exists():
                                resample(file, file_resampled)
                            elif file.lstat().st_mtime_ns != file_resampled.lstat().st_mtime_ns:
                                resample(file, file_resampled)
                            # resampled.add(file_resampled)
                        else:
                            p_send = working_dir.as_posix() + '/'
                        break
                    files.append(file.as_posix())
            elif p == 2:
                xelatex_error = process.match.group(2).decode().replace('\r', '').strip('\n ')
                error_ln = int(process.match.group(1)) - 1  # somehow, the line number is always off by +1

                error_lns = [f'  >> {source_ln[_]}' for _ in range(error_ln - 2, error_ln) if _ >= 0]
                error_lns.append(f'  >> {source_ln[error_ln]}')
                error_lns.extend(
                    [f'  >> {source_ln[_]}' for _ in range(error_ln + 1, error_ln + 3) if _ < len(source_ln)])

                card = -1
                for c, card in enumerate(cards):
                    if error_ln >= card['ln']:
                        card = c
                        if c == len(cards) - 1 or error_ln < cards[c + 1]['ln']:
                            break

                loc = 'Preamble'
                if card > -1:
                    card, side, _ = tuple(cards[card].values())
                    loc = f'Card {card}, {side}'
                msg = '\n'.join([f'Error in {file.name}: {loc}',
                                 *error_lns,
                                 'Error message was',
                                 *[f'  >> {_}' for _ in xelatex_error.split('\n')]])
                raise RuntimeError(msg)
            elif p == 3:  # EOF
                with open(file.with_suffix('.log')) as f:
                    log = f.read()
                m = re.search(r'Output written on (.+)pdf \((\d+)', log)
                logging.info(file.name + f' completed after {datetime.now() - start}! ({m.group(2)} pages)')
                return

            process.sendline(p_send)
    except Exception as e:
        e.add_note(process.buffer.decode())
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/F'], stdout=subprocess.PIPE)
        else:
            os.kill(process.pid, signal.SIGTERM)
        raise e
    finally:
        pass

