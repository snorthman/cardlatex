import importlib.resources

template = importlib.resources.read_text(__package__, 'template.tex')
