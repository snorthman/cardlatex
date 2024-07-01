from pathlib import Path

from lxml import etree
import xmlschema

from .template import template_xsd
from .cache import Cache
from .tex import Tex_ as Tex


class XML:
    def __init__(self, cache: Cache):
        self._schema = xmlschema.XMLSchema11(template_xsd)
        self._cache = cache
        self._tex: list[Tex] = []

        # self._options: dict[str, str] = self._xml.getroot().attrib

    @property
    def draft(self) -> bool:
        return self._options['draft'].lower() == 'true'

    def validate(self, file: Path):
        self._schema.validate(file.as_posix())
        xml: dict = self._schema..to_dict(file.as_posix())

        for tex in xml['tex']:
            file = self._cache.working_directory() / tex['@file']
            assert file.exists(), FileNotFoundError(file)

            tex = Tex(file, {key[1:]: value for key, value in tex.items() if key.startswith('@')})

            self._tex.append(tex)

        pass

        # gather tex files, create Tex objects, create xsd templates based on variables (and defaults), then validate self

