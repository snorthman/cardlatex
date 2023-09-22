import re
from typing import List


def cardlatexprop(prop: str = ''):
    return rf'\cardlatex configuration object' + (f'" {prop}"' if prop else '')


required_props = set()


class Config:

    @staticmethod
    def required(prop):
        required_props.add(prop.__name__)
        return prop

    def __init__(self, tex: str):
        self._config = dict()

        props = set()
        matches: List[re.Match] = list(re.finditer(r'^(.*)\\cardlatex\[(\w+)]\{', tex, re.M))
        for m, match in enumerate(matches):
            if '%' in match.group(1):
                continue

            assert hasattr(Config, prop := match.group(2)), (
                KeyError(rf'unknown {cardlatexprop(prop)}'))
            assert prop not in props, (
                KeyError(rf'duplicate {cardlatexprop(prop)}'))
            props.add(prop)

            b = 1
            rb: re.Match = None
            for rb in re.finditer(r'(?<!\\)[{}]', tex[match.end():]):
                b = b + (1 if rb.group() == '{' else -1)
                if b == 0:
                    break
            assert b == 0 and rb, (
                ValueError(rf'no closing bracket found for {cardlatexprop(prop)}'))

            endpos = match.end() + rb.end() - 1
            if m < len(matches) - 1:
                assert endpos < matches[m + 1].start(), (
                    ValueError(rf'{cardlatexprop()} found inside {cardlatexprop(prop)}'))

            setattr(self, prop, tex[match.end():endpos])

        for prop in required_props:
            if prop not in self._config:
                raise ValueError(cardlatexprop(prop) + ' missing')

    def _set_length_prop(self, prop: str, value: str):
        value = str(value).strip()
        assert re.match(r'^\d+(\.\d+)?(cm|mm|in)?$', value), (
            ValueError(f'invalid value "{value}" for {prop}'))
        self._config[prop] = value

    def __getitem__(self, item):
        return self._config[item]

    def __contains__(self, item):
        return item in self._config

    @property
    @required
    def width(self) -> str:
        return self._config['width']

    @width.setter
    def width(self, value: str):
        self._set_length_prop('width', value)

    @property
    @required
    def height(self) -> str:
        return self._config['height']

    @height.setter
    def height(self, value: str):
        self._set_length_prop('height', value)

    @property
    def bleed(self) -> str:
        return self._config.get('bleed', '0cm')

    @bleed.setter
    def bleed(self, value: str):
        self._set_length_prop('bleed', value)

    @property
    def spacing(self) -> str:
        return self._config.get('spacing', '0cm')

    @spacing.setter
    def spacing(self, value: str):
        self._set_length_prop('spacing', value)

    @property
    def dpi(self) -> str:
        return self._config.get('dpi', '0')

    @dpi.setter
    def dpi(self, value: str):
        self._config['dpi'] = str(float(value))

    @property
    def quality(self) -> str:
        return self._config.get('quality', 100)

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
                left, right = int(r.group(1)) - 1, int(r.group(2)) - 1
                assert left <= right, ValueError(
                    rf'{left} is larger than {right} in {v} for {cardlatexprop("include")}')
                include.extend(range(left, right + 1))
            else:
                include.append(int(v) - 1)
        for i in include:
            if i < 0:
                raise ValueError(f'Including page {i + 1} is invalid for {cardlatexprop("include")}')
        self._config['include'] = include

    @property
    @required
    def front(self) -> str:
        return self._config['front']

    @front.setter
    def front(self, value: str):
        self._config['front'] = value

    @property
    def back(self) -> str:
        return self._config.get('back', self.front)

    @back.setter
    def back(self, value: str):
        self._config['back'] = value
