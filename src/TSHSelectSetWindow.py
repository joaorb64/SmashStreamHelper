import traceback
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from loguru import logger

from src.TSHTournamentDataProvider import TSHTournamentDataProvider


class TSHSelectSetWindow(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            QApplication.translate("app", "TSH_legacy_00253"))
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.proxyModel = QSortFilterProxyModel()
        self.proxyModel.setFilterKeyColumn(-1)
        self.proxyModel.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive)

        def filterList(text):
            self.proxyModel.setFilterFixedString(text)

        searchBar = QLineEdit()
        searchBar.setPlaceholderText("Filter...")
        layout.addWidget(searchBar)
        searchBar.textEdited.connect(filterList)

        options = QHBoxLayout()

        self.showFinished = QCheckBox(
            QApplication.translate("app", "TSH_legacy_00254"))
        options.addWidget(self.showFinished)
        self.showFinished.clicked.connect(lambda check: self.LoadSets())
        self.showCompletePairs = QCheckBox(
            QApplication.translate("app", "TSH_legacy_00255"))
        options.addWidget(self.showCompletePairs)
        self.showCompletePairs.clicked.connect(lambda check: self.LoadSets())

        layout.layout().addLayout(options)

        self.startggSetSelectionItemList = QTableView()
        self.startggSetSelectionItemList.doubleClicked.connect(
            lambda x: self.LoadSelectedSet())
        self.startggSetSelectionItemList.installEventFilter(self)
        layout.addWidget(self.startggSetSelectionItemList)
        self.startggSetSelectionItemList.setSortingEnabled(True)
        self.startggSetSelectionItemList.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.startggSetSelectionItemList.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.startggSetSelectionItemList.setModel(self.proxyModel)
        self.startggSetSelectionItemList.setColumnHidden(6, True)
        self.startggSetSelectionItemList.horizontalHeader(
        ).setSectionResizeMode(QHeaderView.Stretch)
        self.startggSetSelectionItemList.resizeColumnsToContents()

        btOk = QPushButton("OK")
        layout.addWidget(btOk)
        btOk.clicked.connect(
            lambda x: self.LoadSelectedSet()
        )

        self.labelStatus = QLabel()
        layout.addWidget(self.labelStatus)

        self.resize(1200, 500)

        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        TSHTournamentDataProvider.instance.signals.sets_data_updated.connect(
            self.SetsUpdated)

        self.model = QStandardItemModel()

    def eventFilter(self, obj, event):
        if obj is self.startggSetSelectionItemList and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.LoadSelectedSet()
        return super().eventFilter(obj, event)

    def LoadSets(self):
        self.proxyModel.setSourceModel(QStandardItemModel())
        TSHTournamentDataProvider.instance.LoadSets(
            showFinished=self.showFinished.isChecked())
        self.model.clear()
        self.labelStatus.setText(
            QApplication.translate("app", "TSH_legacy_00256"))

    def SetsUpdated(self, data):
        if data == None:
            return

        if data["progress"] >= data["totalPages"]:
            self.labelStatus.setText("")
        else:
            self.labelStatus.setText(
                f"Fetching sets...({data['progress']}/{data['totalPages']})")

        horizontal_labels = ["Stream", "Station",
                             "Wave", "Title", "Player 1", "Player 2"]
        horizontal_labels[0] = QApplication.translate("app", "TSH_legacy_00257")
        horizontal_labels[1] = QApplication.translate("app", "TSH_legacy_00258")
        horizontal_labels[2] = QApplication.translate("app", "TSH_legacy_00259")
        horizontal_labels[3] = QApplication.translate("app", "TSH_legacy_00260")
        horizontal_labels[4] = QApplication.translate(
            "app", "TSH_legacy_00213_{0}").format(1)
        horizontal_labels[5] = QApplication.translate(
            "app", "TSH_legacy_00213_{0}").format(2)
        self.model.setHorizontalHeaderLabels(horizontal_labels)

        sets = data["sets"]

        if sets is not None:
            for s in sets:
                dataItem = QStandardItem(str(s.get("id")))
                dataItem.setData(s, Qt.ItemDataRole.UserRole)

                if self.showCompletePairs.isChecked():
                    if s.get("p1_name") == "" or s.get("p2_name") == "":
                        continue
                player_names = [s.get("p1_name"), s.get("p2_name")]

                try:
                    # For doubles, use team name + entrants names
                    if len(s.get("entrants", [[]])[0]) > 1:
                        for t, team in enumerate(s.get("entrants")):
                            pnames = []
                            for p, player in enumerate(s.get("entrants")[t]):
                                pnames.append(player.get("gamerTag"))
                            player_names[t] += " "+QApplication.translate(
                                "punctuation", "(")+", ".join(pnames)+QApplication.translate("punctuation", ")")
                except Exception as e:
                    logger.error(traceback.format_exc())

                self.model.appendRow([
                    QStandardItem(s.get("stream", "")),
                    QStandardItem(str(s.get("station", "")) if s.get(
                        "station", "") != None else ""),
                    QStandardItem(s.get("tournament_phase", "")),
                    QStandardItem(s["round_name"]),
                    QStandardItem(player_names[0]),
                    QStandardItem(player_names[1]),
                    dataItem
                ])

        self.proxyModel.setSourceModel(self.model)
        self.startggSetSelectionItemList.setColumnHidden(6, True)
        self.startggSetSelectionItemList.resizeColumnsToContents()
        self.startggSetSelectionItemList.horizontalHeader(
        ).setSectionResizeMode(QHeaderView.Stretch)
        QApplication.processEvents()
        self.resize(self.width(), self.height())

    def LoadSelectedSet(self):
        row = 0

        if len(self.startggSetSelectionItemList.selectionModel().selectedRows()) > 0:
            row = self.startggSetSelectionItemList.selectionModel().selectedRows()[
                0].row()
        setId = self.startggSetSelectionItemList.model().index(
            row, 6).data(Qt.ItemDataRole.UserRole)
        self.close()

        if setId:
            setId["auto_update"] = "set"
            self.parent().signals.NewSetSelected.emit(setId)

        if TSHTournamentDataProvider.instance.setLoadingWorker:
            # If there was a previous set loading worker,
            # block its signals
            TSHTournamentDataProvider.instance.setLoadingWorker.cancel()
            TSHTournamentDataProvider.instance.setLoadingWorker.signals.blockSignals(
                True)
