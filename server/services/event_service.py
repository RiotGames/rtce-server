import server.rpc
import tbmatch.event_pb2
import tornado.web
import logging

class GetEventHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        request = tbmatch.event_pb2.GetEventRequest()
        request.ParseFromString(self.request.body)
        logging.debug('received GetEvent {0}'.format(str(request)))

        user = server.users.GetCurrentUser(self)        
        if request.version:
            user.RemoveEvents(int(request.version))
        user.SendPendingEvents(self)

@server.rpc.HandleRpc('EventPing')
def PingTest(request, response, handler):
    server.users.GetCurrentUser(handler)
