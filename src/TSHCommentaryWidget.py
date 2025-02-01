from rlcompleter import Completer
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy import uic
from loguru import logger

from .TSHScoreboardPlayerWidget import TSHScoreboardPlayerWidget
from .Helpers.TSHBadWordFilter import TSHBadWordFilter
from .TSHPlayerDB import TSHPlayerDB
from .StateManager import StateManager


class TSHCommentaryWidget(QDockWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.setWindowTitle(QApplication.translate("app", "TSH_legacy_00161"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.widget.setLayout(QVBoxLayout())

        self.setFloating(True)
        self.setWindowFlags(Qt.WindowType.Window)

        topOptions = QWidget()
        topOptions.setLayout(QHBoxLayout())
        topOptions.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)

        self.widget.layout().addWidget(topOptions)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        topOptions.layout().addWidget(col)
        self.commentatorNumber = QSpinBox()
        row = QWidget()
        row.setLayout(QHBoxLayout())
        commsNumber = QLabel(QApplication.translate("app", "TSH_legacy_00232"))
        commsNumber.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        row.layout().addWidget(commsNumber)
        row.layout().addWidget(self.commentatorNumber)
        self.commentatorNumber.valueChanged.connect(
            lambda val: self.SetCommentatorNumber(val))
        
        characterNumber = QSpinBox()
        charNumber = QLabel(QApplication.translate("app", "TSH_legacy_00141"))
        charNumber.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        row.layout().addWidget(charNumber)
        row.layout().addWidget(characterNumber)
        characterNumber.valueChanged.connect(self.SetCharacterNumber)
        
        self.eyeBt = QToolButton()
        self.eyeBt.setIcon(QIcon('assets/icons/eye.svg'))
        self.eyeBt.setSizePolicy(
            QSizePolicy.Maximum, QSizePolicy.Fixed)
        col.layout().addWidget(self.eyeBt, Qt.AlignmentFlag.AlignRight)
        self.eyeBt.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu()
        self.eyeBt.setMenu(menu)

        menu.addSection("Players")

        self.elements = [
            ["Real Name", ["real_name", "real_nameLabel"]],
            ["Twitter", ["twitter", "twitterLabel"]],
            ["Location", ["locationLabel", "state", "country"]],
            ["Characters", ["characters"]],
            ["Pronouns", ["pronoun", "pronounLabel"]],
        ]
        self.elements[0][0] = QApplication.translate("app", "TSH_legacy_00217")
        self.elements[1][0] = QApplication.translate("app", "TSH_legacy_00218")
        self.elements[2][0] = QApplication.translate("app", "TSH_legacy_00219")
        self.elements[3][0] = QApplication.translate("app", "TSH_legacy_00220")
        self.elements[4][0] = QApplication.translate("app", "TSH_legacy_00221")
        for element in self.elements:
            action: QAction = self.eyeBt.menu().addAction(element[0])
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(
                lambda toggled, action=action, element=element: self.ToggleElements(action, element[1]))
        
        row.layout().addWidget(self.eyeBt)
        col.layout().addWidget(row)

        scrollArea = QScrollArea()
        scrollArea.setFrameShadow(QFrame.Shadow.Plain)
        scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        scrollArea.setWidgetResizable(True)

        self.widgetArea = QWidget()
        self.widgetArea.setLayout(QVBoxLayout())
        self.widgetArea.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Maximum)
        scrollArea.setWidget(self.widgetArea)

        self.widget.layout().addWidget(scrollArea)

        self.commentaryWidgets = []

        StateManager.Set("commentary", {})
        self.commentatorNumber.setValue(2)
        characterNumber.setValue(1)

    def SetCommentatorNumber(self, number):
        while len(self.commentaryWidgets) < number:
            comm = TSHScoreboardPlayerWidget(
                index=len(self.commentaryWidgets)+1,
                teamNumber=0,
                path=f'commentary.{len(self.commentaryWidgets)+1}',
                customName="Commentator"
            )

            comm.btMoveUp.clicked.connect(
                lambda x=None, index=len(self.commentaryWidgets): self.MoveUp(index))

            comm.btMoveDown.clicked.connect(
                lambda x=None, index=len(self.commentaryWidgets): self.MoveDown(index))

            self.commentaryWidgets.append(comm)
            self.widgetArea.layout().addWidget(comm)

        while len(self.commentaryWidgets) > number:
            comm = self.commentaryWidgets[-1]
            comm.setParent(None)
            self.commentaryWidgets.remove(comm)

        if StateManager.Get(f'commentary'):
            for k in list(StateManager.Get(f'commentary').keys()):
                if not k.isnumeric() or (k.isnumeric() and int(k) > number):
                    StateManager.Unset(f'commentary.{k}')

    def MoveUp(self, index):
        if index > 0:
            self.SwapComms(index, index-1)

    def MoveDown(self, index):
        if index < len(self.commentaryWidgets)-1:
            self.SwapComms(index, index+1)

    def SwapComms(self, index1, index2):
        self.commentaryWidgets[index1].SwapWith(self.commentaryWidgets[index2])

    def ToggleElements(self, action: QAction, elements):
        for pw in self.commentaryWidgets:
            for element in elements:
                pw.findChild(QWidget, element).setVisible(action.isChecked())
    
    def SetCharacterNumber(self, value):
        for pw in self.commentaryWidgets:
            pw.SetCharactersPerPlayer(value)