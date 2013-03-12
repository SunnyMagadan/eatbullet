import random

from twisted.internet import reactor

from settings import _url


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
        self.send_message('Game has been started')
        self.send_game_state()

    def join(self, player):
        if self.state == EatBulletGame.WAIT_OPPONENT:
            self.players.append(player)
            self.send_message('Joined player %s' % player.login)
            self.send_players_list()
            self.start()

            return self.id
        else:
            raise Exception(_url("error#failed_to_join"),
                            "Failed to join game #%d" % self.id)

    def turn(self, player):
        if self.state == EatBulletGame.STARTED and self.current_player == player:
            random.shuffle(self.stripper_clip)
            if self.stripper_clip[0] == 1:
                # Game over for current player
                self.state = EatBulletGame.FINISHED
                self.send_message('%s: ate bullet' % self.current_player.login)
                self.send_game_finished()
                # Remove game from the server list
                self.factory.remove_game(self)
            else:
                # Continue game playing. Switch current player
                self.send_message('%s: misfired' % self.current_player.login)
                self.current_player = self.players[self.turn_count % 2]
                self.turn_count += 1
                self.send_game_state()

            return True
        else:
            return False

    def send_game_finished(self):
        state = {'type': 'finished', 'data': {'winner': self.players[self.turn_count % 2].login}}
        self.send_game_message(state)

    def send_game_state(self):
        if self.state != EatBulletGame.WAIT_OPPONENT:
            state = {'type': 'state', 'data': {'current_player': self.current_player.login, 'turn': self.turn_count}}
            self.send_game_message(state)
        elif self.state == EatBulletGame.WAIT_OPPONENT:
            self.send_game_message({'type': 'hint', 'data': 'Waiting for opponent'})

    def send_players_list(self):
        self.send_game_message({'type': 'players', 'data': [player.login for player in self.players]})

    def send_message(self, message):
        self.send_game_message({'type': 'hint', 'data': message})

    def send_game_message(self, message):
        self.factory.send_message(self.game_url, message)
