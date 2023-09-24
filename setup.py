from setuptools import setup

version = '0.4.1'

if __name__ == '__main__':
    setup(
        name='cardlatex',
        version=version,
        packages=['cardlatex'],
        url=r'https://github.com/snorthman/cardlatex',
        license='MIT License',
        author='Stan Noordman',
        author_email='snorthman1@gmail.com',
        description='cardlatex is a XeLaTeX wrapper which compiles TeX from specific templated .tex and .xlsx files.',
        install_requires=[
            'click',
            'openpyxl',
            'pandas',
            'wand',
            'pikepdf'
        ],
        extras_require={
            'dev': [
                'pytest',
                'coverage',
                'flake8'
            ]
        },
        entry_points={
            'console_scripts': [
                'cardlatex = cardlatex.__main__:build',
            ],
        }
    )
