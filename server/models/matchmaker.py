"""
matchmaker.py

Matchmaker model definition and registry.
"""

import logging
import server
import server.config
import server.models.match
import tbmatch.event_pb2
import tornado.ioloop

class QueueUser(object):
    def __init__(self, user, gameplay_options):
        self.user = user
        self.gameplay_options = gameplay_options

class Matchmaker(object):
    def __init__(self):
        self.queue_users = []
        self.poll_timer = tornado.ioloop.PeriodicCallback(lambda: self.Poll(), 5000)

    def JoinQueue(self, user, gameplay_options):
        queue_user = QueueUser(user, gameplay_options)
        logging.debug('queue user {0} joined queue'.format(user.user_id))
        self.queue_users.insert(0, queue_user)

        event = tbmatch.event_pb2.Event()
        event.type = tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS
        status = tbmatch.event_pb2.WaitMatchProgressEvent.WAITING
        event.wait_match_progress.CopyFrom(server.models.match.CreateWaitMatchProgressEvent(status))
        user.SendEvent(event)

    def LeaveQueue(self, user):
        logging.debug('queue user {0} leaved queue'.format(user.user_id))
        for u in self.queue_users:
            if u.user.user_id == user.user_id:
                self.queue_users.remove(u)

                event = tbmatch.event_pb2.Event()
                event.type = tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS
                status = tbmatch.event_pb2.WaitMatchProgressEvent.CANCEL
                event.wait_match_progress.CopyFrom(server.models.match.CreateWaitMatchProgressEvent(status))
                user.SendEvent(event)
                return

    def StartPolling(self):
        logging.debug("start matchmaker polling")
        self.poll_timer.start()

    def Poll(self):
        logging.debug('running matchmaker poll')

        while len(self.queue_users) >= 2:
            p1 = self.queue_users.pop()
            p2 = self.queue_users.pop()

            # TODO put these 2 users in a temporary queue for re-queue in the case echo test failed

            # found a match
            match_id = server.GetNextUniqueId()

            # create intermediate proto structures
            game_config = server.models.match.CreateGameConfig(match_id, p1.user, p1.gameplay_options.character, p2.user, p2.gameplay_options.character)

            game_session = server.models.match.CreateGameSessionRequest(p1.gameplay_options.character, p2.gameplay_options.character)
            p1port, p2port = server.portal.StartGameSession(game_session, p1.user.handle, p2.user.handle)

            game_endpoint_config1 = server.models.match.CreateGameEndpointConfig(0, p1port, game_session.spec[0].secret)
            game_endpoint_config2 = server.models.match.CreateGameEndpointConfig(1, p2port, game_session.spec[1].secret)

            # create the final proto payload and send them as events to the matched users
            status = tbmatch.event_pb2.WaitMatchProgressEvent.MATCH
            wait_match_progress_event1 = server.models.match.CreateWaitMatchProgressEvent(status, match_id, game_config, game_endpoint_config1)
            event1 = tbmatch.event_pb2.Event()
            event1.type = tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS
            event1.wait_match_progress.CopyFrom(wait_match_progress_event1)
            p1.user.SendEvent(event1)

            event2 = tbmatch.event_pb2.Event()
            wait_match_progress_event2 = server.models.match.CreateWaitMatchProgressEvent(status, match_id, game_config, game_endpoint_config2)
            event2.type = tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS
            event2.wait_match_progress.CopyFrom(wait_match_progress_event2)
            p2.user.SendEvent(event2)
