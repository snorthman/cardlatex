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

        # self._options: dict[str, str] = self._xml.getroot().attrib

    @property
    def draft(self) -> bool:
        return self._options['draft'].lower() == 'true'

    def validate(self, file: Path):
        with open(file) as f:
            xml = f.read()

        template = jinja2.Template(template_xsd)
        schema = xmlschema.XMLSchema11(template.render())
        schema.validate(xml)

        texelements = []
        for element in schema.to_dict(xml)['tex']:
            file = self._cache.working_directory() / element['@file']
            assert file.exists(), FileNotFoundError(file)

            self._tex.append(tex := Tex(file, element))
            texelements.append({
                'type': element['@file'],
                'file': element['@file'],
                'variables': list(tex.variables)
            })

        # for tex in self._tex:
        schema = xmlschema.XMLSchema11(template.render(texelements=texelements))
        schema.validate(xml)

        for tex in self._tex:
            tex.write(self._cache)
        pass

        # gather tex files, create Tex objects, create xsd templates based on variables (and defaults), then validate self

