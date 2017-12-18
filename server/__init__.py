import uuid
import tornado.log
import tornado.options
import tornado.web
import tornado.ioloop
import server.generated_routes
import server.models.portal
import server.models.matchmaker
import server.models.users
import server.models.lobbies

tornado.options.parse_command_line()
tornado.log.enable_pretty_logging()

app = tornado.web.Application()    
ioloop = tornado.ioloop.IOLoop.current()

users = server.models.users.Users()
matchmaker = server.models.matchmaker.Matchmaker()
portal = server.models.portal.Portal()
lobbies = server.models.lobbies.Lobbies()

import server.services.match_service
import server.services.lobby_service
import server.services.event_service
import server.services.session_service

def Start():
    tornado.log.logging.info("Server starting at {0}".format(server.config.hostname))

    matchmaker.StartPolling()

    routes = server.generated_routes.GetRoutes()
    routes.append((r'/_01/rpc/GetEvent', server.services.event_service.GetEventHandler))
    app.add_handlers(r'.*', routes) 
    app.listen(server.config.port)
    ioloop.start()
    

NEXT_UNIQUE_ID = 0
def GetNextUniqueId():
    """
    Useful for people who need a unique id for something (having all objects in the system having
    a unique id is less error-prone)
    """
    global NEXT_UNIQUE_ID
    NEXT_UNIQUE_ID = NEXT_UNIQUE_ID + 1
    return NEXT_UNIQUE_ID

def GetNewSecret():
    return uuid.uuid4().int & (1<<64)-1