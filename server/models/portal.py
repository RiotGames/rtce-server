"""
portal.py

The portal is a UDP / TCP endpoint used for ping test and spectator support.`
"""

import time
import errno
import socket
import struct
import random
import datetime
import logging
import tornado.ioloop
import tbmatch.event_pb2
import tbportal.portal_pb2

import server
import server.config
from tornado.platform.auto import set_close_exec

# TODO: this is an in-progress implementation.  

PORTAL_VERSION = 0x8012

MSG_PING_READY = 67
MSG_PING = 68
MSG_PEER_PING_CONFIRM = 69
MSG_HANDSHAKE_REQUEST = 106
MSG_HANDSHAKE_REPLY = 107
MSG_HANDSHAKE_REPORT = 108
MSG_TEST_FOR_ECHO = 109
MSG_ECHO_CONFIRM = 110
MSG_GAME_PROGRESS_REPORT = 111
MSG_GAME_INPUT = 112
MSG_GAME_INPUT_ACK = 113
MSG_VARIANT_CHANGE_REQUEST = 115
MSG_VARIANT_CHANGE_REPLY = 116
MSG_GOODBYE = 127
MSG_GAME_LOAD_PROGRESS = 137

MSGS = {
    MSG_PING_READY : 'MSG_PING_READY',
    MSG_PING  : 'MSG_PING',
    MSG_PEER_PING_CONFIRM : 'MSG_PEER_PING_CONFIRM',
    MSG_HANDSHAKE_REQUEST : 'MSG_HANDSHAKE_REQUEST',
    MSG_HANDSHAKE_REPLY : 'MSG_HANDSHAKE_REPLY',
    MSG_HANDSHAKE_REPORT : 'MSG_HANDSHAKE_REPORT',
    MSG_TEST_FOR_ECHO : 'MSG_TEST_FOR_ECHO',
    MSG_ECHO_CONFIRM : 'MSG_ECHO_CONFIRM',
    MSG_GAME_PROGRESS_REPORT : 'MSG_GAME_PROGRESS_REPORT',
    MSG_GAME_INPUT : 'MSG_GAME_INPUT',
    MSG_GAME_INPUT_ACK : 'MSG_GAME_INPUT_ACK',
    MSG_VARIANT_CHANGE_REQUEST : 'MSG_VARIANT_CHANGE_REQUEST',
    MSG_VARIANT_CHANGE_REPLY : 'MSG_VARIANT_CHANGE_REPLY',
    MSG_GOODBYE : 'MSG_GOODBYE',
    MSG_GAME_LOAD_PROGRESS : 'MSG_GAME_LOAD_PROGRESS',
}
THROTTLE_MSG_LOGS = [ MSG_GAME_INPUT, MSG_GAME_PROGRESS_REPORT ]

STATE_INIT = 'STATE_INIT'
STATE_HANDSHAKE = 'STATE_HANDSHAKE'
STATE_HANDSHAKE_REPORT = 'STATE_HANDSHAKE_REPORT'
STATE_GAME = 'STATE_GAME'
STATE_GAME_PENDING = 'STATE_GAME_PENDING'
STATE_CLOSING = 'STATE_CLOSING'
STATE_CLOSED = 'STATE_CLOSED'
STATE_TIMED_OUT = 'STATE_TIMED_OUT'

HANDSHAKE_TIMEOUT = 'HANDSHAKE_TIMEOUT'
INACTIVE_DISCONNECT = 'INACTIVE_DISCONNECT'
GOODBYE_DISCONNECT = 'GOODBYE_DISCONNECT'

GOODBYE_INVALID = 'GOODBYE_INVALID'
GOODBYE_MATCH_OVER = 'GOODBYE_MATCH_OVER'
GOODBYE_GAME_OVER = 'GOODBYE_GAME_OVER'

