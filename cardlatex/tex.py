import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Callable, Optional

from .template import template_tex


def assert_tex_length(value: str) -> str:
    value = str(value).strip()
    assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
        ValueError(f'invalid measurement value "{value}"'))
    return value


def expand(text: str) -> Generator[tuple[str, str | None, str], None, None]:
    matches: list[re.Match] = list(re.finditer(r'^([^\\\n]*?)\\([a-z]+)(\[\w+])?\{', text, re.M))
    for m, match in enumerate(matches):
        opt = match.group(3)[1:-1] if match.group(3) else ''
        if '%' in match.group(1) or '%' in opt:
            continue

        # find the end of this expansion
        b = 1
        rb: re.Match | None = None
        for rb in re.finditer(r'(?<!\\)[{}]', text[match.end():]):
            b = b + (1 if rb.group() == '{' else -1)
            if b == 0:
                break
        assert b == 0 and rb, (
            ValueError(f'no closing bracket found for "{match.group(2)}"'))
        yield match.group(2), opt if opt else None, text[match.end():match.end() + rb.end() - 1]


def readiter(pattern: str, text: str, func: Callable[[re.Match], str]) -> str:
    t, rr = '', 0
    for m in re.finditer(pattern, text):
        l, r = m.span()
        t += text[rr:l] + func(m)
        rr = r
    if rr > 0:
        return t + text[rr:]
    return ''


def templating(m: re.Match) -> str:
    key = m.group(1)
    if key == 'bleed':
        value = bleed.value
    elif key == 'counter':  # and self._draft is true
        value = r'\node[anchor=north west,white,xshift=-\bleed,yshift=\bleed] at (TL) {\texttt{\arabic{cardlatex}}};'
    else:
        raise SystemError(f'template.tex has an unknown key {key}')
    return value


def inputting(m: re.Match) -> str:
    input_path = Path(m.group(3)).with_suffix('.tex')
    if '%' in m.group(1) or not input_path.exists():
        value = ''
    else:
        with open(input_path, 'r') as f:
            value = f.read()
    return value


@dataclass
class Option:
    key: str
    required: Optional[bool] = field(default=False)
    _value: Optional[str] = field(default=None, init=False)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self._value is None:
            self._value = value
        else:
            raise ValueError(f'Duplicate "{self.key}" commands detected, only one should be present per TeX file')

    def parse(self, content, optional=None):
        self.value = content

    def clear(self):
        self._value = None


class OptionLength(Option):
    def parse(self, content, optional=None):
        content = str(content).strip()
        assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', content), (
            ValueError(f'invalid measurement value "{content}"'))
        super().parse(content)


class OptionVar(Option):
    var: Optional[str] = field(init=False)

    def parse(self, content, optional=None):
        self.var = optional
        if not self.key == 'unvar':
            super().parse(content)


class OptionCard(Option):
    copies: Optional[int] = field(default=1, init=False)

    def parse(self, content, optional=None):
        try:
            self.copies = int(optional) if optional else 1
        except ValueError:
            raise ValueError(f'could not parse number of copies: "{optional}"')
        super().parse(content)

    def output(self, index: int, is_draft: bool = False, **variables: dict[str: str | None]):
        for cmd, var_name, text in expand(self.value):
            if cmd == 'var' and var_name in variables:
                variables[var_name] = text.replace('\t', ' ').strip('\n ')

        out = '\n'.join([r'\toggle' + ('false' if text is None else 'true') + '{' + var + '}' for var, text in variables.items()])
        for i in range(self.copies if not is_draft else 1):
            for option in [front, back]:
                text = option.value
                if text is None:
                    continue

                for var, content in variables.items():
                    text = text.replace(fr'\if[<${var}$>]', r'\ifvar{' + var + '}').replace(f'<${var}$>', '' if content is None else content)

                copies = f'COPY {i + 1}, ' if self.copies > 1 else ''
                opts = ''.join('{' + _.value + '}' for _ in (dpi, width, height))
                out += '\n'.join([
                    f'\n\n% CARD {index}, {copies}{option.key.upper()}',
                    r'\begin{tikzcard}' + opts,
                    text,
                    r'\end{tikzcard}'
                ])
        return out + '\n\\stepcounter{cardlatex}\n\n'


options: list[Option] = [
    width := OptionLength('width', True),
    height := OptionLength('height', True),
    bleed := OptionLength('bleed'),
    dpi := Option('dpi'),
    front := Option('front', True),
    back := Option('back'),
    OptionCard('card'),  # placeholder,
    OptionVar('unvar'),  # placeholder,
    OptionVar('var')     # placeholder, will instead fill up [cards]
]


def write(file: Path) -> tuple[Path, bool, bool]:
    cwd = os.getcwd()
    os.chdir(file.parent)
    with open(file.name) as f:
        source = f.read()

    cardlatex = [(optional, text) for cmd, optional, text in expand(source) if cmd == 'cardlatex']
    assert len(cardlatex) > 0, rf'Missing \cardlatex command, consider cardlatex.exe --help'
    assert len(cardlatex) == 1, rf'Duplicate \cardlatex commands detected, only one \cardlatex should be present per TeX file'
    is_draft = cardlatex[0][0] == 'draft'

    [_.clear() for _ in options]
    cards: list[OptionCard | OptionVar] = []
    cards_cmd = {'card': OptionCard, 'var': OptionVar, 'unvar': OptionVar}
    for cmd, optional, text in expand(cardlatex[0][1]):
        for option in options:
            if cmd == option.key:
                if cmd in cards_cmd:
                    cards.append(option := cards_cmd[cmd](cmd))
                option.parse(text, optional)
                break

    options_required_failed = [_ for _ in options if _.required and _.value is None]
    if options_required_failed:
        options_required_failed = ', '.join(_.key for _ in options_required_failed)
        raise ValueError(f'Missing required options: {options_required_failed}')

    variables = {m.group(1): None for m in re.finditer(r'<\$(\w+)\$>', front.value + (back.value if back.value is not None else ''))}
    content = []
    for i, option in enumerate(cards):
        if isinstance(option, OptionVar):
            variables[option.var] = option.value if option.key == 'var' else None
        else:
            content.append(option.output(i, is_draft, **variables))

    tex = {
        'template': readiter(r'<\$(\w+)\$>', template_tex, templating),
        '@input': readiter(r'^(.*)(\\input\{([\w.]+)})', source, inputting),
        '@toggles': '\n'.join([r'\newtoggle{' + value + '}' for value in variables.keys()]),
        '@document': '\\begin{document}\n\n\t',
        'content': '\n'.join(content).replace('\n', '\n\t'),
        'enddocument': '\n\\end{document}\n'
    }

    os.chdir(cwd)
    with open(out_file := file.with_suffix('.cardlatex.tex'), 'w') as f:
        for key, value in tex.items():
            if value:
                if key.startswith('@'):
                    f.write('\n\n' + '%' * 68 + '\n% ' + key[1:].upper() + '\n\n')
                f.write(value)
    return out_file, is_draft, back.value is not None
