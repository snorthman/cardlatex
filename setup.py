from setuptools import setup

version = '0.3.0'

if __name__ == '__main__':
    setup(
        name='cardlatex',
        version='',
        packages=['cardlatex'],
        url='',
        license='',
        author='snorthman',
        author_email='',
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
            ]
        },
        entry_points={
            'console_scripts': [
                'cardlatex = cardlatex.__main__:build',
            ],
        }
    )
