from autobahn.wamp import WampServerFactory
from twisted.internet import reactor

from game import EatBulletGame
from settings import _url


class EatBulletServerFactory(WampServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False, debugWamp=False, debugApp=False, externalPort=None):
        self.games = {}
        WampServerFactory.__init__(self, url,
                                   debug=debug,
                                   debugCodePaths=debugCodePaths,
                                   debugWamp=True,
                                   externalPort=externalPort)

    def init_game(self, protocol):
        game = EatBulletGame(protocol)
        self.games[game.id] = game
        self.send_games_list()

        return game.id

    def remove_game(self, game):
        if game.id in self.games:
            del self.games[game.id]
        self.send_games_list()
        del game

    def send_games_list(self):
        print 'before send games list'
        ids = [id for id, game in self.games.items() if game.state == EatBulletGame.WAIT_OPPONENT]
        self.send_message(_url('games'), ids)

    def send_message(self, url, message):
        reactor.callLater(0, self.dispatch, url, message)