import sys
import traceback
import random

from autobahn.websocket import listenWS
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from factory import EatBulletServerFactory
from protocol import EatBulletServerProtocol


if __name__ == '__main__':

    log.startLogging(sys.stdout)
    
    factory = EatBulletServerFactory('ws://localhost:9000', debugWamp=True)
    factory.protocol = EatBulletServerProtocol
    listenWS(factory)

    webdir = File(".")
    web = Site(webdir)
    reactor.listenTCP(8080, web)
    
    reactor.run()
