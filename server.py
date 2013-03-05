import sys
import traceback
import random

from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.websocket import listenWS
from autobahn.wamp import exportRpc,\
                          exportPub,\
                          exportSub,\
                          WampServerFactory, \
                          WampServerProtocol, WampProtocol


BASE_URL = 'http://localhost:8080/'

def _url(suffix):
    return '%s%s' % (BASE_URL, suffix)
    

class EatBulletGame(object):

    games_counter = 0

    WAIT_OPPONENT = 0
    STARTED = 1
    FINISHED = 2

    def __init__(self, player):
        EatBulletGame.games_counter += 1
        self.id = EatBulletGame.games_counter
        self.turn_count = 0
        self.state = EatBulletGame.WAIT_OPPONENT
        self.players = [player]
        self.current_player = None
        self.stripper_clip = [1, 0, 0, 0, 0, 0]

    def start(self):
        self.state = EatBulletGame.STARTED
        self.current_player = self.players[self.turn_count % 2]
        self.turn_count += 1
        random.shuffle(self.stripper_clip)
        self.send_game_state()

    def join(self, player):
        self.players.append(player)
        self.send_game_message('Joined player %s' % player.login)
        self.start()

    def turn(self, player):
        if self.state == EatBulletGame.STARTED and self.current_player == player:
            if self.stripper_clip[0] == 1:
                # Game over for current player
                self.state = EatBulletGame.FINISHED
                self.send_game_finished()
            else:
                # Continue game playing. Toggle turn
                self.current_player = self.players[self.turn_count % 2]
                self.turn_count += 1
                random.shuffle(self.stripper_clip)
                self.send_game_state()

    def send_game_finished(self):
        pass

    def send_game_state(self):
        pass

    def send_game_message(self, message):
        reactor.callLater(self.protocol.factory.dispatch(_url('games/%s' % self.id), message))


class RpcApi(object):

    def __init__(self, protocol):
        self.protocol = protocol

    @exportRpc
    def login(self, name):
        self.protocol.login = name
        return 'successfully logined'

    @exportRpc
    def start_game(self):
        game = EatBulletGame(self.protocol)
        self.protocol.factory.games.append(game)
        reactor.callLater(0, self.protocol.pubsub.send_games_list)

        return game.id

    @exportRpc
    def join_game(self, game_id):
        game_id = int(game_id)
        games = self.protocol.factory.games

        if 0 < game_id < len(games):
            if games[game_id].state == EatBulletGame.WAIT_OPPONENT:
                games[game_id].join(self.protocol)
                return 'success'

        return 'fail'


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

        if topicUriSuffix:
            game_id = int(topicUriSuffix)
            games = self.protocol.factory.games
            if 0 < topicUriSuffix < len(games) and self.protocol in games[game_id].players:
                return True

        return False

    def send_users_list(self, exclude=[]):
        factory = self.protocol.factory
        if factory.subscriptions.has_key(_url('players')):
            factory.dispatch(_url('players'),
                             [proto.login for proto in factory.subscriptions[_url('players')] if not proto in exclude])

    def send_games_list(self):
        factory = self.protocol.factory
        factory.dispatch(_url('games'), [game.id for game in factory.games])



class EatBulletServerProtocol(WampServerProtocol):

    def onSessionOpen(self):
        self.api = RpcApi(self)
        self.login = ''
        self.registerForRpc(self.api, _url('api#'))
        self.registerForPubSub(_url('players'))
        
        self.pubsub = PubSubHandlers(self)
        self.registerHandlerForPubSub(self.pubsub, BASE_URL)

    def connectionLost(self, reason):
        self.pubsub.send_users_list(exclude=[self])
        WampServerProtocol.connectionLost(self, reason)


class EatBulletServerFactory(WampServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False, debugWamp=False, debugApp=False, externalPort=None):
        self.games = []
        WampServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths, externalPort=externalPort)


if __name__ == '__main__':

    log.startLogging(sys.stdout)
    
    factory = WampServerFactory('ws://localhost:9000', debugWamp=True)
    factory.protocol = EatBulletServerProtocol
    listenWS(factory)

    webdir = File(".")
    web = Site(webdir)
    reactor.listenTCP(8080, web)
    
    reactor.run()
