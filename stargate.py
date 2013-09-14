"""
StarGate Factory

Copyright (C) 2010 Ovation Networks, Inc.
This file is part of Stargate.

Stargate is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Stargate is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Stargate.  If not, see <http://www.gnu.org/licenses/>.
"""

from twisted.internet import defer
from zope.interface import Interface
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log

from starpy import manager


class IChevron(Interface):
    """
    A stargate plugin.
    """
    def registerEvents():
        """
        Registers all ami events that the stargate plugin will handle
        """
    def registerCommands():
        """
        Register all fastAGI commands that the stargate plugin will handle
        """
    def registerServices():
        """
        Registers all services that the plugin may provide with the application
        """


class StarGateFactory(ReconnectingClientFactory):
    protocol = manager.AMIProtocol

    def __init__(self, username, password):
        self.username = username
        self.secret = password
        self.loginDefer = None

    def buildProtocol(self, addr):
        self.resetDelay()
        return ReconnectingClientFactory.buildProtocol(self, addr)

    def clientConnectionLost(self, connector, reason):
        log.err('Lost connection.  Reason:', reason)
        self.loginDefer = defer.Deferred()
        self.loginDefer.addCallback(self.loginCallback)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.err('Connection failed. Reason:', reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector,
                                                         reason)

    def clientConnectionMade(self):
        self.connected = True

    def registerLogin(self, function):
        self.loginCallback = function
        self.loginDefer = defer.Deferred()
        self.loginDefer.addCallback(self.loginCallback)
