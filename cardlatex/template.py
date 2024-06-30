import importlib.resources

template_tex = importlib.resources.read_text(__package__, 'template.tex')
template_xsd = importlib.resources.read_text(__package__, 'template.xsd')
