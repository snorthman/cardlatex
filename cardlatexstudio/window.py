import json
from pathlib import Path

from PySide6 import QtWidgets, QtCore


class MainWindow(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		# self.setCentralWidget(MainWidget())
		# self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
		# self.setMenuBar(self.main.menubar)
		# self.addToolBar(self.main.toolbar)
		#
		# fileNew.triggered.connect(self.onNew)
		# fileOpen.triggered.connect(self.onOpen)
		# fileSave.triggered.connect(self.onSave)
		# fileSaveAs.triggered.connect(self.onSaveAs)
		#
		self.settings = QtCore.QSettings()
		self.settings.clear()
		# if session := self.session:
		# 	self.loadFile(session)
		# else:
		# 	self.onNew()

	@property
	def session(self) -> Path:
		session = self.settings.value('session')
		return Path(session) if session else None

	@session.setter
	def session(self, value: Path | str):
		self.settings.setValue('session', Path(value.as_posix()))

	@property
	def main(self) -> QtWidgets.QWidget:
		return self.centralWidget()

	def fileDialog(self, mode: QtWidgets.QFileDialog.FileMode) -> Path:
		file = QtWidgets.QFileDialog()
		file.setNameFilter(f'{self.windowTitle()} data (*.tikz)')
		file.setFileMode(mode)
		if file.exec():
			return Path(file.selectedFiles()[0])

	def loadFile(self, file: Path):
		try:
			self.main.workspace.clearNodes()
			with open(file) as f:
				self.main.workspace.addNodes(*json.load(f))
			self.setWindowTitle(file.name)
			self.session = file
			self.main.clearUndoRedo()
		except Exception as e:
			print(str(e))

	def saveFile(self, file: Path):
		with open(file, 'w') as f:
			json.dump([snode.__dict__ for snode in self.main.workspace.serialize().values()], f, indent=2)

	def onOpen(self):
		if path := self.fileDialog(QtWidgets.QFileDialog.FileMode.ExistingFile):
			self.loadFile(path)

	def onSave(self):
		if session := self.session:
			self.saveFile(session)
		else:
			self.onSaveAs()

	def onSaveAs(self):
		if path := self.fileDialog(QtWidgets.QFileDialog.FileMode.AnyFile):
			self.saveFile(path.with_suffix('.tikz'))

	def onNew(self):
		self.setUpdatesEnabled(False)
		self.main.clearUndoRedo()
		self.main.workspace.setupDefaultWorkspace()
		self.main.clearUndoRedo()
		self.settings.setValue('session', None)
		self.setWindowTitle('untitled.tikz')
		self.setUpdatesEnabled(True)