class SocketServer(object):
    def __init__(self, portal, name):
        self.portal = portal
        self.name = name
        self.port = portal.AcquirePort()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        self.sock.bind((server.config.hostname, self.port))
        set_close_exec(self.sock.fileno())

        self.Log('starting socket server. fd %d' % self.sock.fileno())
        def OnSocketReady(fd, events):
            self.OnSocketReady(fd, events)

        server.ioloop.add_handler(self.sock.fileno(), OnSocketReady, server.ioloop.READ)

    def Log(self, s):
        logging.debug('[%s port %s] %s' % (self.name, self.port, s))

    def StopServing(self):      
        self.Log('stopping socket server')
        server.ioloop.remove_handler(self.sock.fileno())
        self.sock.close()
        self.portal.ReleasePort(self.port)
        self.peer_addr = None
        self.sock = None
        self.port = None

    def OnSocketReady(self, fd, events):
        while self.sock:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.error, e:
                if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                    return
                raise
            self.peer_addr = addr
            self.OnRead(data, addr)
            break
    
    def OnRead(self, data, addr):
        # print 'got %d bytes from %s' % (len(data), str(addr))
        header, payload = data[:3], data[3:]
        version, msg = struct.unpack('HB', header)        

        if msg not in THROTTLE_MSG_LOGS:
            self.Log('recv version:0x%0x, msg:%s payload len:%d' % (version, MSGS.get(msg, str(msg)), len(payload)))

        if version != PORTAL_VERSION:
            return
        
        self.OnPayload(msg, payload, addr)
    
    def SendTo(self, addr, msg, payload):
        hdr = struct.pack('HB', PORTAL_VERSION, msg)
        self.Log('send version:0x%0x, msg:%s payload len:%d' % (PORTAL_VERSION, MSGS.get(msg, str(msg)), len(payload)))
        self.sock.sendto(hdr + payload, addr)        

class TimerStore(object):
    def __init__(self, logcb):
        self.logcb = logcb
        self.timers = {}

    def Start(self, name, duration, cb):
        if type(duration) == str:
            timeout_ms = getattr(server.config.game_session_config, duration)
        else:
            timeout_ms = duration
        assert type(timeout_ms) == int or type(timeout_ms) == float and timeout_ms > 0

        self.logcb('starting timer {0}'.format(name))
        self.Stop(name)
        timeout = datetime.timedelta(milliseconds=timeout_ms)

        def callback():
            self.logcb('firing timer {0}'.format(name))
            cb()

        self.timers[name] = server.ioloop.add_timeout(timeout, callback)

    def Stop(self, name):
        self.logcb('stopping timer {0}'.format(name))       
        timer = self.timers.get(name)
        if timer:
            server.ioloop.remove_timeout(timer)
            self.timers[name] = None

    def StopAll(self):
        for name, timer in self.timers.iteritems():
            self.logcb('stopping timer {0}'.format(name))       
            server.ioloop.remove_timeout(timer)
        self.timers = {}

