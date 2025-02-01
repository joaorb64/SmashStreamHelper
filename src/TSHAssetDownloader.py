import traceback
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *

from src.TSHGameAssetManager import TSHGameAssetManager
from src.Workers import Worker

import requests
import shutil
import py7zr
import urllib
import orjson
import os
from loguru import logger


class IconDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.decorationSize = option.rect.size()


class TSHAssetDownloaderSignals(QObject):
    AssetUpdates = Signal(dict)


class TSHAssetDownloader(QObject):
    instance: "TSHAssetDownloader" = None

    def __init__(self) -> None:
        super().__init__()
        self.threadpool = QThreadPool()
        self.signals = TSHAssetDownloaderSignals()

    def UiMounted(self):
        self.iconUpdateAvailable = QIcon('assets/icons/update_available.svg')
        self.iconInstalled = QIcon('assets/icons/installed.svg')

    def CheckAssetUpdates(self, game_codename=None):
        class AssetUpdatesThread(QThread):
            def run(self):
                try:
                    assets = TSHAssetDownloader.instance.DownloadAssetsFetch()

                    updates = {}

                    for game_code, game in assets.items():
                        for asset_code, asset in game["assets"].items():
                            currVersion = str(TSHGameAssetManager.instance.games.get(game_code, {}).get(
                                "assets", {}).get(asset_code, {}).get("version", ""))

                            version = str(assets[game_code]["assets"]
                                          [asset_code].get("version"))

                            if currVersion != version and currVersion != "":
                                if not game_code in updates:
                                    updates[game_code] = []
                                updates[game_code].append(
                                    assets[game_code]["assets"][asset_code])

                    TSHAssetDownloader.instance.signals.AssetUpdates.emit(
                        updates)
                except:
                    logger.error(traceback.format_exc())

        thread = AssetUpdatesThread(self)
        thread.start()

    def DownloadAssets(self):
        assets = self.DownloadAssetsFetch()

        if assets is None:
            return

        self.preDownloadDialogue = QDialog()
        self.preDownloadDialogue.setWindowTitle(
            QApplication.translate("app", "TSH_legacy_00166"))
        self.preDownloadDialogue.setWindowModality(
            Qt.WindowModality.ApplicationModal)
        self.preDownloadDialogue.setLayout(QVBoxLayout())
        self.preDownloadDialogue.resize(1400, 500)
        self.preDownloadDialogue.show()

        self.select = QComboBox()
        selectProxy = QSortFilterProxyModel()
        selectProxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        selectProxy.setSourceModel(self.select.model())
        self.select.model().setParent(selectProxy)
        selectProxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.select.setModel(selectProxy)
        self.select.setEditable(True)
        self.select.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.select.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.font_small = QFont(
            "./assets/font/RobotoCondensed.ttf", pointSize=8)
        self.select.setFont(self.font_small)
        self.select.setModel(QStandardItemModel())
        self.preDownloadDialogue.layout().addWidget(self.select)

        self.select.setIconSize(QSize(64, 64))
        self.select.setFixedHeight(32)
        view = QListView()
        view.setIconSize(QSize(64, 64))
        view.setStyleSheet("QListView::item { height: 32px; }")
        self.select.setView(view)

        model = QStandardItemModel()

        proxyModel = QSortFilterProxyModel()
        proxyModel.setSourceModel(model)
        proxyModel.setFilterKeyColumn(-1)
        proxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        def filterList(text):
            proxyModel.setFilterFixedString(text)

        searchBar = QLineEdit()
        searchBar.setPlaceholderText("Filter...")
        self.preDownloadDialogue.layout().addWidget(searchBar)
        searchBar.textEdited.connect(filterList)

        downloadList = QTableView()
        self.preDownloadDialogue.layout().addWidget(downloadList)
        downloadList.setSortingEnabled(True)
        downloadList.setSelectionBehavior(QAbstractItemView.SelectRows)
        downloadList.setEditTriggers(QAbstractItemView.NoEditTriggers)
        downloadList.setModel(proxyModel)
        downloadList.verticalHeader().hide()
        downloadList.horizontalHeader().setStretchLastSection(True)
        downloadList.setWordWrap(True)
        downloadList.resizeColumnsToContents()
        downloadList.resizeRowsToContents()
        delegate = IconDelegate(downloadList)
        downloadList.setItemDelegate(delegate)

        for i, game in enumerate(assets):
            self.select.addItem(
                QIcon(), assets[game]["name"], i)

            worker = Worker(self.DownloadGameIcon, *[game], i)
            worker.signals.result.connect(self.DownloadGameIconComplete)
            self.threadpool.start(worker)

        self.select.model().sort(0)

        def ReloadGameAssets(index=None):
            nonlocal self

            index = self.select.currentData()

            if index == None:
                index = self.select.currentIndex()

            model.clear()
            header_labels = [
                "game",
                "asset_id",
                "State",
                "Asset pack name",
                "Installed version",
                "Latest version",
                "Size",
                "Stage data",
                "Eyesight data",
                "Description",
                "Credits"
            ]

            header_labels[2] = QApplication.translate("app", "TSH_legacy_00239")
            header_labels[3] = QApplication.translate(
                "app", "TSH_legacy_00240")
            header_labels[4] = QApplication.translate(
                "app", "TSH_legacy_00241")
            header_labels[5] = QApplication.translate("app", "TSH_legacy_00242")
            header_labels[6] = QApplication.translate("app", "TSH_legacy_00243")
            header_labels[7] = QApplication.translate("app", "TSH_legacy_00244")
            header_labels[8] = QApplication.translate("app", "TSH_legacy_00245")
            header_labels[9] = QApplication.translate("app", "TSH_legacy_00246")
            header_labels[10] = QApplication.translate("app", "TSH_legacy_00247")

            model.setHorizontalHeaderLabels(header_labels)
            downloadList.hideColumn(0)
            downloadList.hideColumn(1)
            downloadList.horizontalHeader().setStretchLastSection(True)
            downloadList.setWordWrap(True)
            downloadList.resizeColumnsToContents()
            downloadList.resizeRowsToContents()
            downloadList.setStyleSheet(
                "QTableView::item { padding: 6px 0px; }")

            key = list(assets.keys())[index]

            hasBaseFiles = TSHGameAssetManager.instance.games.get(
                key, {}).get("assets", {}).get("base_files", None) != None

            sortedKeys = list(assets[key]["assets"].keys())
            sortedKeys.sort(
                key=lambda x: chr(0) if x == "base_files" else x)

            for asset in sortedKeys:
                dlSize = "{:.2f}".format(sum(
                    [f.get("size", 0) for f in list(
                        assets[key]["assets"][asset]["files"].values())]
                )/1024/1024) + " MB"

                currVersion = str(TSHGameAssetManager.instance.games.get(key, {}).get(
                    "assets", {}).get(asset, {}).get("version", ""))

                version = str(assets[key]["assets"][asset].get("version"))

                items = [
                    QStandardItem(key),
                    QStandardItem(asset),
                    QStandardItem(),
                    QStandardItem(assets[key]["assets"][asset].get("name")),
                    QStandardItem(currVersion),
                    QStandardItem(version),
                    QStandardItem(dlSize),
                    QStandardItem(),
                    QStandardItem(),
                    QStandardItem(assets[key]["assets"]
                                  [asset].get("description")),
                    QStandardItem(assets[key]["assets"][asset].get("credits"))
                ]

                items[2].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[3].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[4].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[5].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[6].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[7].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                items[8].setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if assets[key]["assets"][asset].get("has_stage_data", False):
                    items[7].setData(self.iconInstalled.pixmap(
                        24, 24), Qt.ItemDataRole.DecorationRole)

                if assets[key]["assets"][asset].get("has_eyesight_data", False):
                    items[8].setData(self.iconInstalled.pixmap(
                        24, 24), Qt.ItemDataRole.DecorationRole)

                model.appendRow(items)

                if not hasBaseFiles and asset != "base_files":
                    for col in range(model.columnCount()):
                        item = model.item(model.rowCount()-1, col)
                        item.setEnabled(False)
                        item.setSelectable(False)

                if currVersion == version:
                    for col in range(model.columnCount()):
                        items[2].setData(self.iconInstalled.pixmap(
                            24, 24), Qt.ItemDataRole.DecorationRole)
                if currVersion != version and currVersion != "":
                    for col in range(model.columnCount()):
                        items[2].setData(self.iconUpdateAvailable.pixmap(
                            24, 24), Qt.ItemDataRole.DecorationRole)

            downloadList.horizontalHeader().setStretchLastSection(True)
            # downloadList.resizeColumnsToContents()
            downloadList.resizeRowsToContents()
            downloadList.setColumnWidth(2, 60)
            downloadList.setColumnWidth(3, 200)
            downloadList.setColumnWidth(4, 120)
            downloadList.setColumnWidth(5, 120)
            downloadList.setColumnWidth(6, 120)
            downloadList.setColumnWidth(7, 120)
            downloadList.setColumnWidth(8, 120)
            downloadList.setColumnWidth(9, 400)

        self.reloadDownloadsList = ReloadGameAssets
        self.select.activated.connect(ReloadGameAssets)
        ReloadGameAssets(0)

        TSHGameAssetManager.instance.signals.onLoadAssets.connect(
            ReloadGameAssets)

        btOk = QPushButton(QApplication.translate("app", "TSH_legacy_00248"))
        self.preDownloadDialogue.layout().addWidget(btOk)

        btUpdateAll = QPushButton(QApplication.translate("app", "TSH_legacy_00249"))
        self.preDownloadDialogue.layout().addWidget(btUpdateAll)

        btUpdateAll.clicked.connect(TSHAssetDownloader.UpdateAllAssets)

        def DownloadStart():
            nonlocal self

            if len(downloadList.selectionModel().selectedRows()) == 0:
                return

            row = downloadList.selectionModel().selectedRows()[0].row()
            game = downloadList.model().index(row, 0).data()
            key = downloadList.model().index(row, 1).data()

            filesToDownload = assets[game]["assets"][key]["files"]

            for f in filesToDownload:
                filesToDownload[f]["path"] = "https://github.com/joaorb64/StreamHelperAssets/releases/latest/download/" + \
                    filesToDownload[f]["name"]
                filesToDownload[f]["extractpath"] = "./user_data/games/"+game

            self.downloadDialogue = QProgressDialog(
                QApplication.translate("app", "TSH_legacy_00250"),
                QApplication.translate("app", "TSH_legacy_00203"),
                0,
                100
            )
            self.downloadDialogue.setMinimumWidth(1200)
            self.downloadDialogue.setWindowModality(
                Qt.WindowModality.WindowModal)
            self.downloadDialogue.show()
            worker = Worker(self.DownloadAssetsWorker, *
                            [[list(filesToDownload.values())]])
            worker.signals.progress.connect(self.DownloadAssetsProgress)
            worker.signals.finished.connect(self.DownloadAssetsFinished)
            self.threadpool.start(worker)

        btOk.clicked.connect(DownloadStart)

    def DownloadAssetsFetch(self):
        assets = None
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/assets.json")
            assets = orjson.loads(response.text)
        except Exception as e:
            messagebox = QMessageBox()
            messagebox.setText(QApplication.translate(
                "app", "TSH_legacy_00251")+"\n"+str(e))
            messagebox.exec()
        return assets

    def DownloadGameIcon(self, game_code, index, progress_callback, cancel_event):
        try:
            # Try getting logo_small
            response = urllib.request.urlopen(
                f"https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/games/{game_code}/base_files/logo_small.png")
            data = response.read()
            return ([index, data])
        except Exception as e1:
            logger.error(traceback.format_exc())
            try:
                # Try getting logo
                response = urllib.request.urlopen(
                    f"https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/games/{game_code}/base_files/logo.png")
                data = response.read()
                return ([index, data])
            except Exception as e2:
                # All options failed
                logger.error(traceback.format_exc())
                return (None)

    def DownloadGameIconComplete(self, result):
        try:
            if result is not None:
                pix = QPixmap()
                pix.loadFromData(result[1], "png")
                pix = pix.scaledToWidth(
                    64, Qt.TransformationMode.SmoothTransformation)
                for i in range(self.select.model().rowCount()):
                    if self.select.model().index(i, 0).data(Qt.ItemDataRole.UserRole) == result[0]:
                        self.select.setItemIcon(i, QIcon(pix))
        except Exception as e:
            logger.error(traceback.format_exc())
            return (None)

    def DownloadAssetsWorker(self, files, progress_callback, cancel_event):
        totalSize = sum(sum(f["size"] for f in fileList) for fileList in files)
        downloaded = 0

        logger.info("Files to download:" + str(files))

        for i, fileList in enumerate(files):
            for f in fileList:
                with open("user_data/games/"+f["name"], 'wb') as downloadFile:
                    logger.info("Downloading "+f["name"])
                    progress_callback.emit(QApplication.translate(
                        "app", "TSH_legacy_00252_{0}_{1}_{2}").format(f["name"], i+1, len(files)))

                    response = urllib.request.urlopen(f["path"])

                    while (True):
                        chunk = response.read(1024*1024)

                        if not chunk:
                            break

                        downloaded += len(chunk)
                        downloadFile.write(chunk)

                        if self.downloadDialogue.wasCanceled():
                            return

                        progress_callback.emit(
                            min(int(downloaded/totalSize*100), 99))
                    downloadFile.close()

                    logger.info("Download OK")

            is7z = ".7z" in fileList[0]["name"]

            if len(fileList) > 0:
                # append in binary mode
                with open('./user_data/games/merged.7z', 'ab') as outfile:
                    for f in fileList:
                        # open in binary mode also
                        with open("./user_data/games/"+f["name"], 'rb') as infile:
                            outfile.write(infile.read())
                for f in fileList:
                    os.remove("./user_data/games/"+f["name"])

                fileList = [fileList[0]]
                fileList[0]["name"] = "merged.7z"

            if is7z:
                with py7zr.SevenZipFile("./user_data/games/"+fileList[0]["name"], 'r') as parent_zip:
                    parent_zip.extractall(f["extractpath"])

                for f in fileList:
                    os.remove("./user_data/games/"+f["name"])
            else:
                for f in files:
                    if os.path.isfile(f["extractpath"]+"/"+f["name"]):
                        os.remove(f["extractpath"]+"/"+f["name"])
                    shutil.move("./user_data/games/" +
                                f["name"], f["extractpath"])

            logger.info("Extract OK")

        progress_callback.emit(100)

        logger.info("All OK")

    def DownloadAssetsProgress(self, n):
        if type(n) == int:
            self.downloadDialogue.setValue(n)

            if n == 100:
                self.downloadDialogue.setMaximum(0)
                self.downloadDialogue.setValue(0)
                self.downloadDialogue.close()
        else:
            self.downloadDialogue.setLabelText(n)

    def DownloadAssetsFinished(self):
        self.downloadDialogue.close()
        TSHGameAssetManager.instance.LoadGames()
        TSHAssetDownloader.instance.CheckAssetUpdates()

    def UpdateAllAssets(self):
        def f(assets):
            TSHAssetDownloader.instance.signals.AssetUpdates.disconnect(f)

            allFilesToDownload = []

            for game, _assets in assets.items():
                for asset in _assets:
                    filesToDownload = list(asset["files"].values())
                    for fileToDownload in filesToDownload:
                        fileToDownload["path"] = f'https://github.com/joaorb64/StreamHelperAssets/releases/latest/download/{fileToDownload["name"]}'
                        fileToDownload["extractpath"] = f'./user_data/games/{game}'
                    allFilesToDownload.append(filesToDownload)

            TSHAssetDownloader.instance.downloadDialogue = QProgressDialog(
                QApplication.translate("app", "TSH_legacy_00250"),
                QApplication.translate("app", "TSH_legacy_00203"),
                0,
                100
            )
            TSHAssetDownloader.instance.downloadDialogue.setMinimumWidth(1200)
            TSHAssetDownloader.instance.downloadDialogue.setWindowModality(
                Qt.WindowModality.WindowModal)
            TSHAssetDownloader.instance.downloadDialogue.show()
            worker = Worker(
                TSHAssetDownloader.instance.DownloadAssetsWorker, *[allFilesToDownload])
            worker.signals.progress.connect(
                TSHAssetDownloader.instance.DownloadAssetsProgress)
            worker.signals.finished.connect(
                TSHAssetDownloader.instance.DownloadAssetsFinished)
            TSHAssetDownloader.instance.threadpool.start(worker)

        TSHAssetDownloader.instance.signals.AssetUpdates.connect(f)
        TSHAssetDownloader.instance.CheckAssetUpdates()


TSHAssetDownloader.instance = TSHAssetDownloader()
