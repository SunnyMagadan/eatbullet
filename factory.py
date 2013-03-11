from autobahn.wamp import WampServerFactory
from twisted.internet import reactor

from game import EatBulletGame


class EatBulletServerFactory(WampServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False, debugWamp=False, debugApp=False, externalPort=None):
        self.games = []
        WampServerFactory.__init__(self, url,
                                   debug=debug,
                                   debugCodePaths=debugCodePaths,
                                   debugWamp=True,
                                   externalPort=externalPort)

    def init_game(self, protocol):
        game = EatBulletGame(protocol)
        self.games.append(game)
        reactor.callLater(0, protocol.pubsub.send_games_list)

        return game.id

    def remove_game(self, game):
        if game in self.games:
            del self.games[game.id - 1]
        reactor.callLater(0, game.current_player.pubsub.send_games_list)
        del game