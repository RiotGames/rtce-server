import requests
import rpc_client
import tbmatch.session_pb2
import google.protobuf.json_format

NEXT_USER_ID = 1

class GameClient(rpc_client.RpcClient):
    def __init__(self, username = None):
        rpc_client.RpcClient.__init__(self)

        if not username:
            global NEXT_USER_ID
            username = 'testuser%03d' % NEXT_USER_ID
            NEXT_USER_ID += 1

        self.username = username
        self.get_event_version = ''
        self.DoLogin()

    def DoLogin(self):
        request = tbmatch.session_pb2.LoginRequest()
        request.login = self.username
        self.Login(request)

        request = tbmatch.session_pb2.GetGameSessionTicketRequest()
        request.game = tbmatch.session_pb2.GT_RISING_THUNDER
        ticket = self.GetGameSessionTicket(request).nonce
        
        self.Logout()

        request = tbmatch.session_pb2.RedeemGameSessionTicketRequest()
        request.nonce = ticket
        request.build_version = '1728'
        request.game = tbmatch.session_pb2.GT_RISING_THUNDER;
        self.RedeemGameSessionTicket(request)

    def DoGetEvents(self):
        request = tbmatch.event_pb2.GetEventRequest()
        request.version = self.get_event_version
        result = self.GetEvent(request)
        if len(result.event) > 0:
            self.get_event_version = str(result.event[-1].event_id)

        return result.event
