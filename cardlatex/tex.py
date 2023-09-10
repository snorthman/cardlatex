import re
import importlib.resources
import xml.etree.ElementTree as xml
from pathlib import Path
from typing import List


def cardlatexprop(prop: str = ''):
    return rf'\cardlatex configuration object' + (f'"{prop}"' if prop else '')


class Tex:
    def __init__(self, tex: Path):
        self._path = tex
        self._config = dict()
        self._template = self.template()

        # with open(tex.parent / tex.with_suffix('.xml')) as f:
        #     self._xml = f.read()
        with open(tex, 'r') as f:
            self._tex = f.read()

    @staticmethod
    def template() -> str:
        with importlib.resources.open_text('cardlatex.resources', 'template.tex') as f:
            return f.read()

    def _set_length_prop(self, prop: str, value: str):
        value = str(value).strip()
        assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
            ValueError(f'invalid value "{value}" for {prop}'))
        self._config[prop] = value

    @property
    def width(self) -> str:
        return self._config['width']

    @width.setter
    def width(self, value: str):
        self._set_length_prop('width', value)

    @property
    def height(self) -> str:
        return self._config['height']

    @height.setter
    def height(self, value: str):
        self._set_length_prop('height', value)

    @property
    def bleed(self) -> str:
        return self._config.get('bleed', '0')

    @bleed.setter
    def bleed(self, value: str):
        self._set_length_prop('bleed', value)

    @property
    def quality(self) -> str:
        return self._config.get('quality', '100')

    @quality.setter
    def quality(self, value: int):
        value = int(value)
        assert 100 >= value >= 1, ValueError(f'value must be between 1 and 100 ("{value}") for quality')
        self._config['quality'] = value

    @property
    def include(self) -> List[int]:
        return self._config.get('include', None)

    @include.setter
    def include(self, value: str):
        values = value.replace(' ', '').split(',')
        include = []
        for v in values:
            if r := re.match(r'(\d+)\.{2,3}(\d+)', v):
                left, right = int(r.group(1)), int(r.group(2))
                assert left <= right, ValueError(rf'{left} is larger than {right} in {v} for {cardlatexprop("include")}')
                include.extend(range(left, right + 1))
            else:
                include.append(int(v))
        self._config['include'] = include

    @property
    def front(self) -> str:
        return self._config['front']

    @front.setter
    def front(self, value: str) -> str:
        self._config['front'] = value

    @property
    def back(self) -> str:
        return self._config.get('back', self.front)

    @back.setter
    def back(self, value: str) -> str:
        self._config['back'] = value

    def generate(self, dest: Path):
        root = xml.Element('cardlatex')

    def _load_config(self):
        props = set()
        matches: List[re.Match] = list(re.finditer(r'\\cardlatex\[(\w+)]\{', self._tex))

        for m, match in enumerate(matches):
            assert hasattr(Tex, prop := match.group(1)), (
                KeyError(rf'unknown {cardlatexprop(prop)}'))
            assert prop not in props, (
                KeyError(rf'duplicate {cardlatexprop(prop)}'))
            props.add(prop)

            b = 1
            rb: re.Match = None
            for rb in re.finditer(r'(?<!\\)[{}]', self._tex[match.end():]):
                b = b + (1 if rb.group() == '{' else -1)
                if b == 0:
                    break
            assert b == 0 and rb, (
                ValueError(rf'no closing bracket found for {cardlatexprop(prop)}'))

            endpos = match.end() + rb.end() - 1
            if m < len(matches) - 1:
                assert endpos < matches[m + 1].start(), (
                    ValueError(rf'{cardlatexprop()} found inside {cardlatexprop(prop)}'))

            setattr(self, prop, self._tex[match.end():endpos])

    def _load_xml(self):
        root = xml.parse(self._path.with_suffix('.xml')).getroot()

    def build(self, dest: Path):
        dest.mkdir(parents=True, exist_ok=True)
        
        self._load_config()
        data = self._load_xml()

        rows = []
        for row in self.include:
            pass
        # prepare <$front$> and <$back$> val

        for r in re.finditer(r'<\$(\w+)\$>', self._template):
            propv = getattr(self, r.group(1))

