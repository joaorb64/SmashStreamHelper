from multiprocessing import Lock
import os
import json
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
import re
import csv
import traceback
from loguru import logger

from .Helpers.TSHDictHelper import deep_clone
from .TSHGameAssetManager import TSHGameAssetManager
from .SettingsManager import SettingsManager

class TSHPlayerDBSignals(QObject):
    db_updated = Signal()


class TSHPlayerDB:
    signals = TSHPlayerDBSignals()
    database = {}
    model: QStandardItemModel = None
    fieldnames = ["prefix", "gamerTag", "name", "twitter",
                  "country_code", "state_code", "mains", "pronoun", "custom_textbox"] # Please always add the new fields at the end of the list
    modelLock = Lock()

    def LoadDB():
        try:
            if os.path.exists("./user_data/local_players.csv") == False:
                with open('./user_data/local_players.csv', 'w', encoding='utf-8') as outfile:
                    spamwriter = csv.writer(outfile)
                    spamwriter.writerow(TSHPlayerDB.fieldnames)
            
            # Backwards compatibility
            with open('./user_data/local_players.csv', 'r', encoding='utf-8') as csvfile:
                lines = csvfile.readlines()
                header = lines[0].rstrip().split(",")
                for field in TSHPlayerDB.fieldnames:
                    if field not in header:
                        lines[0] = lines[0].rstrip() + f",{field}"
                        for i in range(1, len(lines)):
                            lines[i] = lines[i].rstrip() + ","
            
            with open('./user_data/local_players.csv', 'w', encoding='utf-8') as outfile:
                outfile.write("\n".join(lines))

            with open('./user_data/local_players.csv', 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, quotechar='\'')
                for player in reader:
                    tag = player.get(
                        "prefix")+" "+player.get("gamerTag") if player.get("prefix") else player.get("gamerTag")
                    if tag not in TSHPlayerDB.database:
                        TSHPlayerDB.database[tag] = player

                        try:
                            player["mains"] = json.loads(
                                player.get("mains", "{}"))
                        except:
                            player["mains"] = {}
                            logger.error(f"No mains found for: {tag}")

            TSHPlayerDB.SetupModel()
        except Exception as e:
            logger.error(traceback.format_exc())

    def AddPlayers(players, overwrite=False):
        logger.info(f"Adding players to DB: {len(players)}")
        for player in players:
            if player is not None:
                tag = player.get(
                    "prefix")+" "+player.get("gamerTag") if player.get("prefix") else player.get("gamerTag")

                if not overwrite:
                    if tag not in TSHPlayerDB.database:
                        incomingMains = player.get("mains", {})
                        for game in incomingMains:
                            for main in incomingMains[game]:
                                if len(main) == 1:
                                    main.append(0)
                        TSHPlayerDB.database[tag] = player
                    else:
                        dbMains = deep_clone(
                            TSHPlayerDB.database[tag].get("mains", {})
                        )
                        incomingMains = player.get("mains", {})

                        newMains = []
                        for game in incomingMains:
                            for main in incomingMains[game]:
                                if len(main) == 1:
                                    found = next(
                                        (m for m in dbMains.get(game, []) if m[0] == main[0]), None)
                                    if found:
                                        main.append(found[1])
                                    else:
                                        main.append(0)
                                newMains.append(main)
                            dbMains[game] = newMains

                        if SettingsManager.Get("general.disable_overwrite", False):
                            TSHPlayerDB.database[tag] = player | TSHPlayerDB.database[tag]
                        else:
                            TSHPlayerDB.database[tag].update(player)
                        TSHPlayerDB.database[tag]["mains"] = dbMains
                else:
                    if TSHPlayerDB.database.get(tag) is not None and player.get("mains") is not None:
                        try:
                            mains = TSHPlayerDB.database[tag].get("mains", {})
                            mains.update(player.get("mains", {}))
                            player["mains"] = mains
                        except:
                            logger.error(traceback.format_exc())
                    TSHPlayerDB.database[tag] = player

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()

    def DeletePlayer(tag):
        if tag in TSHPlayerDB.database:
            del TSHPlayerDB.database[tag]

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()

    def SetupModel():
        with TSHPlayerDB.modelLock:
            TSHPlayerDB.model = QStandardItemModel()

            cancelIcon = QIcon(QPixmap.fromImage(QImage("./assets/icons/cancel.svg").scaledToWidth(
                32, Qt.TransformationMode.SmoothTransformation)))

            charIcons = {}

            for char in TSHGameAssetManager.instance.stockIcons:
                charIcons[char] = {}
                for skin in TSHGameAssetManager.instance.stockIcons[char]:
                    charIcons[char][skin] = QIcon(QPixmap.fromImage(
                        TSHGameAssetManager.instance.stockIcons[char][skin]))

            for player in TSHPlayerDB.database.values():
                if player is not None:
                    try:
                        tag = player.get(
                            "prefix")+" "+player.get("gamerTag") if player.get("prefix") else player.get("gamerTag")

                        item = QStandardItem(tag)
                        item.setIcon(cancelIcon)

                        if player.get("mains") and type(player.get("mains")) == dict:
                            if TSHGameAssetManager.instance.selectedGame.get("codename") in player.get("mains", {}).keys():
                                playerMains = player.get(
                                    "mains")[TSHGameAssetManager.instance.selectedGame.get("codename")]

                                if playerMains is not None and len(playerMains) > 0:
                                    # Must be a list of size 2 [character, skin]
                                    playerMains = [main for main in playerMains if isinstance(
                                        main, list) and len(main) == 2]

                                    # If the skin is invalid, default to 0
                                    for main in playerMains:
                                        skin = 0
                                        try:
                                            skin = int(main[1])
                                        except:
                                            logger.error(
                                                f'Local DB error: Player {player.get("gamerTag")} has an invalid skin for character {main[0]}')
                                            logger.error(traceback.format_exc())
                                        main[1] = skin

                                    if playerMains[0][0] in TSHGameAssetManager.instance.characters.keys():
                                        character = playerMains[0]

                                        assets = charIcons

                                        if assets == None:
                                            assets = {}

                                        if assets.get(character[0], {}).get(int(playerMains[0][1]), None):
                                            item.setIcon(assets.get(character[0], {}).get(
                                                int(playerMains[0][1]), None))

                        item.setData(player, Qt.ItemDataRole.UserRole)

                        TSHPlayerDB.model.appendRow(item)
                    except:
                        logger.error(
                            f'Error loading player from local DB: {player.get("gamerTag")}')
                        logger.error(traceback.format_exc())

            TSHPlayerDB.signals.db_updated.emit()

    def SaveDB():
        try:
            with open('./user_data/local_players.csv', 'w', encoding="utf-8", newline='') as outfile:
                spamwriter = csv.DictWriter(
                    outfile, fieldnames=TSHPlayerDB.fieldnames, extrasaction="ignore", quotechar='\'')
                spamwriter.writeheader()

                for player in TSHPlayerDB.database.values():
                    if player is not None:
                        playerData = deep_clone(player)

                        if player.get("mains") is not None:
                            playerData["mains"] = json.dumps(player["mains"])

                        spamwriter.writerow(playerData)
        except Exception as e:
            logger.error(traceback.format_exc())


TSHGameAssetManager.instance.signals.onLoad.connect(TSHPlayerDB.SetupModel)
