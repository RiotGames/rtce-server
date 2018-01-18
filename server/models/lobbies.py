# pylint: disable=C0103

"""
lobbies.py

Lobby management
"""

import server
import string
import random
import logging
import tbmatch.match_pb2
import tbmatch.lobby_pb2

class LobbyMember(object):
    def __init__(self, user, lobby):
        self.user = user
        self.ready = False
        self.character = None
        self.owner = user.user_id == lobby.owner_user_id
        self.lobby = lobby

    def EncodeState(self, state):
        state.account_id = self.user.user_id
        state.handle = self.user.handle
        state.owner = self.user.user_id == self.lobby.owner_user_id
        state.ready = self.ready

class Lobby(object):
    def __init__(self, name):
        self.name = name
        self.members = {}
        self.queue = []
        self.lobby_id = server.GetNextUniqueId()
        self.owner_user_id = None
        self.join_code = ''.join(random.choice(string.letters).upper() for i in xrange(5))

    def EncodeState(self):
        state = tbmatch.lobby_pb2.Lobby()
        state.name = self.name
        state.lobby_id = self.lobby_id
        state.state = tbmatch.lobby_pb2.LS_IDLE
        state.type = tbmatch.lobby_pb2.LT_QUEUED
        state.game_config.options.mode = tbmatch.match_pb2.GameOptions.GM_FIGHT

        for m in self.members.values():
            member = state.member.add()
            member.account_id = m.user.user_id
            member.handle = m.user.handle
            member.owner = m.user.user_id == self.owner_user_id
            member.ready = m.ready

        for user_id in self.queue:
            state.queue.extend([user_id])

        return state

    def SetOwner(self, user):
        self.owner_user_id = user.user_id
        member = self.members[user.user_id]
        member.owner = True

        #update all users in the lobby with the new owner
        updateEvent = tbmatch.event_pb2.Event()
        updateEvent.type = tbmatch.event_pb2.Event.E_LOBBY_UPDATE
        updateEvent.lobby_update.lobby_id = self.lobby_id
        updateEvent.lobby_update.queue.extend(self.queue)
        member.EncodeState(updateEvent.lobby_update.update.add())
        
        for m in self.members.values():
            m.user.SendEvent(updateEvent)

    def AddUser(self, user):
        member = LobbyMember(user, self)
        self.members[user.user_id] = member

        # add them to the back of the queue, too
        self.queue.append(user.user_id)

        # if new user is only user, set as owner
        if len(self.members) == 1:
            member.owner = True
            self.owner_user_id = user.user_id

        # tell the new user to join the lobby
        joinEvent = tbmatch.event_pb2.Event()
        joinEvent.type = tbmatch.event_pb2.Event.E_LOBBY_JOIN
        joinEvent.lobby_join.lobby.CopyFrom(self.EncodeState())
        user.SendEvent(joinEvent)

        #tell existing users to update the lobby
        updateEvent = tbmatch.event_pb2.Event()
        updateEvent.type = tbmatch.event_pb2.Event.E_LOBBY_UPDATE
        updateEvent.lobby_update.lobby_id = self.lobby_id
        updateEvent.lobby_update.queue.extend(self.queue)
        member.EncodeState(updateEvent.lobby_update.update.add())
        
        for m in self.members.values():
            if user.user_id != m.user.user_id:
                m.user.SendEvent(updateEvent)

    def RemoveUser(self, user):
        # remove user from member list and from queue
        self.members.pop(user.user_id, None)
        self.queue.remove(user.user_id)
        
        # if user who left was owner, assign new owner for lobby
        if user.user_id == self.owner_user_id and len(self.members) > 0:
                self.SetOwner(self.members.itervalues().next().user)

        # tell the existing user to leave the lobby
        leaveEvent = tbmatch.event_pb2.Event()
        leaveEvent.type = tbmatch.event_pb2.Event.E_LOBBY_LEAVE
        leaveEvent.lobby_leave.lobby_id = self.lobby_id
        leaveEvent.lobby_leave.reason = tbmatch.event_pb2.LobbyLeaveEvent.LEFT
        user.SendEvent(leaveEvent)

        #tell existing users to update the lobby
        updateEvent = tbmatch.event_pb2.Event()
        updateEvent.type = tbmatch.event_pb2.Event.E_LOBBY_UPDATE
        updateEvent.lobby_update.lobby_id = self.lobby_id
        updateEvent.lobby_update.queue.extend(self.queue)
        updateEvent.lobby_update.removed.extend([user.user_id])
        
        for m in self.members.values():
            if user.user_id != m.user.user_id:
                m.user.SendEvent(updateEvent)

    def GetNumberOfUsers(self):
        return len(self.members)

    def SetUserReady(self, user, ready, character):
        self.members[user.user_id].ready = ready
        self.members[user.user_id].character = character

        event = tbmatch.event_pb2.Event()
        event.type = tbmatch.event_pb2.Event.E_LOBBY_UPDATE
        event.lobby_update.lobby_id = self.lobby_id
        self.members[user.user_id].EncodeState(event.lobby_update.update.add())

        for m in self.members.values():
            m.user.SendEvent(event)

    def StartMatchIfReady(self):
        if len(self.members) < 2:
            return
        
        p1 = self.members[self.queue[0]]
        p2 = self.members[self.queue[1]]
        
        if not p1.ready or not p2.ready:
            return
        
        # found a match
        match_id = server.GetNextUniqueId()

        # create intermediate proto structures
        game_config = server.models.match.CreateGameConfig(match_id, p1.user, p1.character, p2.user, p2.character)

        game_session = server.models.match.CreateGameSessionRequest(p1.character, p2.character)
        p1port, p2port = server.portal.StartGameSession(game_session, game_config, p1.user, p2.user)

        game_endpoint_config1 = server.models.match.CreateGameEndpointConfig(0, p1port, game_session.spec[0].secret)
        game_endpoint_config2 = server.models.match.CreateGameEndpointConfig(1, p2port, game_session.spec[1].secret)

        # send lobby match start events to both players
        event1 = tbmatch.event_pb2.Event()
        event1.type = tbmatch.event_pb2.Event.E_LOBBY_MATCH_START
        event1.lobby_match_start.lobby_id = self.lobby_id
        event1.lobby_match_start.match_id = match_id
        event1.lobby_match_start.config.CopyFrom(game_config)
        event1.lobby_match_start.endpoint.CopyFrom(game_endpoint_config1)
        p1.user.SendEvent(event1)

        event2 = tbmatch.event_pb2.Event()
        event2.type = tbmatch.event_pb2.Event.E_LOBBY_MATCH_START
        event2.lobby_match_start.lobby_id = self.lobby_id
        event2.lobby_match_start.match_id = match_id
        event2.lobby_match_start.config.CopyFrom(game_config)
        event2.lobby_match_start.endpoint.CopyFrom(game_endpoint_config2)
        p2.user.SendEvent(event2)

class Lobbies(object):
    def __init__(self):
        self.lobbies = {}

    def CreateLobby(self, name, owner):
        lobby = Lobby(name)
        self.lobbies[lobby.lobby_id] = lobby
        return lobby            

    def GetLobby(self, lobby_id):
        return self.lobbies[lobby_id]

    def FindLobbyWithUser(self, user):
        for _, lobby in self.lobbies.iteritems():
            if user.user_id in lobby.members:
                return lobby
        return lobby

    def FindLobbyWithCode(self, code):
        for _, lobby in self.lobbies.iteritems():
            if lobby.join_code.lower() == code.lower():
                return lobby

    def RemoveUserFromLobby(self, user):
        lobby = self.FindLobbyWithUser(user)
        if lobby:
            lobby.RemoveUser(user)

        # delete lobby if there are no users in it
        if lobby.GetNumberOfUsers() == 0:
            self.lobbies.pop(lobby.lobby_id, None)
