from autobahn.wamp import WampServerProtocol

from pubsub import PubSubHandlers
from rpc import RpcApi
from settings import _url


class EatBulletServerProtocol(WampServerProtocol):

    def onSessionOpen(self):
        self.api = RpcApi(self)
        self.login = ''
        self.registerForRpc(self.api, _url('api#'))

        self.pubsub = PubSubHandlers(self)
        self.registerHandlerForPubSub(self.pubsub, _url())

    def connectionLost(self, reason):
        self.pubsub.send_users_list(exclude=[self])
        WampServerProtocol.connectionLost(self, reason)
