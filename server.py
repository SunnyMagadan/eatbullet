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
        self.factory = player.factory
        self.game_url = _url('games/%s' % self.id)

    def start(self):
        self.state = EatBulletGame.STARTED
        self.current_player = self.players[self.turn_count % 2]
        self.turn_count += 1
        random.shuffle(self.stripper_clip)
        self.send_game_state()

    def join(self, player):
        self.players.append(player)
        self.send_game_message({'type': 'hint', 'data': 'Joined player %s' % player.login})
        self.send_players_list()
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
        if self.state != EatBulletGame.WAIT_OPPONENT:
            state = {'type': 'state', 'data': {'current_player': self.current_player.login, 'turn': self.turn_count}}

            self.send_game_message(state)

    def send_players_list(self):
        self.send_game_message({'type': 'players', 'data': [player.login for player in self.players]})

    def send_game_message(self, message):
        reactor.callLater(0, self.factory.dispatch, self.game_url, message)


class RpcApi(object):

    def __init__(self, protocol):
        self.protocol = protocol

    @exportRpc
    def login(self, name):
        self.protocol.login = name
        reactor.callLater(0, self.protocol.pubsub.send_games_list)

        return 'successfully logined'

    @exportRpc
    def start_game(self):
        game = EatBulletGame(self.protocol)
        self.protocol.factory.games.append(game)
        reactor.callLater(0, self.protocol.pubsub.send_games_list)

        return game.id

    @exportRpc
    def join_game(self, game_id):
        game_id = int(game_id) - 1
        games = self.protocol.factory.games

        if 0 <= game_id < len(games):
            if games[game_id].state == EatBulletGame.WAIT_OPPONENT:
                games[game_id].join(self.protocol)
                return game_id + 1

        raise Exception(_url("error#failed_to_join"),
                        "Failed to join game #%d" % game_id)


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


