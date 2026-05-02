from flask import Flask, render_template, request
from flask_socketio import SocketIO

app = Flask(__name__, template_folder="../controller/templates")
socketio = SocketIO(app, async_mode="threading")

# store player inputs
players = {
    "p1": {"x": 0, "y": 0},
    "p2": {"x": 0, "y": 0}
}

# map socket -> player
client_map = {}

next_player = "p1"

@app.route("/")
def index():
    return render_template("controller.html")

# ---------------------------
@socketio.on("connect")
def handle_connect():
    global next_player

    sid = request.sid

    # assign player
    player = next_player
    next_player = "p2" if next_player == "p1" else "p1"

    client_map[sid] = player

    socketio.emit("assign", {"player": player}, room=sid)

# ---------------------------
@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in client_map:
        player = client_map[sid]
        players[player] = {"x": 0, "y": 0}
        del client_map[sid]

# ---------------------------
@socketio.on("move")
def handle_move(data):
    sid = request.sid

    if sid not in client_map:
        return

    player = client_map[sid]

    players[player] = data["dir"]

# ---------------------------
def get_inputs():
    return players

# ---------------------------
def start_server():
    socketio.run(app, host="0.0.0.0", port=5000)
    
if __name__=="__main__":
	start_server()
	
