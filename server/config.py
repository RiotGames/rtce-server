"""
config.py
"""

import os
import tbmatch.match_pb2
import tbportal.portal_pb2

# The external hostname of the Rising Thunder server.
# If environment variable RT_SERVER_HOSTNAME is defined, it will be used, otherwise
# default to 127.0.0.1 for localhost.
hostname = os.environ.get('RT_SERVER_HOSTNAME', '127.0.0.1')

# Web port to listen on for RPCs
port = 1337

# The UDP port on this server that clients can use for ping testing.
portal_port_base = 42424
portal_port_range = 4096

# number of times to ping for the ping test
portal_ping_count = 5

# amount of time to wait on the client to allow for UI setup before redeeming the game session ticket
game_session_ticket_wait_interval_ms = 0.25

game_session_config = tbportal.portal_pb2.GameSessionConfig()
game_session_config.games_to_win = 2
game_session_config.handshake_reply_interval_ms = 2000

# Enabled features.
featureSet = tbmatch.match_pb2.ClientFeatureSet()
