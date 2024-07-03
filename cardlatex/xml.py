from pathlib import Path

import jinja2
import xmlschema

from .template import template_xsd
from .cache import Cache
from .tex import Tex_ as Tex


class XML:
    def __init__(self, cache: Cache):
        self._cache = cache
        self._tex: list[Tex] = []
        self._draft = None
        self._print = None
        self._paper = None

    def validate(self, file: Path):
        with open(file) as f:
            xml = f.read()

        template = jinja2.Template(template_xsd)
        schema = xmlschema.XMLSchema11(template.render())
        schema.validate(xml)
        xml_dict: dict = schema.to_dict(xml)

        self._draft = xml_dict['@draft']
        self._print = xml_dict['@print']
        self._paper = xml_dict.get('@paper', None)

        texelements = []
        for element in xml_dict['tex']:
            file = self._cache.working_directory() / element['@file']
            assert file.exists(), FileNotFoundError(file)

            self._tex.append(tex := Tex(self._cache, file, element))
            texelements.append({
                'type': element['@file'],
                'file': element['@file'],
                'variables': list(tex.variables)
            })

        schema = xmlschema.XMLSchema11(template.render(texelements=texelements))
        schema.validate(xml)

    def build(self):
        for tex in self._tex:
            tex.write(is_draft=self._draft, is_print=self._print)

        for tex in self._tex:
            tex.xelatex(is_draft=self._draft, is_print=self._print)
