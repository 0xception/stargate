#!/usr/bin/env python2.6
"""
Asterisk event gateway which monitors and manages an asterisk
installation. Currently just collect hangup data for statistical
data collection.

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
import sys
import logging

from twisted.application import service, internet
from twisted.plugin import getPlugins
from twisted.internet import defer
from twisted.enterprise import adbapi
from twisted.python import log

from starpy import fastagi

from stargate import StarGateFactory, IChevron

import config

application = service.Application("StarGate")

class StarGate:
    """ Monitors asterisks event manager interface for registered events """

    def __init__(self, checkInterval=60):
        self.checkInterval = checkInterval
        self.ami = None
        self.commands = {}
        self.amiFactory = StarGateFactory(config.ami['username'],
                                          config.ami['password'])
        self.agiFactory = fastagi.FastAGIFactory(self._dispatchCommand)
        self.dbpool = adbapi.ConnectionPool(config.db['type'],
                                            host=config.db['host'],
                                            user=config.db['username'],
                                            passwd=config.db['password'],
                                            db=config.db['database'],
                                            cp_reconnect=True)

    def main(self):
        """ Sets up the application service and runs the connection """
        ## Connects lib loggers to our twisted logger
        #observer = log.PythonLoggingObserver(loggerName='AMI')
        #observer.start()
        amiLog = logging.getLogger('AMI')
        agiLog = logging.getLogger('FastAGI')
        logging.basicConfig()

        # Sets the callback on connectionLost
        self.service = service.IServiceCollection(application)

        self.amiFactory.registerLogin(self._onAMIConnection)
        internet.TCPClient(config.ami['host'], config.ami['port'],
                          self.amiFactory).setServiceParent(self.service)
        internet.TCPServer(config.agi['port'], self.agiFactory
                          ).setServiceParent(self.service)

        ## Register each plugins available commands
        for chevron in getPlugins(IChevron):
            chevron.registerCommands(self)

        # Register each plugin's available services
        for chevron in getPlugins(IChevron):
            chevron.registerServices(self)

    def registerCommands(self, commands, function):
        """
        Registers fastAGI commands with the main fastAGI service. When the
        command is executed it will be parsed and the given function will
        be executed with the passed parameters.
        """
        if isinstance(commands, (str, unicode, type(None))):
            commands = (commands,)
        for command in commands:
            self.commands.setdefault(command, []).append(function)

    def _debug(*args, **kwargs):
        """ If debug mode is set push out logs """
        d = False
        if d:
            log.msg(*args, **kwargs)

    def _fail(self, failure, agi=None):
        log.err(failure)

        if agi is not None:
            sequence = fastagi.InSequence()
            sequence.append(agi.wait, 1)
            sequence.append(agi.finish)
            return sequence()

    def _dispatchCommand(self, agi):
        """
        Parses the incoming command and dispatches the command to the
        corrisponding command handlers.
        """
        from urlparse import urlparse
        import cgi

        r = urlparse(agi.variables['agi_network_script'])

        log.msg("Command: %s in %s" % (r.path, self.commands,))
        if r.path in self.commands:
            p = cgi.parse_qs(r.query)

            handlers = self.commands[r.path]
            for handler in handlers:
                try:
                    handler(agi, **p)
                except Exception, err:
                    log.err("Exception in command handler %s on command %s: %s"
                        % (handler, r.path, err))

    def _onAMIConnection(self, ami):
        """
        Register AMI event callbacks
        Called each and every time that the factory reconnects to the
        transport/server.
        """
        # We should do an initial query to populate any data
        # from channels, queues, etc to get stargate up to date
        log.msg("AMI Connected")
        self.ami = ami

        # Register each plugins event listeners
        log.msg("Locking Chevrons...")
        for chevron in getPlugins(IChevron):
            chevron.registerEvents(self)

        self.ami.status().addCallback(self._onStatus, ami=self.ami)

    def _onStatus(self, events, ami=None):
        """ Get the current status of channels """
        log.msg("Initial Channel Status")
        for event in events:
            log.msg("Event: %s" % (event))
        #for chevron in getPlugins(IChevron):
        #   chevron.onStatus(events)

stargate = StarGate()
stargate.main()
