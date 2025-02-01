from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy import uic
import json
from .Helpers.TSHCountryHelper import TSHCountryHelper
from .Helpers.TSHDirHelper import TSHResolve
from .StateManager import StateManager
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerDB import TSHPlayerDB
from .TSHTournamentDataProvider import TSHTournamentDataProvider
from .TSHPlayerListSlotWidget import TSHPlayerListSlotWidget
from .TSHBracketView import TSHBracketView
from .TSHPlayerList import TSHPlayerList
from .TSHBracket import *
import traceback
from loguru import logger

# Checks if a number is power of 2


def is_power_of_two(n):
    return (n != 0) and (n & (n-1) == 0)


class TSHBracketWidgetSignals(QObject):
    UpdateData = Signal(object)


class TSHBracketWidget(QDockWidget):
    instance: "TSHBracketWidget" = None
    def __init__(self, *args):
        StateManager.BlockSaving()
        super().__init__(*args)

        uic.loadUi(TSHResolve("src/layout/TSHBracket.ui"), self)

        StateManager.Set("bracket", {})

        TSHTournamentDataProvider.instance.signals.tournament_phases_updated.connect(
            self.UpdatePhases)
        TSHTournamentDataProvider.instance.signals.tournament_phasegroup_updated.connect(
            self.UpdatePhaseGroup)

        self.signals = TSHBracketWidgetSignals()

        self.bracket = Bracket(8, 0)

        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self.mainLayout = self.findChild(QWidget, "bracket")
        self.mainLayout.setLayout(QVBoxLayout())

        self.setFloating(True)
        self.setWindowFlags(Qt.WindowType.Window)

        outerLayout: QWidget = self.findChild(QWidget, "bracket")
        self.playerList = TSHPlayerList(base="bracket.players")

        list: QWidget = self.findChild(QWidget, "listContainer")

        # Add player list settings on the top
        row = QWidget()
        row.setLayout(QHBoxLayout())
        list.layout().addWidget(row)

        col = QWidget()
        col.setLayout(QVBoxLayout())

        self.slotNumber = QSpinBox()
        self.slotNumber.setMinimum(2)
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00139")))
        col.layout().addWidget(self.slotNumber)
        self.slotNumber.valueChanged.connect(lambda val: [
            self.playerList.SetSlotNumber(val),
            self.RebuildBracket(val),
        ])
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.playerPerTeam = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00140")))
        col.layout().addWidget(self.playerPerTeam)
        self.playerPerTeam.valueChanged.connect(
            lambda val: self.playerList.SetPlayersPerTeam(val))
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.charNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "TSH_legacy_00141")))
        col.layout().addWidget(self.charNumber)
        self.charNumber.valueChanged.connect(
            self.playerList.SetCharactersPerPlayer)
        row.layout().addWidget(col)

        list.layout().addWidget(self.playerList)

        self.bracketView = TSHBracketView(self.bracket, self.playerList, self)
        outerLayout.layout().addWidget(self.bracketView)

        self.phaseSelection: QComboBox = self.findChild(
            QComboBox, "phaseSelection")
        self.phaseSelection.currentIndexChanged.connect(self.UpdatePhaseGroups)

        self.phaseGroupSelection: QComboBox = self.findChild(
            QComboBox, "phaseGroupSelection")
        self.phaseGroupSelection.currentIndexChanged.connect(
            self.PhaseGroupChanged)

        self.btRefreshPhase: QPushButton = self.findChild(
            QPushButton, "btRefreshPhase")
        updateIcon = QImage("./assets/icons/undo.svg").scaled(24, 24)
        self.btRefreshPhase.setIcon(QIcon(QPixmap.fromImage(updateIcon)))
        self.btRefreshPhase.clicked.connect(lambda: [
            TSHTournamentDataProvider.instance.GetTournamentPhases()
        ])

        self.btRefreshPhaseGroup: QPushButton = self.findChild(
            QPushButton, "btRefreshPhaseGroup")
        updateIcon = QImage("./assets/icons/undo.svg").scaled(24, 24)
        self.btRefreshPhaseGroup.setIcon(QIcon(QPixmap.fromImage(updateIcon)))
        self.btRefreshPhaseGroup.clicked.connect(self.PhaseGroupChanged)

        self.progressionsIn: QSpinBox = self.findChild(
            QSpinBox, "progressionsIn")
        self.progressionsIn.valueChanged.connect(lambda val: [
            self.bracketView.SetBracket(
                self.bracket,
                progressionsIn=self.progressionsIn.value(),
                progressionsOut=self.progressionsOut.value(),
                winnersOnlyProgressions=self.winnersOnly.isChecked(),
                customSeeding=self.bracket.customSeeding
            ),
            self.bracketView.Update()
        ])
        StateManager.Set("bracket.bracket.progressionsIn", 0)

        self.winnersOnly: QCheckBox = self.findChild(QCheckBox, "winnersOnly")
        self.winnersOnly.toggled.connect(lambda newVal: [
            self.bracketView.SetBracket(
                self.bracket,
                progressionsIn=self.progressionsIn.value(),
                progressionsOut=self.progressionsOut.value(),
                winnersOnlyProgressions=self.winnersOnly.isChecked(),
                customSeeding=self.bracket.customSeeding
            ),
            self.bracketView.Update()
        ])
        StateManager.Set("bracket.bracket.winnersOnly", True)

        self.progressionsOut: QSpinBox = self.findChild(
            QSpinBox, "progressionsOut")
        self.progressionsOut.valueChanged.connect(lambda val: [
            self.bracketView.SetBracket(
                self.bracket,
                progressionsIn=self.progressionsIn.value(),
                progressionsOut=self.progressionsOut.value(),
                winnersOnlyProgressions=self.winnersOnly.isChecked(),
                customSeeding=self.bracket.customSeeding
            ),
            self.bracketView.Update()
        ])
        StateManager.Set("bracket.bracket.progressionsOut", 0)

        self.limitExport: QCheckBox = self.findChild(QCheckBox, "limitExport")
        self.limitExport.stateChanged.connect(lambda newVal: [
            self.bracketView.SetBracket(
                self.bracket,
                progressionsIn=self.progressionsIn.value(),
                progressionsOut=self.progressionsOut.value(),
                winnersOnlyProgressions=self.winnersOnly.isChecked(),
                customSeeding=self.bracket.customSeeding
            ),
            self.bracketView.Update()
        ])

        self.limitExportNumber: QSpinBox = self.findChild(
            QSpinBox, "limitExportNumber")
        self.limitExportNumber.valueChanged.connect(lambda val: [
            self.bracketView.SetBracket(
                self.bracket,
                progressionsIn=self.progressionsIn.value(),
                progressionsOut=self.progressionsOut.value(),
                winnersOnlyProgressions=self.winnersOnly.isChecked(),
                customSeeding=self.bracket.customSeeding
            ),
            self.bracketView.Update()
        ])

        self.playerList.signals.DataChanged.connect(self.bracketView.Update)

        self.slotNumber.setValue(8)
        self.playerPerTeam.setValue(1)
        self.charNumber.setValue(1)

        self.splitter = self.findChild(QSplitter, "splitter")
        self.splitter.setSizes([1, 1])

        self.bracketView.Update()

        StateManager.ReleaseSaving()
        
        TSHBracketWidget.instance = self

    def UpdatePhases(self, phases):
        logger.info("Phases: " + str(phases))
        self.phaseSelection.clear()
        self.phaseSelection.addItem("", {})

        for phase in phases:
            self.phaseSelection.addItem(phase.get("name"), phase)

    def UpdatePhaseGroups(self):
        try:
            selectedGroup = self.phaseSelection.currentData()
            StateManager.Set("bracket.phase", selectedGroup.get("name", ""))
        except:
            StateManager.Set("bracket.phase", "")

        self.phaseGroupSelection.clear()

        if self.phaseSelection.currentData() != None:
            logger.info(
                str(self.phaseSelection.currentData().get("groups", [])))
            for phaseGroup in self.phaseSelection.currentData().get("groups", []):
                self.phaseGroupSelection.addItem(
                    phaseGroup.get("name"), phaseGroup)

                # Let's only allow double elimination for now
                if phaseGroup.get("bracketType") != "DOUBLE_ELIMINATION":
                    itemModel: QStandardItemModel = self.phaseGroupSelection.model()
                    item = itemModel.item(itemModel.rowCount()-1)
                    item.setEnabled(False)

    def PhaseGroupChanged(self):
        try:
            # Do not export phaseGroup name if there's only one phaseGroup
            if len(self.phaseSelection.currentData().get("groups", [])) > 1:
                selectedGroup = self.phaseGroupSelection.currentData()
                StateManager.Set("bracket.phaseGroup",
                                 selectedGroup.get("name"))
            else:
                StateManager.Set("bracket.phaseGroup", "")
        except:
            StateManager.Set("bracket.phaseGroup", "")

        if self.phaseGroupSelection.currentData() != None:
            TSHTournamentDataProvider.instance.GetTournamentPhaseGroup(
                self.phaseGroupSelection.currentData().get("id"))

    def RebuildBracket(self, playerNumber, seedMap=None, customSeeding=False):
        self.bracket = Bracket(playerNumber, self.progressionsIn.value(
        ), seedMap, self.winnersOnly.isChecked(), progressionsOut=self.progressionsOut.value())

        self.bracketView.SetBracket(
            self.bracket,
            progressionsIn=self.progressionsIn.value(),
            progressionsOut=self.progressionsOut.value(),
            winnersOnlyProgressions=self.winnersOnly.isChecked(),
            customSeeding=customSeeding
        )

        if self.progressionsIn.value() > 0:
            for _set in self.bracket.rounds["1"]:
                _set.score[0] = -1
                _set.score[1] = -1
                _set.finished = False

    def UpdatePhaseGroup(self, phaseGroupData):
        StateManager.BlockSaving()
        self.playerList.signals.DataChanged.disconnect()

        try:
            logger.info("Phase Group Data: " + str(phaseGroupData))

            if phaseGroupData.get("progressionsIn", {}) != None:
                self.progressionsIn.setValue(
                    len(phaseGroupData.get("progressionsIn", {})))
            else:
                self.progressionsIn.setValue(0)

            if phaseGroupData.get("progressionsOut", {}) != None:
                self.progressionsOut.setValue(
                    len(phaseGroupData.get("progressionsOut", {})))
            else:
                self.progressionsOut.setValue(0)

            if phaseGroupData.get("winnersOnlyProgressions", False) != None:
                self.winnersOnly.setChecked(
                    phaseGroupData.get("winnersOnlyProgressions", False))
            else:
                self.winnersOnly.setChecked(False)

            self.bracket.customSeeding = phaseGroupData.get(
                "customSeeding", False)

            # Make sure progressions are exported
            QGuiApplication.processEvents()

            self.playerList.LoadFromStandings(phaseGroupData.get("entrants"))

            # Wait for the player list to update
            QGuiApplication.processEvents()

            self.slotNumber.blockSignals(True)
            self.slotNumber.setValue(len(self.playerList.slotWidgets))
            self.slotNumber.blockSignals(False)

            self.playerPerTeam.blockSignals(True)
            self.playerPerTeam.setValue(self.playerList.playersPerTeam)
            self.playerPerTeam.blockSignals(False)

            self.RebuildBracket(
                len(phaseGroupData.get("entrants")),
                phaseGroupData.get("seedMap"),
                phaseGroupData.get("customSeeding", False)
            )

            for r, round in phaseGroupData.get("sets", {}).items():
                for s, _set in enumerate(round):
                    try:
                        score = _set.get("score")
                        if score[0] == None:
                            score[0] = 0
                        if score[1] == None:
                            score[1] = 0

                        roundIndex = str(r)

                        self.bracket.rounds[roundIndex][s].score = score
                        self.bracket.rounds[roundIndex][s].finished = _set.get(
                            "finished")
                    except Exception as e:
                        logger.error(traceback.format_exc())

            QGuiApplication.processEvents()
            self.bracket.UpdateBracket()
            self.bracketView.Update()
        except:
            logger.error(traceback.format_exc())
        finally:
            StateManager.ReleaseSaving()
            self.playerList.signals.DataChanged.connect(
                self.bracketView.Update)
