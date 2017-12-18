# TODO

### matchmaker:
 - [ ] implement re-queue:
   - [ ] echo test failure between the clients when match about to start
     - [ ] test when echo test between player is too high (of a ping test), both re-queue
     - [ ] one of the client is not connected
 
### persistence:
 - [ ] create acccount on-demand during login
 - [ ] simple webpage to create account
 - [ ] store username, password, players preference (loadouts)
 
### spectating:
 - [ ] make portal support spectating
 
### accounts:
 - [ ] allow players to set their name instead of using randomly generated names

### lobbies:
 - [ ] increase capacity if spectating is available, otherwise limit to 2 players
 - [ ] lobby management (banning, kicking, setting ownership)

### portal:
 - [ ] complete portal state machine
 
### testing:
 - [ ] test that the server works on different home & work network configurations
 - [ ] test error cases in portal, including unexpected client disconnect

