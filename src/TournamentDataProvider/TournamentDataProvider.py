class TournamentDataProvider:
    def __init__(self, url, threadpool, parent) -> None:
        self.name = ""
        self.url = url
        self.entrants = []
        self.tournamentData = {}
        self.threadpool = threadpool
        self.videogame = None
        self.parent = parent

    def GetEntrants(self):
        pass

    def GetTournamentData(self):
        pass

    def GetMatch(self, setId):
        pass

    def GetMatches(self, getFinished=False, progress_callback=None):
        pass

    def GetStreamMatchId(self, streamName):
        pass

    def GetUserMatchId(self, user):
        pass

    def GetRecentSets(self, id1, id2, callback):
        pass

    def GetLastSets(self, playerId, playerNumber):
        pass
    
    def GetPlayerHistoryStandings(self, playerId, playerNumber, gameType):
        pass
    
    def GetHeadToHeadStandings(self, player1Id, player2Id, gameType):
        pass

    def GetStandings(self, playerNumber):
        pass