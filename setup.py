from setuptools import setup

version = '1.0.0'

if __name__ == '__main__':
    setup(
        name='cardlatex',
        version=version,
        packages=['cardlatex'],
        package_data={"cardlatex": ["*.tex"]},
        url=r'https://github.com/snorthman/cardlatex',
        license='MIT License',
        author='C.R. Noordman',
        author_email='snorthman1@gmail.com',
        description='cardlatex is a XeLaTeX wrapper which compiles TeX from specifically templated .tex and .xml files.',
        python_requires='>=3.10, <4',
        install_requires=[
            'click~=8.1',
            'wand~=0.6',
            'pikepdf~=8.4',
            'pexpect~=4.9',
            'xmlschema~=3.3',
            'jinja2~=3.1'
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
                'cardlatex = cardlatex.__main__:cardlatex',
            ],
        }
    )
