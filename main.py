from game.game import PongGame
import threading
from server.server import start_server
import subprocess
import sys

if __name__ == "__main__":
    # Start server in background
    t = threading.Thread(target=start_server , daemon=True)
    t.start()
    # Start game
    game = PongGame()
    game.run()
