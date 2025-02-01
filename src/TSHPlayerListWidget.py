from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy import uic
import json
import traceback
from loguru import logger
from .TSHPlayerListSlotWidget import TSHPlayerListSlotWidget

from .TSHScoreboardPlayerWidget import TSHScoreboardPlayerWidget
from .Helpers.TSHCountryHelper import TSHCountryHelper
from .StateManager import StateManager
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerDB import TSHPlayerDB
from .TSHTournamentDataProvider import TSHTournamentDataProvider
from .TSHPlayerList import TSHPlayerList
from src.Helpers.TSHAltTextHelper import generate_top_n_alt_text, add_alt_text_tooltip_to_button
import textwrap


class TSHPlayerListWidgetSignals(QObject):
    UpdateData = Signal(object)


class TSHPlayerListWidget(QDockWidget):
    def __init__(self, *args, base="player_list"):
        StateManager.BlockSaving()
        super().__init__(*args)

        self.signals = TSHPlayerListWidgetSignals()

        self.playerList = TSHPlayerList(base=base)

        self.setWindowTitle(QApplication.translate("app", "TSH_legacy_00138"))
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

        row = QWidget()
        row.setLayout(QHBoxLayout())
        topOptions.layout().addWidget(row)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.slotNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00139")))
        col.layout().addWidget(self.slotNumber)
        self.slotNumber.valueChanged.connect(
            lambda val: self.playerList.SetSlotNumber(val))
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.playerPerTeam = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00140")))
        col.layout().addWidget(self.playerPerTeam)
        self.playerPerTeam.valueChanged.connect(
            self.playerList.SetPlayersPerTeam)
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.charNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00141")))
        col.layout().addWidget(self.charNumber)
        self.charNumber.valueChanged.connect(
            self.playerList.SetCharactersPerPlayer)
        row.layout().addWidget(col)

        row = QWidget()
        row.setLayout(QHBoxLayout())
        topOptions.layout().addWidget(row)

        self.loadFromStandingsBt = QPushButton(
            QApplication.translate("app", "TSH_legacy_00142"))
        self.loadFromStandingsBt.clicked.connect(self.LoadFromStandingsClicked)
        row.layout().addWidget(self.loadFromStandingsBt)

        self.generateAltTextButton = QPushButton(
            QApplication.translate("app", "TSH_legacy_00143"))
        self.generateAltTextButton = add_alt_text_tooltip_to_button(self.generateAltTextButton)
        self.generateAltTextButton.clicked.connect(self.AltTextWindow)
        row.layout().addWidget(self.generateAltTextButton)

        self.widget.layout().addWidget(self.playerList)

        self.slotWidgets = []

        StateManager.Set("player_list", {})

        self.playerPerTeam.setValue(1)
        self.charNumber.setValue(1)
        self.slotNumber.setValue(8)

        self.signals.UpdateData.connect(self.LoadFromStandings)
        StateManager.ReleaseSaving()

    def LoadFromStandingsClicked(self):
        TSHTournamentDataProvider.instance.GetStandings(
            self.slotNumber.value(), self.signals.UpdateData)

    def AltTextWindow(self):
        def copy_text():
            textbox.selectAll()
            textbox.copy()

        messagebox = QDialog()
        messagebox.setWindowTitle(QApplication.translate(
            "app", "TSH_legacy_00144"))
        vbox = QVBoxLayout()
        messagebox.setLayout(vbox)
        textbox = QTextEdit()
        text_data = generate_top_n_alt_text().strip("\n")
        textbox.setText(text_data)
        textbox.setReadOnly(True)
        vbox.layout().addWidget(textbox)

        hbox = QHBoxLayout()
        vbox.layout().addLayout(hbox)

        copyTextButton = QPushButton(
            QApplication.translate("app", "TSH_legacy_00145"))
        copyTextButton.clicked.connect(copy_text)
        hbox.layout().addWidget(copyTextButton)

        messagebox.exec()

    def LoadFromStandings(self, data):
        StateManager.BlockSaving()
        if data is not None and len(data) > 0:
            playerNumber = len(data[0].get("players"))
            self.playerList.SetPlayersPerTeam(playerNumber)

            for i, slot in enumerate(self.playerList.slotWidgets):
                try:
                    slot.SetTeamData(data[i])
                except:
                    slot.Clear()
                    logger.error(traceback.format_exc())
        StateManager.ReleaseSaving()
