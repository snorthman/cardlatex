from setuptools import setup

version = '0.3.0'

if __name__ == '__main__':
    setup(
        name='cardlatex',
        version=version,
        packages=['cardlatex'],
        url='',
        license='',
        author='Stan Noordman',
        author_email='snorthman1@gmail.com',
        description='',
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
