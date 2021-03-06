from autobahn.wamp import exportRpc
from twisted.internet import reactor

from settings import _url


class RpcApi(object):

    def __init__(self, protocol):
        self.protocol = protocol

    @exportRpc
    def login(self, name):
        self.protocol.login = name
        self.protocol.factory.send_games_list()

        return 'successfully logined'

    @exportRpc
    def start_game(self):
        return self.protocol.factory.init_game(self.protocol)

    @exportRpc
    def join_game(self, game_id):
        game_id = int(game_id)
        game = self.protocol.factory.games.get(game_id, None)

        if game:
            return game.join(self.protocol)

        raise Exception(_url("error#failed_to_join"),
                        "Failed to join game #%d" % game_id)

    @exportRpc
    def turn(self, game_id):
        game_id = int(game_id)
        game = self.protocol.factory.games.get(game_id, None)

        if game:
            return game.turn(self.protocol)

        raise Exception(_url("error#failed_to_turn"),
                        "Failed to make turn")
