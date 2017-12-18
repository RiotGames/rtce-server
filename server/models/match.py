"""
match.py

Match related events.
"""

import server
import server.config
import tbmatch.event_pb2
import tbmatch.match_pb2
import tbportal.portal_pb2

def CreateGameSessionRequest(p1_character, p2_character):
    game_session = tbportal.portal_pb2.GameSessionRequest()
    p1_session = game_session.spec.add()
    p1_session.secret = server.GetNewSecret()
    p1_session.character.CopyFrom(p1_character)

    p2_session = game_session.spec.add()
    p2_session.secret = server.GetNewSecret()
    p2_session.character.CopyFrom(p2_character)

    return game_session

#TODO Rename Gameplay options
def CreateGameConfig(match_id, p1, p1_character, p2, p2_character):
    game_config = tbmatch.match_pb2.GameConfig()

    player1 = game_config.player.add()
    player1.user_id = p1.user_id
    player1.handle = p1.handle
    player1.character.CopyFrom(p1_character)

    player2 = game_config.player.add()
    player2.user_id = p2.user_id
    player2.handle = p2.handle
    player2.character.CopyFrom(p2_character)

    game_config.options.CopyFrom(tbmatch.match_pb2.GameOptions())
    game_config.match_id = match_id

    return game_config

def CreateGameEndpointConfig(slot, port, secret):
    game_endpoint_config = tbmatch.match_pb2.GameEndpointConfig()
    game_endpoint_config.slot = slot
    game_endpoint_config.server.host_name = server.config.hostname
    game_endpoint_config.server.port = port
    game_endpoint_config.secret = secret
    game_endpoint_config.ping_score_threshold = 200.0

    return game_endpoint_config

def CreateWaitMatchProgressEvent(
        status,
        match_id = 0, 
        game_config = None, 
        game_endpoint_config = None):
    wait_match_progress = tbmatch.event_pb2.WaitMatchProgressEvent()

    wait_match_progress.status = status
    if match_id:
        wait_match_progress.match_id = match_id 
    if game_config:
        wait_match_progress.config.CopyFrom(game_config)
    if game_endpoint_config:
        wait_match_progress.endpoint.CopyFrom(game_endpoint_config)
    wait_match_progress.users_waiting = 0

    return wait_match_progress
