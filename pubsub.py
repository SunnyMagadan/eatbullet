from autobahn.wamp import exportPub, exportSub
from twisted.internet import reactor

from settings import _url


class PubSubHandlers(object):

    def __init__(self, protocol):
        self.protocol = protocol

    @exportSub('players', True)
    def players(self, topicUriPrefix, topicUriSuffix):
        print "client wants to subscribe to %s%s" % (topicUriPrefix, topicUriSuffix)

        if not self.protocol.login:
            print 'need to login first'
            return False

        reactor.callLater(0, self.send_users_list)

        return True

    @exportSub('games', True)
    def games(self, topicUriPrefix, topicUriSuffix):
        print "client wants to subscribe to %s%s" % (topicUriPrefix, topicUriSuffix)

        if not topicUriSuffix:
            return True

        if len(topicUriSuffix) > 1 and topicUriSuffix[0] == '/':
            game_id = int(topicUriSuffix[1:]) - 1
            games = self.protocol.factory.games
            if 0 <= game_id < len(games) and self.protocol in games[game_id].players:
                print '%s subscribed to game' % self.protocol.login
                games[game_id].send_players_list()
                games[game_id].send_game_state()

                return True

        return False

    def send_users_list(self, exclude=[]):
        factory = self.protocol.factory
        if factory.subscriptions.has_key(_url('players')):
            factory.dispatch(_url('players'),
                             [proto.login for proto in factory.subscriptions[_url('players')] if not proto in exclude])

    def send_games_list(self):
        factory = self.protocol.factory
        print 'before send games list'
        factory.dispatch(_url('games'), [game.id for game in factory.games])