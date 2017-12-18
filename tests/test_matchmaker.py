import time
import tbmatch.event_pb2
import game_client

def test_matchmaking_loop():
    c1 = game_client.GameClient()
    c2 = game_client.GameClient()

    get_match_request = tbmatch.match_pb2.GetMatchRequest()
    c1.GetMatch(get_match_request)
    c2.GetMatch(get_match_request)

    # wait for at least 1 poll to happen
    time.sleep(6)

    assert check_client_events(c1) and check_client_events(c2)

def check_client_events(client):
    found_waiting_event = False
    found_match_event = False
    for event in client.DoGetEvents():
        if is_wait_event(event):
            found_waiting_event = True
        if is_match_event(event):
            found_match_event = True

    return found_waiting_event and found_match_event

def is_wait_event(event):
    return event.type == tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS and event.wait_match_progress.status == tbmatch.event_pb2.WaitMatchProgressEvent.WAITING

def is_match_event(event):
    return event.type == tbmatch.event_pb2.Event.E_WAIT_MATCH_PROGRESS and event.wait_match_progress.status == tbmatch.event_pb2.WaitMatchProgressEvent.MATCH

if __name__ == '__main__':
    test_matchmaking_loop()