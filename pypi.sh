#!/bin/bash

python -m pip install --upgrade build
python -m build
python -m pip install --upgrade twine
python -m twine upload --repository pypi dist/*
read -n 1 -s -r -p ""