from setuptools import setup

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
        'pandas'
    ],
    extras_require={
        'dev': [
            'pytest',
            'coverage',
        ]
    },
    entry_points={
        'console_scripts': [
            'cardlatex = cardlatex.__main__:cli',
        ],
    }
)
