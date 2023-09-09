# cardlatex

**cardlatex** is a XeLaTeX wrapper which compiles TeX from specific template .tex files. If the working directory
contains a .ctex file and a front.tex file, it runs preprocessing to compile generated .tex files. Otherwise, it 
directly runs XeLaTeX.

## Arguments

- `CTEX`: `.ctex` file to compile.

## Options

- `-f, --full`: List all entries including those starting with a dot `.`.

**cardlatexstudio** is a Qt6 application which can read and write .ctex files. These files contain settings and data necessary for **cardlatex** to generate a .tex file with.