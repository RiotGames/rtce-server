import server.rpc
import time
import uuid

@server.rpc.HandleRpc('Login')
def Login(request, response, handler):
    pass
    
@server.rpc.HandleRpc('Logout')
def Logout(request, response, handler):
    server.users.DestroySession(handler)
       
@server.rpc.HandleRpc('GetGameSessionTicket')
def GetGameSessionTicket(request, response, handler):
    response.game = request.game
    response.nonce = str(uuid.uuid4())

@server.rpc.HandleRpc('RedeemGameSessionTicket')
def RedeemGameSessionTicket(request, response, handler):
    # TODO:  Remove this sleep statement and instead implement an asynchronous event handler in the same style as GetEvent
    time.sleep(server.config.game_session_ticket_wait_interval_ms)

    session_key = request.nonce
    server.users.CreateSession(handler, session_key)
