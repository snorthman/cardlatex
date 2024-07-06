import logging
import re
from datetime import datetime

import jinja2
import xmlschema

from .template import template_xsd
from .cache import Cache
from .tex import Tex


class XML:
    def __init__(self, cache: Cache):
        self._cache = cache
        self._tex: list[Tex] = []

        self._draft = None
        self._print = None
        self._paper = None
        self._kwargs = []

    def validate(self):
        with open(self._cache.file_xml) as f:
            xml = f.read()
        xml_dict, tex_list = {}, []

        jj2_texelements = []
        template = jinja2.Template(template_xsd)
        for i in range(2):
            schema = xmlschema.XMLSchema11(template.render(texelements=jj2_texelements))
            try:
                schema.validate(xml)
            except xmlschema.validators.exceptions.XMLSchemaValidationError as e:
                raise Exception('XML validation failed: \n' + re.search(r'Instance:\n\n(.+)\nPath:', e.msg, re.DOTALL).group(1) + '\nReason: ' + e.reason)

            xml_dict: dict = schema.to_dict(xml)
            tex_list.clear()
            for element in xml_dict['tex']:
                file = self._cache.working_directory() / element['@file']
                assert file.exists(), FileNotFoundError(file)

                tex_list.append(tex := Tex(self._cache, file))
                tex.set_attributes(element)
                jj2_texelements.append({
                    'type': element['@file'],
                    'file': element['@file'],
                    'variables': list(tex['variables'])
                })

        self._tex = tex_list
        self._draft = xml_dict['@draft']
        self._print = xml_dict['@print']
        self._paper = xml_dict.get('@paper', None)
        self._kwargs = xml_dict.get('keywords', [])

        logging.info(self._cache.file_xml.name + ' is valid.')

    def build(self):
        for tex in self._tex:
            tex.write(self._kwargs, is_draft=self._draft, is_print=self._print)

        start = datetime.now()
        for tex in self._tex:
            tex_start = datetime.now()
            try:
                tex.xelatex(is_draft=self._draft)
            except Exception as e:
                logging.error(str(e))
                logging.info(f'{tex.name} failed after {datetime.now() - tex_start}')
            else:
                logging.info(f'{tex.name} completed after {datetime.now() - tex_start}')

        logging.info(f'All builds finished after {datetime.now() - start}')
