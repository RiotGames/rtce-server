import server
import server.rpc
import server.config
import tbmatch.event_pb2
import uuid

@server.rpc.HandleRpc('CreateLobby')
def CreateLobby(request, response, handler):
    """
    Create a new lobby and join it, with the creator as owner.
	    Fails if user is already in a lobby.
	    Success confirmed by LobbyJoin event.
    """
    user = server.users.GetCurrentUser(handler)

    # get the name of the lobby.  the ui doesn't care, but lets shove
    # this in there anyway.
    name = request.name and str(uuid.uuid4())
    lobby = server.lobbies.CreateLobby(name, user)
    
    lobby.AddUser(user)
    lobby.SetOwner(user)

@server.rpc.HandleRpc('LobbySetReady')   
def LobbySetReady(request, response, handler):
    """
    Set the ready state for the current user.
    """
    user = server.users.GetCurrentUser(handler)

    lobby = server.lobbies.FindLobbyWithUser(user)
    if lobby:
        lobby.SetUserReady(user, request.ready, request.character)

    # check to see if both players are ready, if so start the match
    lobby.StartMatchIfReady()
    
@server.rpc.HandleRpc('GetLobbyJoinCode')
def GetLobbyJoinCode(request, response, handler):
    lobby = server.lobbies.GetLobby(request.lobby_id)
    response.join_code = lobby.join_code

@server.rpc.HandleRpc('JoinLobbyByCode')
def JoinLobbyByCode(request, response, handler):
    """
    Join an existing lobby via a string code inputted by the user.
    """

    user = server.users.GetCurrentUser(handler)

    code = request.code
    lobby = server.lobbies.FindLobbyWithCode(code)
    if lobby:
        lobby.AddUser(user)

@server.rpc.HandleRpc('LeaveLobby')
def LeaveLobby(request, response, handler):
    """
    Leave an existing lobby.
    """

    user = server.users.GetCurrentUser(handler)
    server.lobbies.RemoveUserFromLobby(user)
        
