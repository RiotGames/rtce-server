import game_client

def test_login():
    game_client.GameClient()

def test_home():
    c = game_client.GameClient()
    profile = c.GetGameProfile()
    games = c.GetRecentGames()

if __name__ == '__main__':
    test_login()