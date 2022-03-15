from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic
import json

from src.TSHScoreboardPlayerWidget import TSHScoreboardPlayerWidget
from .Helpers.TSHCountryHelper import TSHCountryHelper
from .StateManager import StateManager
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerDB import TSHPlayerDB
from .TSHTournamentDataProvider import TSHTournamentDataProvider


class TSHPlayerListSlotWidget(QGroupBox):
    def __init__(self, index, playerList, *args):
        super().__init__(*args)
        self.index = index
        self.playerList = playerList

        self.setLayout(QHBoxLayout())

        self.playerWidgets = []

    def SetPlayersPerTeam(self, number):
        while len(self.playerWidgets) < number:
            p = TSHScoreboardPlayerWidget(
                index=len(self.playerWidgets)+1, teamNumber=1, path=f'player_list.slot.{self.index}.player.{len(self.playerWidgets)+1}')
            self.playerWidgets.append(p)
            self.layout().addWidget(p)

            p.SetCharactersPerPlayer(self.playerList.charNumber.value())

            index = len(self.playerWidgets)

            p.btMoveUp.clicked.connect(lambda x, index=index, p=p: p.SwapWith(
                self.playerWidgets[index-1 if index > 0 else 0]))
            p.btMoveDown.clicked.connect(lambda x, index=index, p=p: p.SwapWith(
                self.playerWidgets[index+1 if index < len(self.playerWidgets) - 1 else index]))

        while len(self.playerWidgets) > number:
            p = self.playerWidgets[-1]
            p.setParent(None)
            self.playerWidgets.remove(p)

        # if number > 1:
        #     self.team1column.findChild(QLineEdit, "teamName").setVisible(True)
        #     self.team2column.findChild(QLineEdit, "teamName").setVisible(True)
        # else:
        #     self.team1column.findChild(QLineEdit, "teamName").setVisible(False)
        #     self.team1column.findChild(QLineEdit, "teamName").setText("")
        #     self.team2column.findChild(QLineEdit, "teamName").setVisible(False)
        #     self.team2column.findChild(QLineEdit, "teamName").setText("")

    def SetCharacterNumber(self, value):
        for pw in self.playerWidgets:
            pw.SetCharactersPerPlayer(value)
