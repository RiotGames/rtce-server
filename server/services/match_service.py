import uuid
import server
import server.rpc
import server.config
import tbportal.portal_pb2

@server.rpc.HandleRpc('PingTest')
def PingTest(request, response, handler):
    user = server.users.GetCurrentUser(handler)

    client_spec = tbportal.portal_pb2.ClientSpec()
    client_spec.secret = server.GetNewSecret()

    ping_test = server.portal.StartPingTest(user, client_spec)
    response.config.server.host_name = server.config.hostname
    response.config.server.port = ping_test.port
    response.config.secret = client_spec.secret

@server.rpc.HandleRpc('GetGameProfile')
def GetGameProfile(request, response, handler):
    user = server.users.GetCurrentUser(handler)
    response.account_id = user.user_id
    response.handle = user.handle
    response.given_name = user.given_name
    response.locale = user.locale
    response.feature_set.CopyFrom(server.config.featureSet)

@server.rpc.HandleRpc('GetRecentGames')
def GetRecentGames(request, response, handler):
    pass

@server.rpc.HandleRpc('UpdatePlayerPreferences')
def UpdatePlayerPreferences(request, response, handler):
    user = server.users.GetCurrentUser(handler)
    user.SetPlayerPreferences(request.updated_prefs)

@server.rpc.HandleRpc('GetMatch')
def GetMatch(request, response, handler):
    user = server.users.GetCurrentUser(handler)
    gameplay_options = request

    server.matchmaker.JoinQueue(user, gameplay_options)

@server.rpc.HandleRpc('CancelGetMatch')
def CancelGetMatch(request, response, handler):
    user = server.users.GetCurrentUser(handler)
    server.matchmaker.LeaveQueue(user)
