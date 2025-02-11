import os
import json
import orjson
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from .StateManager import StateManager
import re
import traceback
import threading
from .Helpers.TSHLocaleHelper import TSHLocaleHelper
from .Workers import Worker
from PIL import Image
from loguru import logger

import requests


class TSHGameAssetManagerSignals(QObject):
    onLoad = Signal()
    onLoadAssets = Signal()


class TSHGameAssetManager(QObject):
    instance: "TSHGameAssetManager" = None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.signals = TSHGameAssetManagerSignals()
        self.games = {}
        self.characters = {}
        self.variants = {}
        self.selectedGame = {}
        self.stockIcons = {}
        self.startgg_id_to_character = {}

        self.characterModel = QStandardItemModel()
        self.skinModels = {}
        self.variantModel = QStandardItemModel()
        self.stageModel = QStandardItemModel()

        StateManager.Set(f"game", {})
        self.assetsLoaderLock = QMutex()
        self.assetsLoaderThread = None
        self.thumbnailSettingsLoaded = False
        self.threadpool = QThreadPool()
        self.workers = []

        self.skinLoaderLock = QMutex()

    def UiMounted(self):
        self.DownloadStartGGCharacters()
        self.LoadGames()

    def DownloadStartGGCharacters(self):
        class DownloaderThread(QThread):
            def run(self):
                try:
                    url = 'https://api.start.gg/characters'
                    r = requests.get(url, allow_redirects=True)
                    r_json = orjson.dumps(orjson.loads(
                        r.text), option=orjson.OPT_INDENT_2)

                    open('./assets/characters.json.tmp', 'wb').write(r_json)

                    try:
                        # Test if downloaded JSON is valid
                        json.load(open('./assets/characters.json.tmp'))

                        # Remove old file, overwrite with new one
                        os.remove('./assets/characters.json')
                        os.rename(
                            './assets/characters.json.tmp',
                            './assets/characters.json'
                        )

                        logger.info("startgg characters file updated")
                    except:
                        logger.error("Characters file download failed")
                except Exception as e:
                    logger.error(
                        "Could not update /assets/characters.json: "+str(e))
        thread = DownloaderThread(self)
        thread.start()

    def LoadGames(self):
        class GameLoaderThread(QThread):
            def run(self):
                self.parent().games = {}

                gameDirs = os.listdir("./user_data/games/")

                for game in gameDirs:
                    if os.path.isfile("./user_data/games/"+game+"/base_files/config.json"):
                        with open("./user_data/games/"+game +
                                  "/base_files/config.json", "rb") as f:
                            self.parent().games[game] = orjson.loads(f.read())

                        # Try logo_small, if it doesn't exist use logo
                        if os.path.isfile("./user_data/games/"+game+"/base_files/logo_small.png"):
                            self.parent().games[game]["logo"] = QIcon(
                                QPixmap(
                                    QImage("./user_data/games/"+game+"/base_files/logo_small.png").scaled(
                                        64,
                                        64,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation
                                    )
                                )
                            )
                        elif os.path.isfile("./user_data/games/"+game+"/base_files/logo.png"):
                            self.parent().games[game]["logo"] = QIcon(
                                QPixmap(
                                    QImage("./user_data/games/"+game+"/base_files/logo.png").scaled(
                                        64,
                                        64,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation
                                    )
                                )
                            )

                        self.parent().games[game]["assets"] = {}
                        self.parent(
                        ).games[game]["path"] = "./user_data/games/"+game+"/"

                        assetDirs = os.listdir("./user_data/games/"+game)
                        assetDirs += ["base_files/" +
                                      f for f in os.listdir("./user_data/games/"+game+"/base_files/")]

                        for dir in assetDirs:
                            if os.path.isdir("./user_data/games/"+game+"/"+dir):
                                if os.path.isfile("./user_data/games/"+game+"/"+dir+"/config.json"):
                                    logger.info(
                                        "Found asset config for ["+game+"]["+dir+"]")
                                    with open("./user_data/games/"+game+"/"+dir +
                                              "/config.json", "rb") as f:
                                        self.parent().games[game]["assets"][dir] = \
                                            orjson.loads(f.read())
                                else:
                                    logger.error(
                                        "No config file for "+game+" - "+dir)

                        # Load translated names
                        # Translate game name
                        locale = TSHLocaleHelper.programLocale
                        if locale.replace('-', '_') in self.parent().games[game].get("locale", {}):
                            game_name = self.parent(
                            ).games[game]["locale"][locale.replace('-', '_')].get("name")
                            if game_name:
                                self.parent(
                                ).games[game]["name"] = game_name
                        elif locale.split('-')[0] in self.parent().games[game].get("locale", {}):
                            game_name = self.parent(
                            ).games[game]["locale"][locale.split('-')[0]].get("name")
                            if game_name:
                                self.parent(
                                ).games[game]["name"] = game_name
                    else:
                        logger.info("Game config for "+game+" doesn't exist.")
                # print(self.parent().games)
                self.parent().signals.onLoadAssets.emit()

        gameLoaderThread = GameLoaderThread(self)
        gameLoaderThread.start()

    def SetGameFromStartGGId(self, gameid):
        def detect_smashgg_id_match(game, id):
            result = str(game.get("smashgg_game_id", "")) == str(id)
            if not result:
                alternates = game.get("alternate_versions", [])
                alternates_ids = []
                for alternate in alternates:
                    if alternate.get("smashgg_game_id"):
                        alternates_ids.append(
                            str(alternate.get("smashgg_game_id")))
                result = str(id) in alternates_ids
            return (result)

        if len(self.games.keys()) == 0:
            return

        for i, game in enumerate(self.games.values()):
            if detect_smashgg_id_match(game, gameid):
                self.LoadGameAssets(i+1)
                break

    def SetGameFromChallongeId(self, gameid):
        def detect_challonge_id_match(game, id):
            result = str(game.get("challonge_game_id", "")) == str(id)
            if not result:
                alternates = game.get("alternate_versions", [])
                alternates_ids = []
                for alternate in alternates:
                    if alternate.get("challonge_game_id"):
                        alternates_ids.append(
                            str(alternate.get("challonge_game_id")))
                result = str(id) in alternates_ids
            return (result)

        if len(self.games.keys()) == 0:
            return

        for i, game in enumerate(self.games.values()):
            if detect_challonge_id_match(game, gameid):
                self.LoadGameAssets(i+1)
                break

    def LoadGameAssets(self, game: int = 0):
        class AssetsLoaderThread(QThread):
            def __init__(self, parent=...) -> None:
                super().__init__(parent)
                self.game = None
                self.lock = None

            def run(self):
                self.lock.lock()
                try:
                    game = self.game

                    if len(self.parent().games.keys()) == 0:
                        return

                    if game == 0 or game == None:
                        game = ""
                    else:
                        game = list(self.parent().games.keys())[game-1]

                    # Game is already loaded
                    if game == self.parent().selectedGame.get("codename"):
                        self.parent().threadpool.waitForDone()
                        return

                    logger.info("Changed to game: "+game)

                    gameObj = self.parent().games.get(game, {})
                    self.parent().selectedGame = gameObj
                    gameObj["codename"] = game

                    if gameObj != None:
                        self.parent().characters = gameObj.get("character_to_codename", {})
                        self.parent().variants = gameObj.get("variant_to_codename", {})

                        assetsKey = ""
                        if len(list(gameObj.get("assets", {}).keys())) > 0:
                            assetsKey = list(gameObj.get(
                                "assets", {}).keys())[0]

                        for asset in list(gameObj.get("assets", {}).keys()):
                            if "icon" in gameObj["assets"][asset].get("type", ""):
                                assetsKey = asset
                                break

                        assetsObj = gameObj.get(
                            "assets", {}).get(assetsKey, None)
                        files = sorted(os.listdir(
                            './user_data/games/'+game+'/'+assetsKey))

                        self.parent().stockIcons = {}

                        for c in self.parent().characters.keys():
                            self.parent().stockIcons[c] = {}

                            filteredFiles = \
                                [f for f in files if f.startswith(assetsObj.get(
                                    "prefix", "")+self.parent().characters[c].get("codename")+assetsObj.get("postfix", ""))]

                            if len(filteredFiles) == 0:
                                self.parent().stockIcons[c][0] = QImage(
                                    './assets/icons/cancel.svg')

                            for i, f in enumerate(filteredFiles):
                                numberStart = f.rfind(
                                    assetsObj.get("postfix", "")) + len(assetsObj.get("postfix", ""))
                                numberEnd = f.rfind(".")
                                number = 0
                                try:
                                    number = int(f[numberStart:numberEnd])
                                except:
                                    logger.error(f)
                                    pass
                                try:
                                    self.parent().stockIcons[c][number] = QImage(
                                        './user_data/games/'+game+'/'+assetsKey+'/'+f).scaledToWidth(
                                            32,
                                            Qt.TransformationMode.SmoothTransformation
                                    )
                                except:
                                    logger.error(traceback.format_exc())

                        logger.info("Loaded stock icons")

                        self.parent().skins = {}

                        packSkinMask = {}

                        widths = {}
                        heights = {}

                        for c in self.parent().characters.keys():
                            self.parent().skins[c] = {}
                            for assetsKey in list(gameObj["assets"].keys()):
                                asset = gameObj["assets"][assetsKey]

                                files = sorted(os.listdir(
                                    './user_data/games/'+game+'/'+assetsKey))

                                filteredFiles = \
                                    [f for f in files if f.startswith(asset.get(
                                        "prefix", "")+self.parent().characters[c].get("codename")+asset.get("postfix", ""))]

                                for f in filteredFiles:
                                    numberStart = f.rfind(
                                        asset.get("postfix", "")) + len(asset.get("postfix", ""))
                                    numberEnd = f.rfind(".")
                                    number = 0
                                    try:
                                        number = int(f[numberStart:numberEnd])
                                    except:
                                        pass
                                    self.parent().skins[c][number] = True

                                    if c not in packSkinMask:
                                        packSkinMask[c] = {}

                                    if assetsKey not in packSkinMask[c]:
                                        packSkinMask[c][assetsKey] = set()

                                    packSkinMask[c][assetsKey].add(number)

                            logger.info("Character "+c+" has " +
                                        str(len(self.parent().skins[c]))+" skins")

                        # Set average size
                        for assetsKey in list(gameObj.get("assets", {}).keys()):
                            if assetsKey != "base_files" and assetsKey not in ["stage_icon", "variant_icon"]:
                                try:
                                    if len(widths.get(assetsKey, [])) > 0 and len(heights.get(assetsKey, [])) > 0:
                                        gameObj["assets"][assetsKey]["average_size"] = assetsObj.get("average_size")
                                except:
                                    logger.error(traceback.format_exc())

                        # Set complete
                        for assetsKey in list(gameObj.get("assets", {}).keys()):
                            try:
                                complete = True

                                for c in self.parent().characters.keys():
                                    if "random" in c.lower():
                                        continue
                                    for skin in self.parent().skins[c].keys():
                                        if assetsKey not in packSkinMask[c] or skin not in packSkinMask[c][assetsKey]:
                                            complete = False
                                            break

                                gameObj["assets"][assetsKey]["complete"] = complete
                            except:
                                logger.error(traceback.format_exc())

                        # Get biggest complete pack
                        assetsKey = "base_files/icon"
                        biggestAverage = 0

                        for asset in list(gameObj.get("assets", {}).keys()):
                            if gameObj["assets"][asset].get("complete") and gameObj["assets"][asset].get("average_size") and asset not in ["stage_icon", "variant_icon"]:
                                size = sum(gameObj["assets"][asset].get(
                                    "average_size").values())

                                if size > biggestAverage:
                                    assetsKey = asset
                                    biggestAverage = size

                        self.parent().biggestCompletePack = assetsKey
                        logger.info("Biggest complete assets: " + assetsKey)

                        # Get stage icon
                        assetsKey = None

                        for asset in list(gameObj.get("assets", {}).keys()):
                            if "stage_icon" in gameObj["assets"][asset].get("type", ""):
                                assetsKey = asset
                                break

                        self.parent().stages = gameObj.get("stage_to_codename", {})

                        if assetsKey:
                            assetsObj = gameObj.get(
                                "assets", {}).get(assetsKey)
                            files = sorted(os.listdir(
                                './user_data/games/'+game+'/'+assetsKey))

                            for stage in self.parent().stages:
                                self.parent().stages[stage]["path"] = './user_data/games/'+game+'/'+assetsKey+'/'+assetsObj.get(
                                    "prefix", "")+self.parent().stages[stage].get("codename", "")+assetsObj.get("postfix", "")+".png"

                        for s in self.parent().stages.keys():
                            self.parent().stages[s]["name"] = s

                        # Load translations
                        try:
                            for c in self.parent().characters.keys():
                                display_name = c
                                export_name = c
                                en_name = c

                                if self.parent().characters[c].get("locale"):
                                    locale = TSHLocaleHelper.programLocale
                                    if locale.replace("-", "_") in self.parent().characters[c]["locale"]:
                                        display_name = self.parent().characters[
                                            c]["locale"][locale.replace("-", "_")]
                                    elif re.split("-|_", locale)[0] in self.parent().characters[c]["locale"]:
                                        display_name = self.parent().characters[
                                            c]["locale"][re.split("-|_", locale)[0]]
                                    elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.programLocale) in self.parent().characters[c]["locale"]:
                                        display_name = self.parent().characters[c]["locale"][TSHLocaleHelper.GetRemaps(
                                            TSHLocaleHelper.programLocale)]

                                    locale = TSHLocaleHelper.exportLocale
                                    if locale.replace("-", "_") in self.parent().characters[c]["locale"]:
                                        export_name = self.parent().characters[
                                            c]["locale"][locale.replace("-", "_")]
                                    elif re.split("-|_", locale)[0] in self.parent().characters[c]["locale"]:
                                        export_name = self.parent().characters[
                                            c]["locale"][re.split("-|_", locale)[0]]
                                    elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.exportLocale) in self.parent().characters[c]["locale"]:
                                        export_name = self.parent().characters[c]["locale"][TSHLocaleHelper.GetRemaps(
                                            TSHLocaleHelper.exportLocale)]

                                self.parent(
                                ).characters[c]["display_name"] = display_name
                                self.parent(
                                ).characters[c]["export_name"] = export_name
                                self.parent(
                                ).characters[c]["en_name"] = en_name
                        except:
                            logger.error(traceback.format_exc())

                        
                        # Load translations for variants
                        try:
                            for c in self.parent().variants.keys():
                                display_name = c
                                export_name = c
                                en_name = c

                                if self.parent().variants[c].get("locale"):
                                    locale = TSHLocaleHelper.programLocale
                                    if locale.replace("-", "_") in self.parent().variants[c]["locale"]:
                                        display_name = self.parent().variants[
                                            c]["locale"][locale.replace("-", "_")]
                                    elif re.split("-|_", locale)[0] in self.parent().variants[c]["locale"]:
                                        display_name = self.parent().variants[
                                            c]["locale"][re.split("-|_", locale)[0]]
                                    elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.programLocale) in self.parent().variants[c]["locale"]:
                                        display_name = self.parent().variants[c]["locale"][TSHLocaleHelper.GetRemaps(
                                            TSHLocaleHelper.programLocale)]

                                    locale = TSHLocaleHelper.exportLocale
                                    if locale.replace("-", "_") in self.parent().variants[c]["locale"]:
                                        export_name = self.parent().variants[
                                            c]["locale"][locale.replace("-", "_")]
                                    elif re.split("-|_", locale)[0] in self.parent().variants[c]["locale"]:
                                        export_name = self.parent().variants[
                                            c]["locale"][re.split("-|_", locale)[0]]
                                    elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.exportLocale) in self.parent().variants[c]["locale"]:
                                        export_name = self.parent().variants[c]["locale"][TSHLocaleHelper.GetRemaps(
                                            TSHLocaleHelper.exportLocale)]

                                self.parent(
                                ).variants[c]["display_name"] = display_name
                                self.parent(
                                ).variants[c]["export_name"] = export_name
                                self.parent(
                                ).variants[c]["en_name"] = en_name
                        except:
                            logger.error(traceback.format_exc())

                    StateManager.Set(f"game", {
                        "name": self.parent().selectedGame.get("name"),
                        "smashgg_id": self.parent().selectedGame.get("smashgg_game_id"),
                        "codename": self.parent().selectedGame.get("codename"),
                        "logo": self.parent().selectedGame.get("path", "")+"/base_files/logo.png",
                    })

                    self.parent().UpdateCharacterModel()
                    self.parent().UpdateSkinModel()
                    self.parent().UpdateVariantModel()
                    self.parent().UpdateStageModel()
                    self.parent().signals.onLoad.emit()
                except:
                    logger.error(traceback.format_exc())
                finally:
                    self.parent().threadpool.waitForDone()
                    self.lock.unlock()

        self.thumbnailSettingsLoaded = False
        self.assetsLoaderThread = AssetsLoaderThread(
            TSHGameAssetManager.instance)
        self.assetsLoaderThread.game = game
        self.assetsLoaderThread.lock = self.assetsLoaderLock
        self.assetsLoaderThread.start(QThread.Priority.HighestPriority)

        # Setup startgg character id to character name
        sggcharacters = orjson.loads(
            open('./assets/characters.json', 'rb').read())
        self.startgg_id_to_character = {}

        for c in sggcharacters.get("entities", {}).get("character", []):
            self.startgg_id_to_character[str(c.get("id"))] = c

        # self.programState["asset_path"] = self.selectedGame.get("path")
        # self.programState["game"] = game

        # self.SetupAutocomplete()

        # if self.settings.get("autosave") == True:
        #    self.ExportProgramState()

        # self.gameSelect.clear()

        # self.gameSelect.addItem("")

        # for game in self.games:
        #    self.gameSelect.addItem(self.games[game]["name"])

    def UpdateStageModel(self):
        try:
            self.stageModel = QStandardItemModel()

            for stage in self.selectedGame.get("stage_to_codename", {}).items():
                # Load stage name translations
                stage[1]["en_name"] = stage[1].get("name")

                # Display name
                display_name = stage[1].get("name")

                locale = TSHLocaleHelper.programLocale
                if locale.replace('-', '_') in stage[1].get("locale", {}):
                    display_name = stage[1].get("locale", {})[
                        locale.replace('-', '_')]
                elif locale.split('-')[0] in stage[1].get("locale", {}):
                    display_name = stage[1].get("locale", {})[
                        locale.split('-')[0]]
                elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.programLocale) in stage[1].get("locale", {}):
                    display_name = stage[1].get("locale", {})[
                        TSHLocaleHelper.GetRemaps(TSHLocaleHelper.programLocale)]

                stage[1]["display_name"] = display_name

                # Export name
                export_name = stage[1].get("name")

                locale = TSHLocaleHelper.exportLocale
                if locale.replace('-', '_') in stage[1].get("locale", {}):
                    export_name = stage[1].get("locale", {})[
                        locale.replace('-', '_')]
                elif locale.split('-')[0] in stage[1].get("locale", {}):
                    export_name = stage[1].get("locale", {})[
                        locale.split('-')[0]]
                elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.exportLocale) in stage[1].get("locale", {}):
                    export_name = stage[1].get("locale", {})[
                        TSHLocaleHelper.GetRemaps(TSHLocaleHelper.exportLocale)]

                stage[1]["name"] = export_name

                item = QStandardItem(f'{stage[1].get("display_name")} / {stage[1].get("en_name")}' if stage[1].get(
                    "display_name") != stage[1].get("en_name") else stage[1].get("display_name"))
                item.setData(stage[1], Qt.ItemDataRole.UserRole)
                self.stageModel.appendRow(item)

                worker = Worker(self.LoadStageImage, *[stage[1], item])
                worker.signals.result.connect(self.LoadStageImageComplete)
                self.threadpool.start(worker)
        except:
            logger.error(traceback.format_exc())

    def LoadStageImage(self, stage, item, progress_callback, cancel_event):
        try:
            if stage.get("path") and os.path.exists(stage.get("path")):
                img = Image.open(stage.get("path"))

                resizeMultiplier = 1

                if img.width > img.height:
                    resizeMultiplier = 64/img.width
                else:
                    resizeMultiplier = 64/img.height

                img = img.resize((int(img.width*resizeMultiplier),
                                 int(img.height*resizeMultiplier)), Image.BILINEAR)

                img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(
                    data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
                pix = QPixmap.fromImage(qimg)
                icon = QIcon(pix)

                return ([item, icon])
        except Exception as e:
            img = QPixmap("./assets/icons/cancel.svg").scaled(32, 32)
            icon = QIcon(img)
            logger.error(traceback.format_exc())
            return ([item, icon])

    def LoadStageImageComplete(self, result):
        try:
            if result is not None:
                if result[0] and result[1]:
                    result[0].setIcon(result[1])
        except Exception as e:
            logger.error(traceback.format_exc())
            return (None)

    def UpdateCharacterModel(self):
        try:
            self.characterModel = QStandardItemModel()

            # Add one empty
            item = QStandardItem("")
            self.characterModel.appendRow(item)

            for c in self.characters.keys():
                item = QStandardItem()
                item.setData(c, Qt.ItemDataRole.EditRole)
                print(c)
                item.setIcon(
                    QIcon(QPixmap.fromImage(self.stockIcons[c][0]))
                )

                data = {
                    "name": self.characters[c].get("export_name"),
                    "en_name": c,
                    "display_name": self.characters[c].get("display_name"),
                    "codename": self.characters[c].get("codename")
                }

                if self.characters[c].get("display_name") != c:
                    item.setData(
                        f'{self.characters[c].get("display_name")} / {c}', Qt.ItemDataRole.EditRole)

                item.setData(data, Qt.ItemDataRole.UserRole)
                self.characterModel.appendRow(item)

            self.characterModel.sort(0)
        except:
            logger.error(traceback.format_exc())

    def UpdateVariantModel(self):
        try:
            self.variantModel = QStandardItemModel()

            # Add one empty
            item = QStandardItem("")
            self.variantModel.appendRow(item)

            for c in self.variants.keys():
                item = QStandardItem()
                item.setData(c, Qt.ItemDataRole.EditRole)
                print(c)

                data = {
                    "name": self.variants[c].get("export_name"),
                    "en_name": c,
                    "display_name": self.variants[c].get("display_name"),
                    "codename": self.variants[c].get("codename")
                }

                
                data["icon_path"] = self.GetVariantIconPath(data["codename"])
                if data["icon_path"]:
                    item.setIcon(QIcon(QPixmap.fromImage(QImage(data["icon_path"])))
                    )
                else:
                    item.setIcon(QIcon(QPixmap.fromImage(QImage('./assets/icons/cancel.svg')))
                    )

                if self.variants[c].get("display_name") != c:
                    item.setData(
                        f'{self.variants[c].get("display_name")} / {c}', Qt.ItemDataRole.EditRole)

                item.setData(data, Qt.ItemDataRole.UserRole)
                self.variantModel.appendRow(item)

            self.variantModel.sort(0)
        except:
            logger.error(traceback.format_exc())

    def GetVariantIconPath(self, variant_codename):
        game_codename = self.selectedGame.get("codename")
        icon_path, asset_root_path = "", "./user_data/games"
        icon_config_path = f"{asset_root_path}/{game_codename}/variant_icon/config.json"
        if os.path.isfile(icon_config_path):
            with open(icon_config_path, "rt", encoding="utf-8") as icon_config_file:
                icon_config = json.loads(icon_config_file.read())
            icon_filename = f"{asset_root_path}/{game_codename}/variant_icon/{icon_config.get('prefix')}{variant_codename}{icon_config.get('postfix')}.png"
            if os.path.isfile(icon_filename):
                icon_path = icon_filename
        return(icon_path)

    def UpdateSkinModel(self):
        self.skinModels = {}

        self.workers = []

        for key, character in self.characters.items():
            characterData = character

            if characterData:
                skins = TSHGameAssetManager.instance.skins.get(key, {})

            sortedSkins = [int(k) for k in skins.keys()]
            sortedSkins.sort()

            skinModel = QStandardItemModel()

            allAssetData = []
            allItem = []

            for skin in sortedSkins:
                item = QStandardItem()

                skinModel.appendRow(item)

                assetData = {}
                assetData["assets"] = TSHGameAssetManager.instance.GetCharacterAssets(
                    character.get("codename"), skin)
                if assetData["assets"] == None:
                    assetData["assets"] = {}

                skinIndex = str(skin)

                # Get skin name
                skinNameData = TSHGameAssetManager.instance.characters.get(
                    character.get("en_name"), {}).get("skin_name", {})

                skin_name = character.get("name")
                skin_name_en = character.get("en_name")

                try:
                    locale = TSHLocaleHelper.programLocale

                    if locale.replace("-", "_") in skinNameData.get(skinIndex, {}).get("locale", {}):
                        skin_name = skinNameData.get(skinIndex, {}).get(
                            "locale", {})[locale.replace("-", "_")]
                    elif re.split("-|_", locale)[0] in skinNameData.get(skinIndex, {}).get("locale", {}):
                        skin_name = skinNameData.get(skinIndex, {}).get(
                            "locale", {})[re.split("-|_", locale)[0]]
                    elif TSHLocaleHelper.GetRemaps(TSHLocaleHelper.exportLocale) in skinNameData.get("locale", {}):
                        skin_name = skinNameData.get(skinIndex, {}).get("locale", {})[TSHLocaleHelper.GetRemaps(
                            TSHLocaleHelper.exportLocale)]
                    elif skinNameData.get(skinIndex, {}).get("name"):
                        skin_name = skinNameData.get(skinIndex, {}).get("name")

                    if skinNameData.get(skinIndex, {}).get("name"):
                        skin_name_en = skinNameData.get(
                            skinIndex, {}).get("name")
                except:
                    logger.error(traceback.format_exc())

                if skinNameData.get(skinIndex, {}).get("is_different_character", False):
                    assetData["name"] = skin_name
                    assetData["en_name"] = skin_name_en

                item.setData(skin_name if skin_name else skinIndex,
                             Qt.ItemDataRole.EditRole)
                item.setData(assetData, Qt.ItemDataRole.UserRole)

                allItem.append(item)
                allAssetData.append(assetData)

            worker = Worker(self.LoadSkinImages, *
                            [allAssetData, allItem, skinModel])
            worker.signals.result.connect(self.LoadSkinImagesComplete)
            self.workers.append(worker)

            self.skinModels[key] = skinModel

        for w in self.workers:
            self.threadpool.start(w)

    def LoadSkinImages(self, allAssetData, allItem, skinModel, progress_callback, cancel_event):
        try:
            icons = []

            for i in range(len(allAssetData)):
                assetData = allAssetData[i]

                # Set to use first asset as a fallback
                key = TSHGameAssetManager.instance.biggestCompletePack
                asset = None

                if assetData["assets"].get(key):
                    asset = assetData["assets"][key]
                elif assetData["assets"].get("full"):
                    asset = assetData["assets"]["full"]
                elif assetData["assets"].get("base_files/icon"):
                    asset = assetData["assets"]["base_files/icon"]

                if asset:
                    # pix = QPixmap(asset["asset"])
                    img = Image.open(asset["asset"])
                else:
                    # pix = QPixmap("./assets/icons/cancel.svg").scaled(16,16)
                    img = Image.open("./assets/icons/cancel.svg")

                targetW = 128
                targetH = 96

                originalW = img.width
                originalH = img.height

                proportional_zoom = 1

                if asset.get("average_size"):
                    proportional_zoom = 0
                    proportional_zoom = max(
                        proportional_zoom,
                        (targetW / asset.get("average_size", {}).get("x", 0)) * 1.2
                    )
                    proportional_zoom = max(
                        proportional_zoom,
                        (targetH / asset.get("average_size", {}).get("y", 0)) * 1.2
                    )

                # For cropped assets, zoom to fill
                # Calculate max zoom
                zoom_x = targetW / originalW
                zoom_y = targetH / originalH

                minZoom = 1
                rescalingFactor = 1
                customZoom = 1

                if asset.get("rescaling_factor"):
                    rescalingFactor = asset.get("rescaling_factor")

                uncropped_edge = asset.get("uncropped_edge", [])

                if not uncropped_edge or len(uncropped_edge) == 0:
                    if zoom_x > zoom_y:
                        minZoom = zoom_x
                    else:
                        minZoom = zoom_y
                else:
                    if (
                        "u" in uncropped_edge and
                        "d" in uncropped_edge and
                        "l" in uncropped_edge and
                        "r" in uncropped_edge
                    ):
                        customZoom = 1.2  # Add zoom in for uncropped assets
                        minZoom = customZoom * proportional_zoom * rescalingFactor
                    elif (
                        not "l" in uncropped_edge and
                        not "r" in uncropped_edge
                    ):
                        minZoom = zoom_x
                    elif (
                        not "u" in uncropped_edge and
                        not "d" in uncropped_edge
                    ):
                        minZoom = zoom_y
                    else:
                        minZoom = customZoom * proportional_zoom * rescalingFactor

                zoom = max(minZoom, customZoom * minZoom)

                # Centering
                xx = 0
                yy = 0

                eyesight = asset.get("eyesight")

                if not eyesight:
                    eyesight = {
                        "x": originalW / 2,
                        "y": originalH / 2
                    }

                xx = -eyesight["x"] * zoom + targetW / 2

                maxMoveX = targetW - originalW * zoom

                if not uncropped_edge or not "l" in uncropped_edge:
                    if (xx > 0):
                        xx = 0

                if not uncropped_edge or not "r" in uncropped_edge:
                    if (xx < maxMoveX):
                        xx = maxMoveX

                yy = -eyesight["y"] * zoom + targetH / 2

                maxMoveY = targetH - originalH * zoom

                if not uncropped_edge or not "u" in uncropped_edge:
                    if (yy > 0):
                        yy = 0

                if not uncropped_edge or not "d" in uncropped_edge:
                    if (yy < maxMoveY):
                        yy = maxMoveY

                img = img.resize(
                    (int(originalW*zoom), int(originalH*zoom)), Image.BILINEAR)
                img = img.crop((
                    int(-xx),
                    int(-yy),
                    int(-xx+128),
                    int(-yy+96)
                ))

                img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(
                    data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
                pix = QPixmap.fromImage(qimg)
                icon = QIcon(pix)

                icons.append(icon)

            return ([(allItem[i], icons[i]) for i in range(len(allItem))])
        except Exception as e:
            logger.error(traceback.format_exc())
            return (None)

    def LoadSkinImagesComplete(self, results):
        try:
            for result in results:
                if result is not None:
                    if result[0] and result[1]:
                        result[0].setIcon(result[1])
        except Exception as e:
            logger.error(traceback.format_exc())
            return (None)

    def GetCharacterAssets(self, characterCodename: str, skin: int, assetpack: str = None):
        charFiles = {}

        if self.selectedGame is not None:
            assetsPacks = []

            if assetpack:
                assetsPacks = [assetpack]
            else:
                assetsPacks = self.selectedGame.get("assets", {}).items()

            # For each assets pack
            for assetKey, asset in assetsPacks:
                try:
                    # Skip stage icon asset packs
                    if type(asset.get("type")) == list:
                        if "stage_icon" in asset.get("type") or "variant_icon" in asset.get("type"):
                            continue
                    elif type(asset.get("type")) == str:
                        if asset.get("type") in ["stage_icon", "variant_icon"]:
                            continue

                    assetPath = f'{self.selectedGame.get("path")}/{assetKey}/'

                    baseName = asset.get(
                        "prefix", "")+characterCodename+asset.get("postfix", "")

                    skinFileList = [f for f in os.listdir(
                        assetPath) if f.startswith(baseName)]

                    skinFiles = {}

                    for f in skinFileList:
                        skinId = f[len(baseName):].rsplit(".", 1)[0]
                        if skinId == "":
                            skinId = 0
                        else:
                            skinId = int(skinId)
                        skinFiles[skinId] = f

                    if len(skinFiles) > 0:
                        charFiles[assetKey] = {
                            "type": asset.get("type", [])
                        }

                        # If skin exists, load it
                        if skin in skinFiles:
                            charFiles[assetKey]["asset"] = assetPath + \
                                skinFiles[skin]
                        else:
                            # If skin remap exists, load remap
                            if asset.get("skin_mapping", {}).get(characterCodename, {}).get(str(skin)):
                                target = int(asset.get("skin_mapping", {}).get(
                                    characterCodename, {}).get(str(skin)))
                                charFiles[assetKey]["asset"] = assetPath + \
                                    skinFiles[target]
                            # If none is found, default to skin 0
                            else:
                                charFiles[assetKey]["asset"] = assetPath + \
                                    skinFiles[0]

                    if asset.get("eyesights"):
                        eyesights = asset.get("eyesights", {}).get(
                            characterCodename, {})

                        if len(eyesights.keys()) > 0:
                            if str(skin) in eyesights:
                                if assetKey in charFiles:
                                    charFiles[assetKey]["eyesight"] = eyesights.get(
                                        str(skin))
                            else:
                                charFiles[assetKey]["eyesight"] = list(
                                    eyesights.values())[0]

                    if asset.get("rescaling_factor"):
                        rescaling_factor = asset.get("rescaling_factor", {}).get(
                            characterCodename, {})

                        if len(rescaling_factor.keys()) > 0:
                            if str(skin) in rescaling_factor:
                                if assetKey in charFiles:
                                    charFiles[assetKey]["rescaling_factor"] = rescaling_factor.get(
                                        str(skin))
                            else:
                                charFiles[assetKey]["rescaling_factor"] = rescaling_factor.get(
                                    "0", 1)

                    if asset.get("unflippable"):
                        unflippable = asset.get("unflippable", {}).get(
                            characterCodename, {})

                        if len(unflippable.keys()) > 0:
                            if str(skin) in unflippable:
                                if assetKey in charFiles:
                                    charFiles[assetKey]["unflippable"] = unflippable.get(
                                        str(skin))
                            else:
                                charFiles[assetKey]["unflippable"] = list(
                                    unflippable.values())[0]

                    if asset.get("metadata"):
                        metadata = {}
                        charFiles[assetKey]['metadata'] = {}
                        for key in range(len(asset.get("metadata"))):
                            metadata[key] = asset.get("metadata", {})[key]["values"].get(
                                characterCodename, {}).get("value", "")
                            charFiles[assetKey]['metadata'][f"{key}"] = {}
                            charFiles[assetKey]['metadata'][f"{key}"]["title_en"] = asset.get("metadata", {})[
                                key].get("title", '')
                            if TSHLocaleHelper.exportLocale in asset.get("metadata", {})[key].get("locale", {}).keys() or TSHLocaleHelper.exportLocale.split('-')[0] in asset.get("metadata", {})[key].get("locale", {}).keys():
                                try:
                                    metadata_title_locale = asset.get("metadata", {})[key].get("locale", {})[
                                        TSHLocaleHelper.exportLocale]
                                except KeyError:
                                    metadata_title_locale = asset.get("metadata", {})[key].get(
                                        "locale", {})[TSHLocaleHelper.exportLocale.split('-')[0]]
                            else:
                                metadata_title_locale = asset.get("metadata", {})[
                                    key].get("title", '')
                            charFiles[assetKey]['metadata'][f"{key}"]["title"] = metadata_title_locale
                            charFiles[assetKey]['metadata'][f"{key}"][f"value_en"] = metadata[key]
                            if TSHLocaleHelper.exportLocale in asset.get("metadata", {})[key]["values"].get(characterCodename, {}).get("locale", {}).keys() or TSHLocaleHelper.exportLocale.split('-')[0] in asset.get("metadata", {})[key]["values"].get(characterCodename, {}).get("locale", {}).keys():
                                try:
                                    metadata[key] = asset.get("metadata", {})[key]["values"].get(
                                        characterCodename, {}).get("locale", {})[TSHLocaleHelper.exportLocale]
                                except KeyError:
                                    metadata[key] = asset.get("metadata", {})[key]["values"].get(
                                        characterCodename, {}).get("locale", {})[TSHLocaleHelper.exportLocale.split('-')[0]]
                            charFiles[assetKey]['metadata'][f"{key}"][f"value"] = metadata[key]

                        # if len(metadata.keys()) > 0:
                        #     if str(skin) in metadata:
                        #         charFiles[assetKey]["metadata"] = metadata.get(
                        #             str(skin))
                        #     else:
                        #         charFiles[assetKey]["metadata"] = list(
                        #             metadata.values())[0]

                    if asset.get("uncropped_edge"):
                        if assetKey in charFiles:
                            charFiles[assetKey]["uncropped_edge"] = asset.get(
                                "uncropped_edge")

                    if asset.get("average_size"):
                        if assetKey in charFiles:
                            charFiles[assetKey]["average_size"] = asset.get(
                                "average_size")
                except Exception as e:
                    logger.error(traceback.format_exc())

        return (charFiles)

    def GetCharacterFromStartGGId(self, smashgg_id: int):
        startggcharacter = self.startgg_id_to_character.get(str(smashgg_id))

        if startggcharacter:
            character = next((c for c in self.characters.items() if c[1].get(
                "smashgg_name") == startggcharacter.get("name")), None)
            if character:
                return character

        return None

    def GetStageFromStartGGId(self, smashgg_id: int):
        stage = next((s for s in self.stages.items() if str(
            s[1].get("smashgg_id")) == str(smashgg_id)), None)
        return stage


if not os.path.exists("./user_data/games"):
    os.makedirs("./user_data/games")

if TSHGameAssetManager.instance == None:
    TSHGameAssetManager.instance = TSHGameAssetManager()
