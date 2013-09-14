#!/usr/bin/env python
"""
Stargate queue callback plugin designed to allow callers to call into
a tech support line, enter the queue and then possibly press/dial an
extension to set give their callback number and ask that the system
auto call them back when they are next up in queue. Allowing them to not waste
their min or sit on hold for very long.

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

from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.python import log
from twisted.application import internet
from starpy import fastagi

from stargate import IChevron
import config


def debug(*args, **kwargs):
    """ If debug mode is set push out logs """
    d = False
    if d:
        log.msg(*args, **kwargs)


class RequestHandler:
    """ Handles requests to control the callback queue """

    def __init__(self, dbpool):
        self.dbpool = dbpool
        self.uid = 0
        self.errCount = 0
        self.deferred = defer.Deferred()

    def _fail(self, failure):
        """
        Attempt to retry our collector calls up to a maximum
        failed attempts (default 3). If still unsuccessful
        return failed deferred object
        """
        log.err(failure)

    def validateNumber(self, number=None):
        """ Validates a number against the callback queue blacklist """
        if number is not None:
            return self.dbpool.runQuery("""
                        SELECT id,number FROM `callback_blacklist`
                        WHERE number=%s""", (number,))
        return self.deferred.errback(ValueError("No Number Set"))

    def resetQueue(self):
        """
        Reset the queue database by clearing/deleting out all the non-callback
        rows.
        """
        return self.dbpool.runQuery("""
                    DELETE FROM `queue`
                    WHERE callback=0""")

    def resetQueueMembers(self):
        """
        Resets the queue members database by clearing/deleting out all members
        """
        return self.dbpool.runQuery("""DELETE FROM `queue_members`""")

    def addAgentToQueue(self, agent, queue, name, location, penalty,
                        calls_taken, last_call, status, paused):
        """
        Add agent location/queue to the database. Uniqueness occurs for
        interface/location and queue combinations.
        """
        if queue is None or location is None:
            return self.deferred.errback(ValueError("No queue/location set"))

        return self.dbpool.runQuery("""
                    INSERT INTO `queue_members`
                        (agent, queue, name, location, penalty, calls_taken,
                         last_call, status, paused, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (agent, queue, name, location, penalty, calls_taken,
                 last_call, status, paused,))

    def removeAgentFromQueue(self, queue, location):
        """ Remove agent location/queue from the database. """
        if queue is None or location is None:
            return self.deferred.errback(ValueError("No queue/location set"))

        return self.dbpool.runQuery("""
                    DELETE FROM `queue_members`
                    WHERE queue=%s AND location=%s""", (queue, location,))

    def updateAgentStatus(self, queue, location, penalty, calls_taken,
                          last_call, status, paused):
        """ Update an agent status. """
        if queue is None or location is None:
            return self.deferred.errback(ValueError("No queue/location set"))

        return self.dbpool.runQuery("""
                    UPDATE `queue_members` SET
                        penalty=%s,
                        calls_taken=%s,
                        last_call=%s,
                        status=%s,
                        paused=%s
                    WHERE queue=%s AND location=%s""", (penalty, calls_taken,
                last_call, status, paused, queue, location,))

    def addToQueue(self, uid, callerid, queue):
        """ Validates the caller before adding them to the callback queue """
        if uid > 0:
            return self.dbpool.runQuery("""
                        INSERT INTO `queue`
                            (uid, callback, callerid, queue_name)
                        VALUES (%s, 0, %s, %s)""", (uid, callerid, queue,))

        return self.deferred.errback(ValueError("No UniqueID Set"))

    def removeFromQueue(self, uid=None, force=False):
        """
        Validates the caller before removing them from the callback queue
        """
        if uid is not None:
            condition = ""
            if not force:
                condition = "AND callback=0"
            return self.dbpool.runQuery("""
                        DELETE FROM `queue`
                        WHERE uid=%s""" + condition, (uid,))
        return self.deferred.errback(ValueError("No UniqueID Set"))

    def updateCallbackCount(self, uid=None):
        """
        Updates the callback counter for the specified uid/caller. This is used
        to keep track of the number of callback attempts so we dont get into a
        situation where we are spamming the number with calls
        """
        if uid > 0:
            return self.dbpool.runQuery("""
                        UPDATE `queue` SET
                            count=count+1
                        WHERE uid=%s""", (uid,))
        return self.deferred.errback(ValueError("No UniqueID Set"))

    def toggleQueueCallback(self, uid=None, number=None, room=None):
        """
        Sets the caller up so that they are not removed from the callback
        database on exit from the queue, allowing the script to poll and at a
        later point in time call them back.
        """
        if uid is not None:
            return self.dbpool.runQuery("""
                    UPDATE `queue` SET
                        callback=IF(callback=0, 1, 0),
                        number=%s,
                        room=%s
                    WHERE uid=%s""", (number, room, uid,))
        return self.deferred.errback(ValueError("No UniqueID Set"))

    def getQueueCallback(self, name=None):
        """
        Queries the database and returns the top caller in the callback queue
        """
        if name is not None:
            return self.dbpool.runQuery("""
                    SELECT
                        q.uid, q.callback, q.callerid, q.number, q.room,
                        q.queue_name, q.count, r.ticket, r.caller_dnid
                    FROM `queue` AS q
                    LEFT JOIN `records` AS r
                        ON `r`.`uid`=`q`.uid
                    WHERE q.queue_name = %s
                    ORDER BY q.id ASC
                    LIMIT 1""", (name,))

        return self.deferred.errback(ValueError("No Queue Name Set"))

    def getQueues(self):
        """ Gets all of the configured queues from the database """
        return self.dbpool.runQuery("SELECT id, name FROM `queue_name`")


