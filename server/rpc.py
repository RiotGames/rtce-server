"""
server.py

The Rising Thunder application server layer.  Simply holds the server configuration and
makes it really easy to implement RPCs.  Most of the heavy lifting is done by flask.
"""

import logging
import google.protobuf.json_format

log = logging.getLogger("tornado.general")
log.debug('loading server')

# Create the flask application.  We do this here so scripts which implement RPCs can
# easily get to the flask app via 
#
#   import server
#   server.app       # this is the flask app!
#

_RPC_HANDLERS = {}
def HandleRpc(route):
    """
    Used by RPC implementors to handle an RPC.  Typical usage looks like:

       import server

       @server.HandleRpc('Login')
       def Login(request, response):
           # do something here.

    The type of request and response are determined by the service proto definition.
    For example, for Login, the type of request is tbmatch.session_pb2.LoginRequest().
    One easy way to find the type of your RPC is to just look for the app route in
    routes.py and read the code.

    RPC handlers should do their work, write to response, and return.  If something
    goes wrong, raise an exception.
    """
    def AddRoute(fn):
        log.debug('adding rpc handler to {0}'.format(route))
        _RPC_HANDLERS[route] = fn
    return AddRoute
    
def GetRouteHandler(route):
    """
    Used by routes.py to lookup RPC handlers in the flask route handler.  If you're
    implementing an RPC, you can just ignore this one.
    """
    return _RPC_HANDLERS.get(route, None)

def LogProto(reason, proto):
    json = google.protobuf.json_format.MessageToJson(proto)
    for line in json.split('\n'):
        logging.debug(reason + line)
        reason = ''

