import traceback
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from loguru import logger

from src.TSHTournamentDataProvider import TSHTournamentDataProvider


class TSHSelectStationWindow(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            QApplication.translate("app", "TSH_legacy_00278"))
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
        self.startggSetSelectionItemList.horizontalHeader(
        ).setSectionResizeMode(QHeaderView.Stretch)
        self.startggSetSelectionItemList.resizeColumnsToContents()

        btOk = QPushButton("OK")
        layout.addWidget(btOk)
        btOk.clicked.connect(
            lambda x: self.LoadSelectedSet()
        )

        self.resize(1200, 500)

        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        TSHTournamentDataProvider.instance.signals.get_stations_finished.connect(
            self.SetStations)

    def eventFilter(self, obj, event):
        if obj is self.startggSetSelectionItemList and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.LoadSelectedSet()
        return super().eventFilter(obj, event)

    def LoadStations(self):
        self.proxyModel.setSourceModel(QStandardItemModel())
        TSHTournamentDataProvider.instance.LoadStations()

    def SetStations(self, stations):
        logger.info("Got stations" + str(len(stations)))
        model = QStandardItemModel()
        horizontal_labels = ["Type", "Id", "Stream", "Identifier"]
        horizontal_labels[0] = QApplication.translate("app", "TSH_legacy_00279")
        horizontal_labels[1] = QApplication.translate("app", "TSH_legacy_00280")
        horizontal_labels[2] = QApplication.translate("app", "TSH_legacy_00257")
        horizontal_labels[3] = QApplication.translate("app", "TSH_legacy_00281")
        model.setHorizontalHeaderLabels(horizontal_labels)

        if stations is not None:
            for s in stations:
                model.appendRow([
                    QStandardItem(str(s.get("type", ""))),
                    QStandardItem(str(s.get("id", ""))),
                    QStandardItem(str(s.get("stream", ""))),
                    QStandardItem(str(s.get("identifier", "")))
                ])

                model.setData(
                    model.index(model.rowCount()-1, 0),
                    s, Qt.ItemDataRole.UserRole
                )

        self.proxyModel.setSourceModel(model)
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

        station = self.startggSetSelectionItemList.model().index(
            row, 0).data(Qt.ItemDataRole.UserRole)

        self.close()

        if station:
            self.parent().signals.StationSelected.emit(station)