class GameChannel(SocketServer):
    def __init__(self, session, portal, slot, user, client_spec):
        SocketServer.__init__(self, portal, 'chan %s %s' % (slot, user.handle))
        self.session = session
        self.client_spec = client_spec
        self.character_spec = tbmatch.match_pb2.CharacterSpec()
        self.character_spec.CopyFrom(client_spec.character)
        self.slot = slot
        self.user = user
        self.connected = False
        self.active = True
        self.got_new_variants = False
        self.need_another_game = False
        self.handshake_random = None
        self.handshake_status = None        
        self.sender = None
        self.mapped_port = None
        self.local_address = None
        self.local_port = None
        self.peer = None
        self.game_recv_count = 0
        self.total_recv_count = 0
        self.claimed_losses = 0
        self.claimed_wins = 0
        self.claimed_draws = 0
        self.inactive_timeout_timer = None
        self.send_variant_change_reply_timer = None
        self.last_game_report = tbmatch.match_pb2.GameReport()
        self.report_timeout_timer = tornado.ioloop.PeriodicCallback(lambda: self.ReportTimeoutCb(), server.config.game_session_config.handshake_report_timeout_ms)

    def StopServing(self):
        SocketServer.StopServing(self)
        self.report_timeout_timer.stop()
        
    def OnPayload(self, msg, payload, addr):
        self.session.OnPayload(self, msg, payload, addr)
    
    def IsConnected(self):
        return self.connected

    def IsHandshakeReported(self):
        return self.handshake_status != None

    def AuthenticateClient(self, msg, payload, addr):
        if msg != MSG_HANDSHAKE_REQUEST:
            self.Log('not a handshake request')
            return False

        secret, random_request, mapped_port, la1, la2, la3, la4, local_port = struct.unpack('<QLHLLLLH', payload)
        if secret != self.client_spec.secret:
            self.Log('bad secret 0x%08x needed 0x%08x' % (secret, self.client_spec.secret))
            return False

        self.Log('authenticated sender: %s' % str(addr))
        self.sender = addr
        self.handshake_random = random_request
        self.mapped_port = mapped_port
        self.local_port = local_port
        self.local_address = (la1, la2, la3, la4)
        self.connected = True
        return True

    def AwaitHandshakeReport(self):
        self.report_timeout_timer.start()

    def SendHandshakeReply(self, peer):
        peer_addr, peer_port = peer.sender
        packed_ip = socket.inet_aton(peer_addr)
        peer_addr_int = struct.unpack("!L", packed_ip)[0]

        self.Log('peer internet addr 0x%08x' % peer_addr_int)
        peer_addr_int = socket.htonl(peer_addr_int)
        peer_port = socket.htons(peer_port)

        payload = struct.pack('LLLHHLLLLH',
            self.handshake_random,
            peer.handshake_random,
            peer_addr_int,
            peer_port,
            peer.mapped_port,
            peer.local_address[0],
            peer.local_address[1],
            peer.local_address[2],
            peer.local_address[3],
            peer.local_port
        )

        self.SendTo(self.sender, MSG_HANDSHAKE_REPLY, payload)

    def ValidateHandshakeReport(self, payload, addr):
        assert self.handshake_status == None

        handshake_status, min_ping_ms, avg_ping_ms, max_ping_ms = struct.unpack('<BHHH', payload)
        self.handshake_status = handshake_status
        self.report_timeout_timer.stop()
        return True

    def GetHandshakeStatus(self):
        return self.handshake_status

    def PacketReceived(self, is_game_packet):
        self.total_recv_count += 1
        if is_game_packet:
            self.game_recv_count += 1

        if self.active:
            self.StopInactiveTimeout()
            self.StartInactiveTimeout()

    def ValidateVariantChange(self, payload):
        assert self.need_another_game
        assert self.connected
        assert not self.got_new_variants

        new_char_spec = tbmatch.match_pb2.CharacterSpec()
        variants_size = struct.unpack('H', payload[:2])[0]
        try:
            new_char_spec.ParseFromString(payload[2:2+variants_size])
        except:
            log.Error('invalid proto for variant change.')
            return False
    
        if new_char_spec.type_name != self.character_spec.type_name:
            self.Log('variant change: invalid attempt to change character')
            return False

        self.character_spec.secondary_meter = new_char_spec.secondary_meter
        self.character_spec.variants.CopyFrom(new_char_spec.variants)
        self.got_new_variants = True
        return True

    def ReportTimeoutCb(self):
        self.session.NotifyTimeout(HANDSHAKE_TIMEOUT)

    def NewGameStarted(self):
        self.game_recv_count = 0
        self.StartInactiveTimeout()

    def StartInactiveTimeout(self):
        if self.active and not self.inactive_timeout_timer:
            timeout_ms = server.config.game_session_config.handshake_reply_interval_ms
            self.inactive_timeout_timer = server.ioloop.add_timeout(datetime.timedelta(milliseconds=timeout_ms), lambda: self.InactiveTimeoutCb())
            
    def StopInactiveTimeout(self):
        if self.inactive_timeout_timer:
            server.ioloop.remove_timeout(self.inactive_timeout_timer)
            self.inactive_timeout_timer = None
            
    def InactiveTimeoutCb(self):
        self.Log('inactive timeout fired')
        self.session.NotifyTimeout(INACTIVE_DISCONNECT)

    def AddProgressReport(self, frame_count, ping_ms, max_ping_ms, min_ping_ms, fps):
        # do we really care?  maybe?
        pass

    def GetClaimedFinished(self):
        return self.claimed_draws + self.claimed_losses + self.claimed_wins

    def ValidateGoodBye(self, payload):
        assert self.connected
        assert not self.need_another_game

        # channel going away.  stop checking for inactivity.
        self.active = False
        self.StopInactiveTimeout()

        # Reset since we're not in variant change state
        self.got_new_variants = False
        outcome_size = struct.unpack('H', payload[:2])[0]
        try:
            self.last_game_report.ParseFromString(payload[2:2+outcome_size])
        except:
            log.Error('goodbye: invalid proto for game report.')
            return GOODBYE_INVALID

        if self.last_game_report.win_slot in [0, 1]:
            slot = 0 if self.slot == 'p1' else 1
            if self.last_game_report.win_slot == slot:
                self.claimed_wins += 1
            else:
                self.claimed_losses += 1
        else:
            if self.last_game_report.draw:
                self.claimed_draws += 1
        
        games_to_win = server.config.game_session_config.games_to_win
        max_games = games_to_win * 2 - 1
        if self.claimed_wins > games_to_win or self.claimed_losses > games_to_win or self.GetClaimedFinished() > max_games:
           self.Log('goodbye: too many games reported (wins:{0} losses:{1} draws:{2}'.format(self.claimed_wins, self.claimed_losses, self.claimed_draws))
           return GOODBYE_INVALID
    
        result = GOODBYE_INVALID
        if self.claimed_wins == games_to_win or self.claimed_losses == games_to_win or self.GetClaimedFinished() == max_games:
            result = GOODBYE_MATCH_OVER
        else:
            self.need_another_game = True
            result = GOODBYE_GAME_OVER

        self.Log('returnining {0} from ValidateGoodbye'.format(result))
        return result

    def CompareClaims(self, other):
        return self.claimed_wins == other.claimed_losses and \
               self.claimed_losses == other.claimed_wins and \
               self.claimed_draws == other.claimed_draws