class EatBulletServerProtocol(WampServerProtocol):

    def onSessionOpen(self):
        self.api = RpcApi(self)
        self.login = ''
        self.registerForRpc(self.api, _url('api#'))

        self.pubsub = PubSubHandlers(self)
        self.registerHandlerForPubSub(self.pubsub, BASE_URL)

    def connectionLost(self, reason):
        self.pubsub.send_users_list(exclude=[self])
        WampServerProtocol.connectionLost(self, reason)

    def onMessage(self, msg, binary):
      """
      INTERNAL METHOD! Handle WAMP messages received from WAMP client.
      """

      if self.debugWamp:
         log.msg("RX WAMP: %s" % str(msg))

      if not binary:
         try:
            obj = self.factory._unserialize(msg)
            if type(obj) == list:

               ## Call Message
               ##
               if obj[0] == WampProtocol.MESSAGE_TYPEID_CALL:

                  ## parse message and create call object
                  callid = obj[1]
                  uri = self.prefixes.resolveOrPass(obj[2])
                  args = obj[3:]
                  call = self._onBeforeCall(callid, uri, args)

                  ## execute incoming RPC
                  d = maybeDeferred(self._callProcedure, call)

                  ## process and send result/error
                  d.addCallbacks(self._onAfterCallSuccess,
                                 self._onAfterCallError,
                                 callbackArgs = (call,),
                                 errbackArgs = (call,))

               ## Subscribe Message
               ##
               elif obj[0] == WampProtocol.MESSAGE_TYPEID_SUBSCRIBE:
                  topicUri = self.prefixes.resolveOrPass(obj[1])
                  h = self._getSubHandler(topicUri)
                  if h:
                     ## either exact match or prefix match allowed
                     if h[1] == "" or h[4]:

                        ## direct topic
                        if h[2] is None and h[3] is None:
                           self.factory._subscribeClient(self, topicUri)

                        ## topic handled by subscription handler
                        else:
                           try:
                              ## handler is object method
                              if h[2]:
                                 a = h[3](h[2], str(h[0]), str(h[1]))

                              ## handler is free standing procedure
                              else:
                                 a = h[3](str(h[0]), str(h[1]))

                              ## only subscribe client if handler did return True
                              if a:
                                 self.factory._subscribeClient(self, topicUri)
                           except Exception as e:
                              if self.debugWamp:
                                 log.msg("execption during topic subscription handler")
                                 print e
                     else:
                        if self.debugWamp:
                           log.msg("topic %s matches only by prefix and prefix match disallowed" % topicUri)
                  else:
                     if self.debugWamp:
                        log.msg("no topic / subscription handler registered for %s" % topicUri)

               ## Unsubscribe Message
               ##
               elif obj[0] == WampProtocol.MESSAGE_TYPEID_UNSUBSCRIBE:
                  topicUri = self.prefixes.resolveOrPass(obj[1])
                  self.factory._unsubscribeClient(self, topicUri)

               ## Publish Message
               ##
               elif obj[0] == WampProtocol.MESSAGE_TYPEID_PUBLISH:
                  topicUri = self.prefixes.resolveOrPass(obj[1])
                  h = self._getPubHandler(topicUri)
                  if h:
                     ## either exact match or prefix match allowed
                     if h[1] == "" or h[4]:

                        ## Event
                        ##
                        event = obj[2]

                        ## Exclude Sessions List
                        ##
                        exclude = [self] # exclude publisher by default
                        if len(obj) >= 4:
                           if type(obj[3]) == bool:
                              if not obj[3]:
                                 exclude = []
                           elif type(obj[3]) == list:
                              ## map session IDs to protos
                              exclude = self.factory.sessionIdsToProtos(obj[3])
                           else:
                              ## FIXME: invalid type
                              pass

                        ## Eligible Sessions List
                        ##
                        eligible = None # all sessions are eligible by default
                        if len(obj) >= 5:
                           if type(obj[4]) == list:
                              ## map session IDs to protos
                              eligible = self.factory.sessionIdsToProtos(obj[4])
                           else:
                              ## FIXME: invalid type
                              pass

                        ## direct topic
                        if h[2] is None and h[3] is None:
                           self.factory.dispatch(topicUri, event, exclude, eligible)

                        ## topic handled by publication handler
                        else:
                           try:
                              ## handler is object method
                              if h[2]:
                                 e = h[3](h[2], str(h[0]), str(h[1]), event)

                              ## handler is free standing procedure
                              else:
                                 e = h[3](str(h[0]), str(h[1]), event)

                              ## only dispatch event if handler did return event
                              if e:
                                 self.factory.dispatch(topicUri, e, exclude, eligible)
                           except:
                              if self.debugWamp:
                                 log.msg("execption during topic publication handler")
                     else:
                        if self.debugWamp:
                           log.msg("topic %s matches only by prefix and prefix match disallowed" % topicUri)
                  else:
                     if self.debugWamp:
                        log.msg("no topic / publication handler registered for %s" % topicUri)

               ## Define prefix to be used in CURIEs
               ##
               elif obj[0] == WampProtocol.MESSAGE_TYPEID_PREFIX:
                  prefix = obj[1]
                  uri = obj[2]
                  self.prefixes.set(prefix, uri)

               else:
                  log.msg("unknown message type")
            else:
               log.msg("msg not a list")
         except Exception, e:
            traceback.print_exc()
      else:
         log.msg("binary message")


class EatBulletServerFactory(WampServerFactory):

    def __init__(self, url, debug=False, debugCodePaths=False, debugWamp=False, debugApp=False, externalPort=None):
        self.games = []
        WampServerFactory.__init__(self, url,
                                   debug=debug,
                                   debugCodePaths=debugCodePaths,
                                   debugWamp=True,
                                   externalPort=externalPort)


if __name__ == '__main__':

    log.startLogging(sys.stdout)
    
    factory = EatBulletServerFactory('ws://localhost:9000', debugWamp=True)
    factory.protocol = EatBulletServerProtocol
    listenWS(factory)

    webdir = File(".")
    web = Site(webdir)
    reactor.listenTCP(8080, web)
    
    reactor.run()
