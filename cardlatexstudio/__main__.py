import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt

import cardlatexstudio.__resources__
from .__version__ import __version__
from .window import MainWindow


if __name__ == '__main__':
    print(f'version: {__version__}')

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([])
    app.setOrganizationName('xgdragon')
    app.setApplicationName('tikzcardstudio')

    QFontDatabase.addApplicationFont(':/JetBrainsMonoNL-Regular')

    mw = MainWindow()
    mw.showNormal()

    sys.exit(app.exec())