class GameSession(object):
    def __init__(self, portal, game_session, game_config, p1, p2):
        self.state = STATE_INIT
        self.handshake_reply_count = 0
        self.variant_change_reply_count = 0
        self.finished_games = 0
        self.send_variant_change_reply_timer = None
        self.match_report = tbmatch.match_pb2.MatchReport()
        self.next_game_config = None
        self.successful_match = False
        self.match_id = game_config.match_id
        self.timers = TimerStore(lambda s: self.Log(s))
        self.p1 = GameChannel(self, portal, 'p1', p1, game_session.spec[0])
        self.p2 = GameChannel(self, portal, 'p2', p2, game_session.spec[1])
        self.TransitionToState(STATE_HANDSHAKE)

    def Log(self, s):
        logging.debug('[session %s vs %s] %s' % (self.p1.user.handle, self.p2.user.handle, s))

    def Close(self):
        assert self.state != STATE_CLOSED
        self.TransitionToState(STATE_CLOSED)

    def OnPayload(self, channel, msg, payload, addr):
        if self.state not in [STATE_HANDSHAKE, STATE_HANDSHAKE_REPORT, STATE_GAME, STATE_GAME_PENDING, STATE_CLOSING, STATE_TIMED_OUT]:
            return
        
        if channel == self.p1:
            recv_channel  = self.p1
            other_channel = self.p2
        else:
            recv_channel  = self.p2
            other_channel = self.p1
            
        if msg not in THROTTLE_MSG_LOGS:
            self.Log('received {0} msg in state {1} from {2}'.format(MSGS.get(msg, str(msg)), self.state, recv_channel.slot))

        if self.state == STATE_HANDSHAKE:
            if recv_channel.IsConnected():
                return
            if recv_channel.AuthenticateClient(msg, payload, addr):
                if other_channel.IsConnected():
                    self.TransitionToState(STATE_HANDSHAKE_REPORT)
                    return
        elif self.state == STATE_HANDSHAKE_REPORT:
            if recv_channel.IsHandshakeReported():
                return
            if recv_channel.ValidateHandshakeReport(payload, addr):
                if other_channel.IsHandshakeReported():
                    other_handshake_status = other_channel.GetHandshakeStatus()
                    recv_handshake_status = recv_channel.GetHandshakeStatus() 
                    if other_handshake_status != recv_handshake_status:
                        logging.error('handshake status disagree: {0}, {1}', recv_handshake_status, other_handshake_status)
                        self.NotifyTimeout(HANDSHAKE_TIMEOUT)
                        return
                    if recv_handshake_status == tbportal.portal_pb2.GameSessionReport.OK:
                        logging.debug('handshake complete, session active')
                        self.TransitionToState(STATE_GAME)
                        return
                    elif recv_handshake_status == tbportal.portal_pb2.GameSessionReport.HIGH_PING:
                        logging.debug('handshake failed due to high ping')
                    
                    self.handshake_status = recv_handshake_status
                    self.NotifyTimeout(HANDSHAKE_FAIL)
        elif self.state == STATE_GAME:
            # Still waiting on opponent to transition to STATE_GAME_PENDING.
            recv_channel.PacketReceived(False)
            if recv_channel.need_another_game:
                return

            # Don't pass server protocol packets through to opponent
            if msg == MSG_GAME_INPUT:
                recv_channel.PacketReceived(True)
                self.HandleInput(recv_channel, payload)
                return
            elif msg == MSG_GAME_PROGRESS_REPORT:
                frame_count, ping_ms, max_ping_ms, min_ping_ms, fps = struct.unpack('LHHHH', payload)
                recv_channel.AddProgressReport(frame_count, ping_ms, max_ping_ms, min_ping_ms, fps)
                return
            elif msg == MSG_GOODBYE:                
                self.HandleGoodbyeInGame(recv_channel, other_channel, payload)
                return

            recv_channel.PacketReceived(True)
            # Stop handshaking if we've received 1 game packets from all clients
            if recv_channel.game_recv_count > 0 and other_channel.game_recv_count > 0:
                logging.debug('game running.  end var change reply')
                self.CancelHandshakeComplete()
                
        elif self.state == STATE_GAME_PENDING:
            # aknowledge packet no matter what, since the channel is active
            recv_channel.PacketReceived(False)

            # Still waiting on opponent to transition to STATE_GAME_PENDING.
            if recv_channel.got_new_variants:
                return

            if msg == MSG_GAME_INPUT:
                self.HandleInput(recv_channel, payload)
                return
            elif msg == MSG_VARIANT_CHANGE_REQUEST:
                if recv_channel.ValidateVariantChange(payload):
                    if not other_channel.got_new_variants:
                        self.Log('got new variants for {0}.  waiting for {1}.'.format(recv_channel.slot, other_channel.slot))
                    else:
                        self.Log('got new variants for both players. launching game.')
                        self.VariantsChangeTimeoutCb()

        elif self.state == STATE_CLOSING:
            recv_channel.PacketReceived(False)
            if msg == MSG_GAME_INPUT:
                self.HandleInput(recv_channel, payload)
            elif msg == MSG_GOODBYE:
                self.HandleGoodbyeInClosing(recv_channel, other_channel, payload)
        elif self.state == STATE_TIMED_OUT:
            # Continue handling inputs for a few seconds after we're done.
            if msg == MSG_GAME_INPUT:
                self.HandleInput(recv_channel, payload)

    def HandleInput(self, channel, payload):
        # this is where we'd do spectator stuff
        pass
    
    def HandleGoodbyeInGame(self, recv_channel, other_channel, payload):
        result = recv_channel.ValidateGoodBye(payload)        
        if result == GOODBYE_MATCH_OVER:
            if other_channel.need_another_game:
                self.AddGameToMatchRecord()
                self.ExitGame()
            else:
                self.TransitionToState(STATE_CLOSING)
            self.SendGameOver(recv_channel)
            self.SendMatchOver(recv_channel)
        elif result == GOODBYE_GAME_OVER:
            self.Log('game complete for channel {0}.  waiting for {1}'.format(recv_channel.user.handle, other_channel.user.handle))
            if other_channel.need_another_game:
                if self.AddGameToMatchRecord():
                    self.Log('game complete, need another game, transitioning to game pending')
                    self.TransitionToState(STATE_GAME_PENDING)
                else:
                    self.ExitGame()
            else:
                self.timers.Start('goodbye', 'goodbye_timeout_ms', lambda: self.GoodbyeTimeoutCb())
            self.SendGameOver(recv_channel)

    def HandleGoodbyeInClosing(self, recv_channel, other_channel, payload):
        if recv_channel.GetClaimedFinished() > other_channel.GetClaimedFinished():
            # Ignore extra goodbye packets coming from the channel
            # that triggered the move to CLOSING state.
            return

        result = recv_channel.ValidateGoodBye(payload)        
        if result == GOODBYE_MATCH_OVER:
            if self.AddGameToMatchRecord():
                # at this point we trust that the clients reported things correctly
                self.match_report.draw = self.p1.claimed_wins == self.p1.claimed_wins
                self.match_report.win_slot = self.p1.claimed_wins > self.p1.claimed_wins and 0 or 1
                self.match_report.players_agree = True
            self.SendGameOver(recv_channel)
        elif result == GOODBYE_GAME_OVER:
            # One player said match over, the other said game over.
            self.match_report.players_agree = False

        self.SendMatchOver(recv_channel)
        self.ExitGame()

    def AddGameToMatchRecord(self):
        self.finished_games += 1
        self.Log('finished {0} games.'.format(self.finished_games))
        if self.p1.CompareClaims(self.p2) and self.finished_games == self.p1.GetClaimedFinished():
            # now would be a good time to notify some observer or adjust elo or whatever.
            self.Log('players agree on match outcome')
            self.match_report.players_agree = True
            return True

        self.Log('players disagree on match outcome. p1:{0}/{1}/{2} p2:{3}/{4}/{5}'.format(
            self.p1.claimed_wins, self.p1.claimed_losses, self.p1.claimed_draws,
            self.p2.claimed_wins, self.p2.claimed_losses, self.p2.claimed_draws
        ))
        self.match_report.players_agree = False
        return False

    def SendGameOver(self, channel):
        gameOverEvent = tbmatch.event_pb2.Event()
        gameOverEvent.type = tbmatch.event_pb2.Event.E_GAME_OVER
        gameOverEvent.game_over.match_id = self.match_id
        gameOverEvent.game_over.report.CopyFrom(channel.last_game_report)
        channel.user.SendEvent(gameOverEvent)
        
    def SendMatchOver(self, channel):
        matchOverEvent = tbmatch.event_pb2.Event()
        matchOverEvent.type = tbmatch.event_pb2.Event.E_MATCH_OVER
        matchOverEvent.match_over.status = tbmatch.event_pb2.MatchOverEvent.VALID
        matchOverEvent.match_over.match_id = self.match_id
        matchOverEvent.match_over.win_slot = channel.last_game_report.win_slot
        matchOverEvent.match_over.draw = channel.last_game_report.draw
        channel.user.SendEvent(matchOverEvent)

    def SendMatchAbandoned(self, channel):
        matchAbandonedEvent = tbmatch.event_pb2.Event()
        matchAbandonedEvent.type = tbmatch.event_pb2.Event.E_MATCH_ABANDONED
        matchAbandonedEvent.match_abandoned.match_id = self.match_id
        channel.user.SendEvent(matchAbandonedEvent)
        
    def ExitGame(self):
        self.successful_match = True
        self.TransitionToState(STATE_TIMED_OUT)

    def TransitionToState(self, state):
        self.Log('transitioning from {0} to {1}'.format(self.state, state))
        self.ExitState(self.state)
        self.EnterState(state)

    def EnterState(self, state):
        start_state, self.state = self.state, state
        if self.state == STATE_HANDSHAKE_REPORT:
            # Start sending handshake reply packets
            self.SendHandshakeReplyCb()
            self.p1.AwaitHandshakeReport()
            self.p2.AwaitHandshakeReport()
        elif self.state == STATE_GAME:
            self.p1.NewGameStarted()
            self.p2.NewGameStarted()
            if start_state == STATE_HANDSHAKE_REPORT:
                # send Event_Type_E_MATCH_CONNECTED to observers
                pass
            elif start_state == STATE_GAME or start_state == STATE_GAME_PENDING:
                # Start sending variant reply packets.
                self.variant_change_reply_count = 0
                self.SendVariantChangeReplyCb()
                # send Event_Type_E_GAME_BEGIN to observers
        elif self.state == STATE_GAME_PENDING:
            # set timeout for variant selection
            self.timers.Start('variant_change', 'var_change_timeout_ms', lambda: self.VariantsChangeTimeoutCb())
            pass
        elif self.state == STATE_CLOSING:
            # set timeout for other goodbye packet
            pass
        elif self.state == STATE_TIMED_OUT:
            if self.successful_match:
                # wait a few seconds to catch any lingering input reports
                self.timers.Start('linger', 'input_linger_timeout_ms', lambda: self.Close)
            else:
                self.Close()
        elif self.state == STATE_CLOSED:
            self.timers.StopAll()
            self.portal.RemoveSocketServer(self.p1)
            self.portal.RemoveSocketServer(self.p2)
            self.Log('closed (p1 recv:{0} p2 recv:{1}'.format(self.p1.total_recv_count, self.p2.total_recv_count))
            # TODO: make sure this object gets destroyed or something

    def ExitState(self, state):
        if state == STATE_HANDSHAKE_REPORT:
            self.CancelHandshakeComplete()
        elif state == STATE_GAME:
            self.timers.Stop('goodbye')
        elif state == STATE_GAME_PENDING:
            self.timers.Stop('variant_change')
    
    def SendHandshakeReplyCb(self):
        self.p1.SendHandshakeReply(self.p2)
        self.p2.SendHandshakeReply(self.p1)
        
        max_handshake_replies = server.config.game_session_config.max_handshake_replies
        self.handshake_reply_count += 1
        self.Log('got handshake reply %d of %d' % (self.handshake_reply_count, max_handshake_replies))

        if self.handshake_reply_count < max_handshake_replies:
            timeout_ms = server.config.game_session_config.handshake_reply_interval_ms
            self.send_handshake_reply_timer = server.ioloop.add_timeout(datetime.timedelta(milliseconds=timeout_ms), lambda: self.SendHandshakeReplyCb())
        else:
            self.Log('timeout handshake reply')
            self.CancelHandshakeComplete()

    def CancelHandshakeComplete(self):
        # TODO: conver this to a timer store object
        if self.send_handshake_reply_timer:
            server.ioloop.remove_timeout(self.send_handshake_reply_timer)
            self.send_handshake_reply_timer = None
        
    def NotifyTimeout(self, reason):
        self.Log('sending abandoned event to players')
        self.SendMatchAbandoned(self.p1)
        self.SendMatchAbandoned(self.p2)
        pass

    def SendVariantChangeReplyCb(self):
        next_config = self.next_game_config.SerializeToString()
        payload = struct.pack('H', len(next_config)) + next_config
        self.p1.SendTo(self.p1.peer_addr, MSG_VARIANT_CHANGE_REPLY, payload)
        self.p2.SendTo(self.p2.peer_addr, MSG_VARIANT_CHANGE_REPLY, payload)
        self.p1.need_another_game = False
        self.p2.need_another_game = False
        self.variant_change_reply_count += 1

        self.timers.Stop('send_variant_change_reply')
        if self.variant_change_reply_count < server.config.game_session_config.max_var_change_replies:
            self.timers.Start('send_variant_change_reply', 'var_change_reply_interval_ms', lambda: self.SendVariantChangeReplyCb())
        else:
            self.Log('timeout variant change reply')

    
    def VariantsChangeTimeoutCb(self):
        self.next_game_config = tbmatch.match_pb2.NextGameConfig()
        self.next_game_config.character_spec.add().CopyFrom(self.p1.character_spec)
        self.next_game_config.character_spec.add().CopyFrom(self.p2.character_spec)
        self.TransitionToState(STATE_GAME)

    def GoodbyeTimeoutCb(self):
        self.Log('goodbye timeout expired')
        self.NotifyTimeout(GOODBYE_DISCONNECT)

