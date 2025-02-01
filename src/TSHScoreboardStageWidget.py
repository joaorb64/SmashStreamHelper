import traceback
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy import uic
import json
import orjson
import requests
import textwrap

from src.Helpers.TSHLocaleHelper import TSHLocaleHelper
from src.TSHStageStrikeLogic import TSHStageStrikeLogic
from .Helpers.TSHDirHelper import TSHResolve
from .Helpers.TSHDictHelper import deep_get
from .StateManager import StateManager
from .TSHGameAssetManager import TSHGameAssetManager
import socket
from loguru import logger


class TSHScoreboardStageWidgetSignals(QObject):
    rulesets_changed = Signal()


class Ruleset():
    def __init__(self) -> None:
        self.name = ""
        self.neutralStages = []
        self.counterpickStages = []
        self.banByMaxGames = {}
        self.useDSR = False
        self.useMDSR = False
        self.banCount = 0
        self.strikeOrder = []
        self.videogame = ""
        self.errors = []


class TSHScoreboardStageWidget(QDockWidget):

    def __init__(self, *args):
        super().__init__(*args)

        self.setWindowTitle(QApplication.translate("app", "TSH_legacy_00146"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFloating(True)
        self.setWindowFlags(Qt.WindowType.Window)

        self.innerWidget = QWidget()
        self.setWidget(self.innerWidget)

        self.stageStrikeLogic = TSHStageStrikeLogic()

        self.signals = TSHScoreboardStageWidgetSignals()

        uic.loadUi(TSHResolve("src/layout/TSHScoreboardStage.ui"), self.innerWidget)

        self.userRulesets = []
        self.startggRulesets = []

        self.stagesModel = QStandardItemModel()
        self.neutralModel = QStandardItemModel()
        self.counterpickModel = QStandardItemModel()

        self.rulesetsBox = self.findChild(QComboBox, "rulesetSelect")
        self.rulesetsBox.activated.connect(self.LoadRuleset)

        self.stagesView = self.findChild(QListView, "allStages")
        self.stagesView.setIconSize(QSize(64, 64))

        self.stagesNeutral = self.findChild(QListView, "neutralStages")
        self.stagesNeutral.setIconSize(QSize(64, 64))

        self.stagesCounterpick = self.findChild(QListView, "counterpickStages")
        self.stagesCounterpick.setIconSize(QSize(64, 64))

        self.rulesetName = self.findChild(QLineEdit, "rulesetName")
        self.rulesetName.textEdited.connect(self.ExportCurrentRuleset)

        self.btAddNeutral = self.findChild(QPushButton, "btAddNeutral")
        self.btAddNeutral.clicked.connect(
            lambda x=None, view=self.stagesNeutral: self.AddStage(view))
        self.btAddNeutral.setIcon(QIcon("./assets/icons/arrow_right.svg"))

        self.btRemoveNeutral = self.findChild(QPushButton, "btRemoveNeutral")
        self.btRemoveNeutral.clicked.connect(
            lambda: self.RemoveStage(self.stagesNeutral))
        self.btRemoveNeutral.setIcon(QIcon("./assets/icons/arrow_left.svg"))

        self.btAddCounterpick = self.findChild(QPushButton, "btAddCounterpick")
        self.btAddCounterpick.clicked.connect(
            lambda x=None, view=self.stagesCounterpick: self.AddStage(view))
        self.btAddCounterpick.setIcon(QIcon("./assets/icons/arrow_right.svg"))

        self.btRemoveCounterpick = self.findChild(
            QPushButton, "btRemoveCounterpick")
        self.btRemoveCounterpick.clicked.connect(
            lambda: self.RemoveStage(self.stagesCounterpick))
        self.btRemoveCounterpick.setIcon(
            QIcon("./assets/icons/arrow_left.svg"))

        self.noDSR = self.findChild(QRadioButton, "noDSR")
        self.noDSR.clicked.connect(self.ExportCurrentRuleset)
        self.noDSR.setToolTip('\n'.join(textwrap.wrap(QApplication.translate("app", "no_dsr_tooltip"), 40)))
        self.DSR = self.findChild(QRadioButton, "DSR")
        self.DSR.clicked.connect(self.ExportCurrentRuleset)
        self.DSR.setToolTip('\n'.join(textwrap.wrap(QApplication.translate("app", "dsr_tooltip"), 40)))
        self.MDSR = self.findChild(QRadioButton, "MDSR")
        self.MDSR.clicked.connect(self.ExportCurrentRuleset)
        self.MDSR.setToolTip('\n'.join(textwrap.wrap(QApplication.translate("app", "mdsr_tooltip"), 40)))

        self.strikeOrder = self.findChild(QLineEdit, "strikeOrder")
        self.strikeOrder.textEdited.connect(self.ExportCurrentRuleset)

        self.fixedBanCount = self.findChild(QRadioButton, "fixedBanCount")
        self.fixedBanCount.clicked.connect(self.ExportCurrentRuleset)
        self.variableBanCount = self.findChild(
            QRadioButton, "variableBanCount")
        self.variableBanCount.clicked.connect(self.ExportCurrentRuleset)

        self.banCount = self.findChild(QSpinBox, "banCount")
        self.banCount.valueChanged.connect(self.ExportCurrentRuleset)

        self.banCountByMaxGames = self.findChild(
            QLineEdit, "banCountByMaxGames")
        self.banCountByMaxGames.textEdited.connect(self.ExportCurrentRuleset)

        self.webappLabel = self.findChild(QLabel, "labelIp")
        self.webappLabel.setText(
            QApplication.translate("app", "TSH_legacy_00147_{0}").format(f"<a href='http://{self.GetIP()}:5000'>http://{self.GetIP()}:5000</a>"))
        self.webappLabel.setOpenExternalLinks(True)

        self.labelValidation = self.findChild(QLabel, "labelValidation")
        self.labelValidation.setText("")

        self.signals.rulesets_changed.connect(self.LoadRulesets)
        self.LoadStartggRulesets()
        self.LoadRuleset()

        TSHGameAssetManager.instance.signals.onLoad.connect(self.SetupOptions)

        StateManager.Set(f"score.ruleset", None)
        self.ExportCurrentRuleset()

        self.btSave = self.findChild(QPushButton, "btSave")
        self.btSave.setIcon(QIcon('assets/icons/save.svg'))
        self.btDelete = self.findChild(QPushButton, "btDelete")
        self.btDelete.setIcon(QIcon('assets/icons/cancel.svg'))
        self.btClear = self.findChild(QPushButton, "btClear")
        self.btClear.setIcon(QIcon('assets/icons/undo.svg'))

        self.rulesetName.textChanged.connect(self.UpdateBottomButtons)
        self.btSave.clicked.connect(self.SaveRuleset)
        self.btDelete.clicked.connect(self.DeleteRuleset)
        self.btClear.clicked.connect(self.ClearRuleset)

        self.stagesModel.dataChanged.connect(
            lambda topLeft, bottomRight: self.update_cloned_items())

        # TSHTournamentDataProvider.instance.signals.tournament_changed.connect()
        # load tournament ruleset

    def update_cloned_items(self):
        neutralStages = []

        for rowNeutral in range(self.neutralModel.rowCount()):
            neutralItem = self.neutralModel.item(rowNeutral)

            for rowAll in range(self.stagesModel.rowCount()):
                stageItem = self.stagesModel.item(rowAll)

                if neutralItem.data(Qt.ItemDataRole.UserRole).get("codename") == stageItem.data(Qt.ItemDataRole.UserRole).get("codename"):
                    neutralStages.append(stageItem)

        self.neutralModel.clear()

        for s in neutralStages:
            self.neutralModel.appendRow(s.clone())

        counterpickStages = []

        for rowNeutral in range(self.counterpickModel.rowCount()):
            neutralItem = self.counterpickModel.item(rowNeutral)

            for rowAll in range(self.stagesModel.rowCount()):
                stageItem = self.stagesModel.item(rowAll)

                if neutralItem.data(Qt.ItemDataRole.UserRole).get("codename") == stageItem.data(Qt.ItemDataRole.UserRole).get("codename"):
                    counterpickStages.append(stageItem)

        self.counterpickModel.clear()

        for s in counterpickStages:
            self.counterpickModel.appendRow(s.clone())

    def GetIP(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def AddStage(self, view: QListView):
        selected = self.stagesView.selectedIndexes()

        if len(selected) == 1:
            data = selected[0].data(Qt.ItemDataRole.UserRole)

            for i in range(self.stagesNeutral.model().rowCount()):
                if self.stagesNeutral.model().item(i, 0).data(Qt.ItemDataRole.UserRole).get("codename") == data.get("codename"):
                    return

            for i in range(self.stagesCounterpick.model().rowCount()):
                if self.stagesCounterpick.model().item(i, 0).data(Qt.ItemDataRole.UserRole).get("codename") == data.get("codename"):
                    return

            item = self.stagesView.model().itemFromIndex(selected[0]).clone()
            view.model().appendRow(item)
            view.model().sort(0)
            self.ExportCurrentRuleset()

    def RemoveStage(self, view: QListView):
        selected = view.selectedIndexes()

        if len(selected) == 1:
            view.model().removeRow(selected[0].row())
            self.ExportCurrentRuleset()

    def UpdateBottomButtons(self):
        found = next((
            ruleset for ruleset in self.userRulesets if ruleset.get(
                "videogame") == TSHGameAssetManager.instance.selectedGame.get(
                    "codename") and ruleset.get("name") == self.rulesetName.text()), None)

        if found:
            self.btSave.setText(QApplication.translate("app", "TSH_legacy_00148"))
            self.btDelete.setEnabled(True)
        else:
            self.btSave.setText(QApplication.translate("app", "TSH_legacy_00149"))
            self.btDelete.setEnabled(False)

    def SaveRuleset(self):
        found = next((
            ruleset for ruleset in self.userRulesets if ruleset.get(
                "videogame") == TSHGameAssetManager.instance.selectedGame.get(
                    "codename") and ruleset.get("name") == self.rulesetName.text()), None)

        if found:
            self.userRulesets.remove(found)

        self.userRulesets.append(vars(self.GetCurrentRuleset(True)))

        self.SaveRulesetsFile()

    def DeleteRuleset(self):
        found = next((
            ruleset for ruleset in self.userRulesets if ruleset.get(
                "videogame") == TSHGameAssetManager.instance.selectedGame.get(
                    "codename") and ruleset.get("name") == self.rulesetName.text()), None)

        if found:
            self.userRulesets.remove(found)
            self.SaveRulesetsFile()

    def ClearRuleset(self):
        self.LoadRuleset()

    def SaveRulesetsFile(self):
        try:
            with open("./user_data/rulesets.json", 'w', encoding="utf-8") as outfile:
                json.dump(self.userRulesets, outfile, indent=4, sort_keys=True)
        except FileNotFoundError:
            logger.debug("./user_data/rulesets.json not found")
        except Exception as e:
            logger.error(traceback.format_exc())

        self.LoadRulesets()
        self.UpdateBottomButtons()

    def SetupOptions(self):
        self.rulesetsBox.clear()

        self.ClearRuleset()
        self.LoadRulesets()

        self.stagesModel = TSHGameAssetManager.instance.stageModel
        self.stagesModel.dataChanged.connect(
            lambda topLeft, bottomRight: self.update_cloned_items())
        self.stagesModel.sort(0)
        self.stagesView.setModel(self.stagesModel)

    def LoadRulesets(self):
        rulesetsModel = QStandardItemModel()

        rulesetsModel.appendRow(QStandardItem(""))

        # Load local rulesets
        try:
            self.userRulesets = orjson.loads(
                open("./user_data/rulesets.json", encoding="utf-8").read())

            for ruleset in self.userRulesets:
                if ruleset.get("videogame") == TSHGameAssetManager.instance.selectedGame.get("codename"):
                    myRuleset = Ruleset()
                    myRuleset.__dict__.update(ruleset)

                    neutral = []
                    for neutralStage in myRuleset.neutralStages:
                        stage = TSHGameAssetManager.instance.selectedGame.get(
                            "stage_to_codename").get(neutralStage, {})
                        neutral.append(stage)
                    myRuleset.neutralStages = neutral

                    counterpick = []
                    for counterpickStage in myRuleset.counterpickStages:
                        stage = TSHGameAssetManager.instance.selectedGame.get(
                            "stage_to_codename").get(counterpickStage, {})
                        counterpick.append(stage)
                    myRuleset.counterpickStages = counterpick

                    item = QStandardItem(ruleset.get("name"))
                    item.setData(myRuleset, Qt.ItemDataRole.UserRole)
                    item.setIcon(QIcon("./assets/icons/db.svg"))
                    rulesetsModel.appendRow(item)
        except FileNotFoundError:
            logger.warning("./user_data/rulesets.json not found, skipping import")
            self.userRulesets = []
        except:
            self.userRulesets = []
            logger.error(traceback.format_exc())

        # Load startgg rulesets
        for ruleset in self.startggRulesets:
            myRuleset = Ruleset()
            if str(ruleset.get("videogameId")) == str(TSHGameAssetManager.instance.selectedGame.get("smashgg_game_id")):
                if not ruleset.get("settings"):
                    ruleset["settings"] = {}
                if not ruleset.get("settings").get("stages"):
                    ruleset["settings"]["stages"] = {}
                if ruleset.get("settings") and ruleset.get("settings", {}).get("stages", {}).get("neutral"):
                    neutral = []
                    for stage in ruleset["settings"]["stages"]["neutral"]:
                        stage = next((s[1] for s in TSHGameAssetManager.instance.selectedGame.get(
                            "stage_to_codename").items() if str(s[1].get("smashgg_id")) == str(stage)), {"smashgg_id": stage})
                        neutral.append(stage)
                    myRuleset.neutralStages = neutral
                if ruleset.get("settings") and ruleset.get("settings", {}).get("stages", {}).get("counterpick"):
                    counterpick = []
                    for stage in ruleset["settings"]["stages"]["counterpick"]:
                        stage = next((s[1] for s in TSHGameAssetManager.instance.selectedGame.get(
                            "stage_to_codename").items() if str(s[1].get("smashgg_id")) == str(stage)), {"smashgg_id": stage})
                        counterpick.append(stage)
                    myRuleset.counterpickStages = counterpick
                myRuleset.name = ruleset.get("name")

                myRuleset.strikeOrder = ruleset.get(
                    "settings", {}).get("strikeOrder")

                if deep_get(ruleset, "settings.additionalFlags") and isinstance(deep_get(ruleset, "settings.additionalFlags"), dict):
                    myRuleset.useDSR = ruleset.get("settings", {}).get(
                        "additionalFlags", {}).get("useDSR", False)
                    myRuleset.useMDSR = ruleset.get("settings", {}).get(
                        "additionalFlags", {}).get("useMDSR", False)

                    myRuleset.banCount = ruleset.get("settings", {}).get(
                        "additionalFlags", {}).get("banCount", 0)

                    myRuleset.banByMaxGames = ruleset.get("settings", {}).get(
                        "additionalFlags", {}).get("banCountByMaxGames", 0)

                item = QStandardItem(ruleset.get("name"))
                item.setData(myRuleset, Qt.ItemDataRole.UserRole)
                item.setIcon(QIcon("./assets/icons/startgg.svg"))
                rulesetsModel.appendRow(item)

        # Update list
        self.rulesetsBox.setModel(rulesetsModel)

    def FindStageInModel(self, codename: str):
        for row in range(self.stagesModel.rowCount()):
            item = self.stagesModel.item(row)
            if item.data(Qt.ItemDataRole.UserRole).get("codename") == codename:
                return item

    def LoadRuleset(self):
        data = self.rulesetsBox.currentData()

        if data == None:
            data = Ruleset()

        self.rulesetName.setText(data.name)

        if data.useDSR:
            self.DSR.setChecked(True)
        elif data.useMDSR:
            self.MDSR.setChecked(True)
        else:
            self.noDSR.setChecked(True)

        if data.strikeOrder:
            self.strikeOrder.setText(
                ",".join([str(s) for s in data.strikeOrder]))

        if data.banCount:
            self.fixedBanCount.setChecked(True)
            self.banCount.setValue(data.banCount)
            self.banCountByMaxGames.setText("")
        elif data.banByMaxGames:
            self.variableBanCount.setChecked(True)
            self.banCountByMaxGames.setText(
                ",".join([f'{k}:{v}' for k, v in data.banByMaxGames.items()]))
            self.banCount.setValue(0)

        self.neutralModel = QStandardItemModel()
        if data.neutralStages:
            for stage in data.neutralStages:
                item = self.FindStageInModel(stage.get("codename"))
                self.neutralModel.appendRow(item.clone())
        self.stagesNeutral.setModel(self.neutralModel)

        self.counterpickModel = QStandardItemModel()
        if data.counterpickStages:
            for stage in data.counterpickStages:
                item = self.FindStageInModel(stage.get("codename"))
                self.counterpickModel.appendRow(item.clone())
        self.stagesCounterpick.setModel(self.counterpickModel)

        self.ExportCurrentRuleset()

    def ExportCurrentRuleset(self):
        try:
            ruleset = self.GetCurrentRuleset()
            self.stageStrikeLogic.SetRuleset(ruleset)
            self.ValidateRuleset(ruleset)
            StateManager.Set(f"score.ruleset", vars(ruleset))
        except:
            logger.error(traceback.format_exc())

    def ValidateRuleset(self, ruleset: Ruleset):
        issues = []

        # Validate bans
        if len(ruleset.neutralStages) > 0:
            if sum(ruleset.strikeOrder) != len(ruleset.neutralStages) - 1:
                remaining = (len(ruleset.neutralStages) - 1) - \
                    sum(ruleset.strikeOrder)
                issues.append(QApplication.translate(
                    "app", "TSH_legacy_00150_{0}").format(remaining))

        # Add errors
        for error in ruleset.errors:
            issues.append(error)

        if len(issues) == 0:
            validText = QApplication.translate(
                "app", "TSH_legacy_00151")
            self.labelValidation.setText(
                f"<span style='color: green'>{validText}</span>")
        else:
            issuesText = "\n".join(issues)
            self.labelValidation.setText(
                f'<span style="color: red">{issuesText}</span>')

    def GetCurrentRuleset(self, forSaving=False):
        ruleset = Ruleset()

        ruleset.videogame = TSHGameAssetManager.instance.selectedGame.get(
            "codename")
        ruleset.name = self.rulesetName.text()

        ruleset.neutralStages = []
        for i in range(self.stagesNeutral.model().rowCount()):
            if not forSaving:
                ruleset.neutralStages.append(self.stagesNeutral.model().item(
                    i, 0).data(Qt.ItemDataRole.UserRole))
            else:
                ruleset.neutralStages.append(self.stagesNeutral.model().item(
                    i, 0).data(Qt.ItemDataRole.UserRole).get("en_name"))

        ruleset.counterpickStages = []
        for i in range(self.stagesCounterpick.model().rowCount()):
            if not forSaving:
                ruleset.counterpickStages.append(self.stagesCounterpick.model().item(
                    i, 0).data(Qt.ItemDataRole.UserRole))
            else:
                ruleset.counterpickStages.append(self.stagesCounterpick.model().item(
                    i, 0).data(Qt.ItemDataRole.UserRole).get("en_name"))

        ruleset.useDSR = self.DSR.isChecked()
        ruleset.useMDSR = self.MDSR.isChecked()

        if self.fixedBanCount.isChecked():
            ruleset.banCount = self.banCount.value()

        if self.variableBanCount.isChecked():
            try:
                inputText: str = self.banCountByMaxGames.text()
                ruleset.banByMaxGames = {}

                for _set in inputText.split(","):
                    split = _set.split(":")

                    if len(split) == 2:
                        key, value = split
                        ruleset.banByMaxGames[key.strip()] = int(value.strip())
            except:
                ruleset.banByMaxGames = {}
                ruleset.errors.append(QApplication.translate(
                    "app", "TSH_legacy_00152"))
                logger.error(traceback.format_exc())

        ruleset.strikeOrder = [
            int(n.strip()) for n in (self.strikeOrder.text().split(",") if self.strikeOrder.text() != "" else "1,2,1".split(",")) if n.strip() != ""
        ]

        return ruleset

    def QueryRequests(self, url=None, type=None, headers=None, jsonParams=None, params=None):
        requestCode = 0
        data = None
        while requestCode != 200:
            data = type(
                url,
                headers=headers,
                json=jsonParams,
                params=params
            )
            requestCode = data.status_code
        return orjson.loads(data.text)

    def LoadStartggRulesets(self):
        try:
            class DownloadThread(QThread):
                query = self.QueryRequests
                def run(self):
                        data = self.query(
                            "https://www.start.gg/api/-/gg_api./rulesets",
                            type=requests.get
                        )
                        rulesets = deep_get(data, "entities.ruleset")
                        open('./assets/rulesets.json',
                             'wb').write(orjson.dumps(rulesets, option=orjson.OPT_INDENT_2))
                        self.parent().startggRulesets = rulesets
                        logger.info("startgg Rulesets downloaded from startgg")
                        self.parent().signals.rulesets_changed.emit()
            downloadThread = DownloadThread(self)
            downloadThread.start()
        except Exception as e:
            logger.error(traceback.format_exc())

        # https://www.start.gg/api/-/gg_api./rulesets
        # entities > ruleset[]

        # description: null
        # eventSettings: null
        # expand: []
        # gameMode: 1
        # id: 172
        # isDefault: false
        # name: "Community CUP"
        # settings: {gameSetup: true, stages: {neutral: [311, 328, 397, 378, 387], counterpick: [497, 484, 407, 348]},…}
        # type: "standard"
        # videogameId: 1386

        # "additionalFlags":{"banCountByMaxGames":{"3":3,"5":2},"useDSR":true}
        # "additionalFlags":{"banCount":2,"useDSR":true}
        # "additionalFlags":{"useMDSR":true,"banCount":1}

        # settings -> stages -> "strikeOrder":[1,2,1]
        # "strikeOrder":[1,1,1]
