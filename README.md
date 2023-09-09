# cardlatex

**cardlatex** is a XeLaTeX wrapper which compiles TeX from specific templated `.tex` files. 

XML files contain the card data. XML templates can be generated from the source tex files. 
Both `.tex` and `.xml` must share the same file name.

## `.tex` Configuration

Configuration is defined in the `.tex` document. Example: `\cardlatex[bleed]{5mm}`. Defining the same variable more than once is an error.

- `width (length)`: `required` Width of the card.
- `height (length)`: `required` Height of the card.
- `bleed (length)`: `default = 0` Bleed margin of the card.
- `quality (number)`: `default = 100` Quality of `\includegraphics` images. Useful for testing. Must be between 1 and 100.
- `include (number)`: Compile only specific rows. If left undefined, all rows in the XML are compiled.
- `front (text)`: `required` Front template of the card.
- `back (text)`: Back template of the card. If left undefined, the front template is used for the back of the card.

## `cardlatex compile`

Compile `.tex`/`.xml` file pairs.

`cardlatex compile [<tex files>] [flags]`

### Options

- `-c, --combine`: Combine all output PDF files to one. Has no effect is compiling only one `.tex` file.
- `-p, --print <paper>`: Grid each row to fit on `<paper>`. See below for allowed `<paper>` values.
- `-q, --quality <number>`: Override `\cardlatex[quality]` configuration to be set to `<number>`.
- `-b, --bleed <length>`: Override `\cardlatex[bleed]` configuration to be set to `<length>`.

## `cardlatex xml`

Generate a base `.xml` file for the given `.tex` file. If the `.xml` file(s) already exist, the 

`cardlatex xml [<tex files>] [flags]`

### Options

- `-n, --only-new`: D


## Arguments

`.tex` files to compile. If multiple `.tex` files are used, a single `.pdf` file is provided which tries to optimally position all cards.

## Options

- `-x, --xml`: Generate a default XML file for each `.tex` file given as argument.
- `-f, --full`: List all entries including those starting with a dot `.`.

**cardlatexstudio** is a Qt6 application which can read and write .ctex files. These files contain settings and data necessary for **cardlatex** to generate a .tex file with.