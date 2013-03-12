from autobahn.wamp import exportPub, exportSub
from twisted.internet import reactor

from game import EatBulletGame
from settings import _url


class PubSubHandlers(object):

    def __init__(self, protocol):
        self.protocol = protocol

    @exportSub('games', True)
    def games(self, topicUriPrefix, topicUriSuffix):
        print "client wants to subscribe to %s%s" % (topicUriPrefix, topicUriSuffix)

        if not topicUriSuffix:
            return True

        if len(topicUriSuffix) > 1 and topicUriSuffix[0] == '/':
            game_id = int(topicUriSuffix[1:])
            game = self.protocol.factory.games.get(game_id, None)
            if game and self.protocol in game.players:
                print '%s subscribed to game' % self.protocol.login
                game.send_players_list()
                game.send_game_state()

                return True

        return False