class PingTest(SocketServer):
    def __init__(self, portal, user, client_spec):
        SocketServer.__init__(self, portal, 'pingtest')
        self.state = 'wait'
        self.user = user
        self.client_spec = client_spec
        self.timer = server.ioloop.add_timeout(datetime.timedelta(seconds=100), lambda: self.OnTimeout())
        self.send_count = 0
        self.recv_count = 0
        self.success = False
        self.records = []
        for i in xrange(server.config.portal_ping_count):
            self.records.append({ 'rand': random.randint(0, 65535) })

    def StopServing(self):
        SocketServer.StopServing(self)

        event = tbmatch.event_pb2.Event()
        event.type = tbmatch.event_pb2.Event.E_PING_TEST_COMPLETE
        event.ping_test_complete.success = self.success
        self.user.SendEvent(event)
        server.ioloop.remove_timeout(self.timer)

    def OnTimeout(self):
        self.portal.RemoveSocketServer(self)

    def OnPayload(self, msg, payload, addr):
        if self.state == 'wait' and msg == MSG_PING_READY:
            self.OnPingReady(payload, addr)
            return

        if self.state == 'test' and msg == MSG_PING:
            self.OnPing(payload, addr)
            return

    def OnPingReady(self, payload, addr):
        secret, client_rand = struct.unpack('QH', payload)
        if self.client_spec.secret != secret:
            return
        
        self.state = 'test'
        self.sender = addr
        self.last_client_rand = client_rand
        self.SendPing(addr)

    def OnPing(self, payload, addr):
        client_rand, server_rand = struct.unpack('HH', payload)
        self.last_client_rand = client_rand
        for record in self.records:
            sent = record.get('sent')
            if record['rand'] == server_rand and sent:
                self.recv_count += 1
                if self.recv_count == len(self.records):
                    self.success = True
                    self.portal.RemoveSocketServer(self)
                self.SendPing(addr)
                return

    def SendPing(self, addr):
        if self.send_count >= len(self.records):
            # Done sending. Timeout after one more wait timeout
            return
                
        record = self.records[self.send_count]
        server_random = record['rand']
        record['sent'] = time.time()

        self.SendTo(addr, MSG_PING, struct.pack('HH', self.last_client_rand, server_random))
        self.send_count += 1


class Portal(object):
    def __init__(self):
        self.socket_servers = {}
        self.free_ports = range(server.config.portal_port_base,
                                server.config.portal_port_base + server.config.portal_port_range)

    def AcquirePort(self):
        return self.free_ports.pop(0)

    def ReleasePort(self, port):
        self.free_ports.append(port)

    def StartPingTest(self, user, client_spec):
        p = PingTest(self, user, client_spec)
        self.AddSocketServer(p)
        return p

    def StartGameSession(self, game_session, game_config, p1, p2):
        s = GameSession(self, game_session, game_config, p1, p2)
        return s.p1.port, s.p2.port

    def AddSocketServer(self, server):
        assert server.port
        self.socket_servers[server.port] = server

    def RemoveSocketServer(self, server):
        assert server.port
        server.StopServing()
        self.socket_servers[server.port] = None


