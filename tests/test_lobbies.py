import game_client
import tbmatch.lobby_pb2


def test_create_lobby():
    c = game_client.GameClient()
    request = tbmatch.lobby_pb2.CreateLobbyRequest()
    request.type = tbmatch.lobby_pb2.LT_QUEUED
    c.CreateLobby(request)
    c.DoGetEvents()

def test_set_lobby_ready():
    c = game_client.GameClient()
    request = tbmatch.lobby_pb2.CreateLobbyRequest()
    request.type = tbmatch.lobby_pb2.LT_QUEUED
    c.CreateLobby(request)

    request = tbmatch.lobby_pb2.LobbySetReadyRequest()
    request.ready = True
    c.LobbySetReady(request)

    c.DoGetEvents()

def test_join_lobby_code():
    c = game_client.GameClient()
    request = tbmatch.lobby_pb2.CreateLobbyRequest()
    request.type = tbmatch.lobby_pb2.LT_QUEUED
    c.CreateLobby(request)

    request = tbmatch.lobby_pb2.JoinLobbyByCodeRequest()
    request.code = "test"
    c.JoinLobbyByCode(request)

    c.DoGetEvents()