class QueuePlugin:
    """
    Queue plugin implementation to work with the stargate asterisk
    interface system.
    """
    implements(IChevron, IPlugin)

    def __init__(self):
        self.application = None
        self.service = None
        self.factory = None
        self.cfg = config.plugins['queue']

    def registerServices(self, application):
        debug("%s Chevron: Services Locked." % (self.__class__.__name__,))
        if self.application is None:
            self.application = application
        self.checker = internet.TimerService(self.cfg['interval'],
                                             self._callbackService)
        self.checker.setServiceParent(self.application.service)

    def registerCommands(self, application):
        debug("%s Chevron: Commands Locked." % (self.__class__.__name__,))
        if self.application is None:
            self.application = application
        self.application.registerCommands('ToggleCallback',
                                          self._toggleCallback)
        self.application.registerCommands('RemoveCallback',
                                          self._removeCallback)

    def registerEvents(self, application):
        debug("%s Chevron: Events Locked." % (self.__class__.__name__,))

        if self.application is None:
            self.application = application
        self.application.ami.registerEvent('Join', self._onQueueJoin)
        self.application.ami.registerEvent('Leave', self._onQueueLeave)
        #self.application.ami.registerEvent('Hangup', self._onQueueLeave)
        self.application.ami.registerEvent('QueueCallerAbandoned',
                                           self._onCallerAbandonded)
        self.application.ami.registerEvent('AgentConnect',
                                           self._onAgentConnect)
        self.application.ami.registerEvent('AgentDump', self._onAgentDump)
        self.application.ami.registerEvent('AgentComplete',
                                           self._onAgentComplete)
        self.application.ami.registerEvent('QueueMemberStatus',
                                           self._onAgentStatus)
        self.application.ami.registerEvent('QueueMemberPaused',
                                           self._onAgentPause)
        self.application.ami.registerEvent('QueueMemberAdded',
                                            self._onAgentAdded)
        self.application.ami.registerEvent('QueueMemberRemoved',
                                            self._onAgentRemoved)

        h = RequestHandler(self.application.dbpool)
        d1 = h.resetQueue().addErrback(self._fail)
        d2 = h.resetQueueMembers().addErrback(self._fail)
        s = self.application.ami.queueStatus()
        dl = defer.gatherResults([d1, d2, s])
        dl.addCallback(self._initQueue)

    def _fail(self, failure, agi=None):
        """ Handles failures """
        log.err(failure)

        if agi is not None:
            sequence = fastagi.InSequence()
            sequence.append(agi.wait, 1)
            sequence.append(agi.setPriority, 1)
            sequence.append(agi.finish)
            return sequence()

    def _interesting(self, agi=None, event=None):
        """
        Decides whether this channel event is interesting.
        Ideally it would be all incoming calls on the zap channel and
        all incoming calls from the vonage lines. The point is to exclude
        events triggered by internal channels and communication.
        """
        if agi is not None:
            queue = agi.variables['agi_queue']
        elif event is not None:
            debug("%s Chevron: Event Triggered: %s" %
                (self.__class__.__name__, event,))
            queue = event['queue']
        else:
            return False

        return (queue in self.cfg['queues'])

    def _initQueue(self, args):
        """
        Initializes the callback queue database and sets the current callers
        in queue up according to their current order. Attempting to verify any
        stale data in the database and verifying that the users are either
        still in the queue or allowing them to get callbacks.
        """

        events = args[2]

        debug("%s Chevron: Initializing Queue" % (self.__class__.__name__,))
        for event in events:
            if not self._interesting(event=event):
                continue

            debug("Event: %s" % (event,))
            if event['event'] == "QueueEntry":
                h = RequestHandler(self.application.dbpool)
                d = h.addToQueue(event['uniqueid'],
                                 event['calleridnum'],
                                 event['queue'])
                d.addErrback(self._fail)
            elif event['event'] == "QueueMember":
                (_, agent) = event['location'].split("/")

                h = RequestHandler(self.application.dbpool)
                d = h.addAgentToQueue(agent,
                                      event['queue'], event['name'],
                                      event['location'], event['penalty'],
                                      event['callstaken'], event['lastcall'],
                                      event['status'], event['paused'])
                d.addErrback(self._fail)

    def _onQueueJoin(self, ami, event):
        """
        When a user/channel joins a asterisk queue this AMI event will be
        triggered and will add the caller into our queue.
        """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

        if not self._interesting(event=event):
            return

        h = RequestHandler(self.application.dbpool)
        d = h.addToQueue(event['uniqueid'],
                         event['calleridnum'], event['queue'])
        d.addErrback(self._fail)

    def _onQueueLeave(self, ami, event):
        """
        When a user/channel leaves an asterisk queue this AMI event will
        trigger and causes the caller to be removed from the callback queue
        if they were not set to get a callback from support.
        """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

        if not self._interesting(event=event):
            return

        h = RequestHandler(self.application.dbpool)
        d = h.removeFromQueue(event['uniqueid'])
        d.addErrback(self._fail)

    def _onCallerAbandonded(self, ami, event):
        """
        When a user leaves the queue before connecting to an agent they have
        officially abandonded the queue. This will be reflected in the call
        data records status
        """
        pass

    def _onAgentConnect(self, ami, event):
        """ Agent was successfully connected to a call """
        pass

    def _onAgentDump(self, ami, event):
        """ Agent dumped/hanged up on the call. """
        pass

    def _onAgentComplete(self, ami, event):
        """ Agent call completed successfuly. """
        pass

    def _onAgentStatus(self, ami, event):
        """
        Queue agent status has changed.
        Status Codes:
            AST_DEVICE_UNKNOWN      0
            AST_DEVICE_NOT_INUSE    1
            AST_DEVICE_INUSE        2
            AST_DEVICE_BUSY         3
            AST_DEVICE_INVALID      4
            AST_DEVICE_UNAVAILABLE  5
            AST_DEVICE_RINGING      6
            AST_DEVICE_RINGINUSE    7
            AST_DEVICE_ONHOLD       8
        """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

        if not self._interesting(event=event):
            return

        h = RequestHandler(self.application.dbpool)
        d = h.updateAgentStatus(
                queue=event['queue'],
                location=event['location'],
                penalty=event['penalty'],
                calls_taken=event['callstaken'],
                last_call=event['lastcall'],
                status=event['status'],
                paused=event['paused'])
        d.addErrback(self._fail)

    def _onAgentPause(self, ami, event):
        """
        Agent was paused. Calls from the queue will not get sent to the agent
        while they are paused.
        """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

    def _onAgentAdded(self, ami, event):
        """ Agent was dynamically added to a queue. """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

        if not self._interesting(event=event):
            return

        (_, agent) = event['location'].split("/")

        h = RequestHandler(self.application.dbpool)
        d = h.addAgentToQueue(agent, event['queue'], event['membername'],
                              event['location'], event['penalty'],
                              event['callstaken'], event['lastcall'],
                              event['status'], event['paused'])
        d.addErrback(self._fail)

    def _onAgentRemoved(self, ami, event):
        """ Agent was removed from a queue dynamically. """
        debug("%s Chevron: %s Event Triggered: %s" %
            (self.__class__.__name__, event['event'], event,))

        if not self._interesting(event=event):
            return

        h = RequestHandler(self.application.dbpool)
        d = h.removeAgentFromQueue(event['queue'], event['location'])
        d.addErrback(self._fail)

    def _toggleCallback(self, agi, number=None, room=None):
        """
        Toggles the callback switch for the current channel/uid and sets the
        callback number if one is given, otherwise the caller ID will be used
        as the callback number instead.
        """
        debug("%s Chevron: Toggle Callback Triggered." %
            (self.__class__.__name__,))
        if number is None:
            number = agi.variables['agi_callerid']
        else:
            number = number[0]

        if room is not None:
            room = room[0]

        ## Chained defers method
        h = RequestHandler(self.application.dbpool)
        d = h.validateNumber(number)
        d.addCallback(self._setCallback,
                      uid=agi.variables['agi_uniqueid'],
                      number=number, room=room, agi=agi)
        d.addErrback(self._fail, agi=agi)

    def _removeCallback(self, agi, uniqueid=None):
        """
        Removes the given uniqueid from the callback queue. This should be used
        once the callback as occured and the caller is now back in the queue.
        """
        debug("%s Chevron: Remove Callback Triggered." %
            (self.__class__.__name__,))
        if uniqueid is not None:
            uniqueid = uniqueid[0]
            h = RequestHandler(self.application.dbpool)
            d = h.removeFromQueue(uniqueid, force=True)
            d.addErrback(self._fail, agi=agi)

        sequence = fastagi.InSequence()
        sequence.append(agi.finish)
        return sequence()

    def _setCallback(self, matches, uid=0, number=None, room=None, agi=None):
        """
        Verifies that the number that the caller wishes to recieve a callback
        on is not in the callback blacklist. If the number validates then the
        callback switch is toggled.
        """
        sequence = fastagi.InSequence()
        if uid > 0:
            if len(matches) > 0:
                debug("%s Chevron: Number is invalid" %
                    (self.__class__.__name__,))
                sequence.append(agi.setVariable, "INVALID", 1)
                sequence.append(agi.streamFile, 'privacy-incorrect')
                sequence.append(agi.wait, 1)
                sequence.append(agi.setPriority, 1)
            else:
                debug("%s Chevron: Number is valid" %
                    (self.__class__.__name__,))
                h = RequestHandler(self.application.dbpool)
                d = h.toggleQueueCallback(uid, number, room)
                d.addErrback(self._fail, agi=agi)

        sequence.append(agi.finish)
        return sequence()

    def _callbackService(self):
        """
        Checks the callback queue for any callers who need to be called back
        in order to re-enter the call queue.
        """
        debug("%s Chevron: Callback Triggered." % (self.__class__.__name__,))
        if self.application.ami != None:
            for name in self.cfg['queues']:
                h = RequestHandler(self.application.dbpool)
                d = h.getQueueCallback(name)
                ## Uncomment this to re-enable the call back features
                #d.addCallbacks(self._sendCallback, self._fail)

    def _sendCallback(self, callers=None):
        """
        Uses the asterisk AMI interface to originate a call out to the number
        given. If the call fails to connect it leaves the caller in the queue
        otherwise it will remove the caller from the queue once they answer the
        line.
        """
        for caller in callers:
            if caller[1] != 0:
                l = []
                if caller[6] >= config.plugins['callback']['callback_limit']:
                    debug("%s Chevron: Exceeded Callback Attempts Limit" %
                        (self.__class__.__name__,))
                    h = RequestHandler(self.application.dbpool)
                    rd = h.removeFromQueue(caller[0], force=True)
                    rd.addErrback(self._fail)
                    l.append(rd)

                debug("%s Chevron: Sending Callback" %
                    (self.__class__.__name__,))

                # Send the actual callback to the number. The results of
                # success or fail do not matter at this time. We use another
                # AGI call once the channel is picked up to determine if it
                # worked. This is because the originate can't tell accurately.
                cd = self.application.ami.originate(
                    channel='SIP/' + caller[3] + '@13193656200',
                    context=self.cfg['callback']['context'],
                    exten=self.cfg['callback']['exten'],
                    priority=self.cfg['callback']['priority'],
                    callerid=self.cfg['callback']['callerid'],
                    timeout=self.cfg['callback']['timeout'],
                    variable={'callbackUID': caller[0],
                              'queueName': caller[5],
                              'itemID': caller[7],
                              'roomNumber': caller[4],
                              'callbackDNID': caller[8]})
                l.append(cd)

                # Update the callback counter after callback (successful or
                # not)
                h = RequestHandler(self.application.dbpool)
                ud = h.updateCallbackCount(caller[0])
                ud.addErrback(self._fail)
                l.append(ud)

                dl = defer.DeferredList(l)


# Comment out this line to disable the plugin
queuePlugin = QueuePlugin()
