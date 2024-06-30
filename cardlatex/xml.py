from pathlib import Path

from lxml import etree

from .template import template_xsd
from .cache import Cache
from .tex import Tex


class XML:
    def __init__(self, file: Path, cache: Cache):
        self._xml = etree.parse(file)
        self._schema = etree.XMLSchema(etree.XML(template_xsd.encode()))
        self._cache = cache
        self._tex: list[Tex] = []

        self._options: dict[str, str] = self._xml.getroot().attrib

    @property
    def draft(self) -> bool:
        return self._options['draft'].lower() == 'true'

    def validate(self):
        self._schema.assertValid(self._xml)

        root = self._xml.getroot()
        for el in root:
            file = self._cache.working_directory() / el.attrib['file']

            self._tex.append(Tex(self._cache.working_directory() / el.attrib['file']))
        pass

        # gather tex files, create Tex objects, create xsd templates based on variables (and defaults), then validate self

