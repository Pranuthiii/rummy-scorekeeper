from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rummy-scorekeeper-change-me")
DB = os.path.join(os.path.dirname(__file__), "rummy.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        set_score INTEGER NOT NULL DEFAULT 200,
        open_card_value INTEGER NOT NULL DEFAULT 0,
        opening_winner TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        winner_player TEXT,
        created_at TEXT NOT NULL,
        finished_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        color TEXT NOT NULL,
        score INTEGER NOT NULL DEFAULT 0,
        eliminated INTEGER NOT NULL DEFAULT 0,
        eliminated_at TEXT,
        FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        round_no INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS round_scores (
        round_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(round_id, player_id),
        FOREIGN KEY(round_id) REFERENCES rounds(id) ON DELETE CASCADE,
        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

init_db()

COLORS = ["#FF5C8A", "#7C5CFC", "#00B8A9", "#FFB000", "#00A8FF", "#FF6B35",
          "#8AC926", "#C77DFF", "#00C2FF", "#F15BB5", "#2EC4B6", "#FF595E"]

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Please enter a login name.", "error")
            return render_template("login.html")
        conn = db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            conn.execute("INSERT INTO users(username, created_at) VALUES(?, ?)",
                         (username, datetime.now().isoformat(timespec="seconds")))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        session["user_id"] = row["id"]
        session["username"] = row["username"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = db()
    matches = conn.execute("""
        SELECT * FROM matches WHERE user_id = ? ORDER BY id DESC LIMIT 12
    """, (session["user_id"],)).fetchall()
    leaderboard = conn.execute("""
        SELECT p.name, COUNT(*) AS wins
        FROM matches m
        JOIN players p ON p.match_id = m.id AND p.name = m.winner_player
        WHERE m.user_id = ? AND m.status = 'finished'
        GROUP BY p.name
        ORDER BY wins DESC, p.name COLLATE NOCASE
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("dashboard.html", matches=matches, leaderboard=leaderboard)

@app.route("/new-match", methods=["GET", "POST"])
@login_required
def new_match():
    if request.method == "POST":
        names = [x.strip() for x in request.form.getlist("player_name") if x.strip()]
        try:
            set_score = int(request.form.get("set_score", 200))
            open_card = int(request.form.get("open_card_value", 0))
        except ValueError:
            flash("Score values must be numbers.", "error")
            return redirect(url_for("new_match"))

        if not 2 <= len(names) <= 6:
            flash("This version supports 2–6 players.", "error")
            return redirect(url_for("new_match"))
        if len({n.lower() for n in names}) != len(names):
            flash("Player names must be unique within a match.", "error")
            return redirect(url_for("new_match"))
        if set_score <= 0:
            flash("Set score must be greater than zero.", "error")
            return redirect(url_for("new_match"))
        if not 0 <= open_card <= 54:
            flash("Open-card value must be between 0 and 54.", "error")
            return redirect(url_for("new_match"))

        conn = db()
        cur = conn.execute("""
            INSERT INTO matches(user_id, set_score, open_card_value, created_at)
            VALUES (?, ?, ?, ?)
        """, (session["user_id"], set_score, open_card,
              datetime.now().isoformat(timespec="seconds")))
        match_id = cur.lastrowid
        for i, name in enumerate(names):
            conn.execute("INSERT INTO players(match_id, name, color) VALUES(?, ?, ?)",
                         (match_id, name, COLORS[i % len(COLORS)]))
        conn.commit()
        conn.close()
        return redirect(url_for("game", match_id=match_id))
    return render_template("new_match.html")

@app.route("/match/<int:match_id>")
@login_required
def game(match_id):
    conn = db()
    match = conn.execute("""
        SELECT * FROM matches WHERE id = ? AND user_id = ?
    """, (match_id, session["user_id"])).fetchone()
    if not match:
        conn.close()
        return "Match not found", 404
    players = conn.execute("""
        SELECT * FROM players WHERE match_id = ? ORDER BY id
    """, (match_id,)).fetchall()
    rounds = conn.execute("""
        SELECT * FROM rounds WHERE match_id = ? ORDER BY round_no DESC
    """, (match_id,)).fetchall()
    round_data = []
    for r in rounds:
        scores = conn.execute("""
            SELECT rs.points, p.name, p.color
            FROM round_scores rs JOIN players p ON p.id = rs.player_id
            WHERE rs.round_id = ? ORDER BY p.id
        """, (r["id"],)).fetchall()
        round_data.append((r, scores))
    match_no = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE user_id=? AND id<=?",
        (session["user_id"], match_id)
    ).fetchone()[0]
    conn.close()
    return render_template("game.html", match=match, match_no=match_no, players=players, rounds=round_data)

@app.route("/match/<int:match_id>/round", methods=["POST"])
@login_required
def add_round(match_id):
    conn = db()
    match = conn.execute("SELECT * FROM matches WHERE id=? AND user_id=?",
                         (match_id, session["user_id"])).fetchone()
    if not match:
        conn.close()
        return jsonify({"ok": False, "error": "Match not found"}), 404
    if match["status"] == "finished":
        conn.close()
        return jsonify({"ok": False, "error": "This match is already finished."}), 400

    players = conn.execute("SELECT * FROM players WHERE match_id=? ORDER BY id",
                            (match_id,)).fetchall()
    points = {}
    for p in players:
        try:
            value = int(request.form.get(f"score_{p['id']}", "0") or 0)
        except ValueError:
            conn.close()
            return jsonify({"ok": False, "error": f"Invalid score for {p['name']}."}), 400
        if value < 0:
            conn.close()
            return jsonify({"ok": False, "error": "Round points cannot be negative."}), 400
        points[p["id"]] = value

    active = [p for p in players if not p["eliminated"]]
    if not active:
        conn.close()
        return jsonify({"ok": False, "error": "No active players remain."}), 400

    round_no = conn.execute("SELECT COALESCE(MAX(round_no), 0)+1 FROM rounds WHERE match_id=?",
                            (match_id,)).fetchone()[0]
    cur = conn.execute("INSERT INTO rounds(match_id, round_no, created_at) VALUES(?,?,?)",
                       (match_id, round_no, datetime.now().isoformat(timespec="seconds")))
    round_id = cur.lastrowid

    for p in players:
        conn.execute("INSERT INTO round_scores(round_id, player_id, points) VALUES(?,?,?)",
                     (round_id, p["id"], points[p["id"]]))
        conn.execute("UPDATE players SET score = score + ? WHERE id=?",
                     (points[p["id"]], p["id"]))

    # A player is out as soon as their cumulative score reaches the target.
    threshold = match["set_score"]
    conn.commit()

    updated = conn.execute("SELECT * FROM players WHERE match_id=? ORDER BY id",
                           (match_id,)).fetchall()
    newly_out = []
    for p in updated:
        if not p["eliminated"] and p["score"] >= threshold:
            conn.execute("""
                UPDATE players SET eliminated=1, eliminated_at=?
                WHERE id=?
            """, (datetime.now().isoformat(timespec="seconds"), p["id"]))
            newly_out.append(p["name"])

    updated = conn.execute("SELECT * FROM players WHERE match_id=? ORDER BY id",
                           (match_id,)).fetchall()
    remaining = [p for p in updated if not p["eliminated"]]

    winner = None
    if len(remaining) == 1:
        winner = remaining[0]["name"]
        conn.execute("""
            UPDATE matches SET status='finished', winner_player=?, finished_at=?
            WHERE id=?
        """, (winner, datetime.now().isoformat(timespec="seconds"), match_id))
    elif len(remaining) == 0:
        # Safety fallback for an all-out round. The lowest score wins.
        winner_row = min(updated, key=lambda p: p["score"])
        winner = winner_row["name"]
        conn.execute("""
            UPDATE matches SET status='finished', winner_player=?, finished_at=?
            WHERE id=?
        """, (winner, datetime.now().isoformat(timespec="seconds"), match_id))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "newly_out": newly_out, "winner": winner,
                    "remaining": [p["name"] for p in remaining]})

@app.route("/match/<int:match_id>/opening", methods=["POST"])
@login_required
def set_opening(match_id):
    conn = db()
    match = conn.execute("SELECT * FROM matches WHERE id=? AND user_id=?",
                         (match_id, session["user_id"])).fetchone()
    if not match:
        conn.close()
        return jsonify({"ok": False, "error": "Match not found"}), 404
    winner = request.form.get("opening_winner", "").strip()
    value = int(request.form.get("open_card_value", "0") or 0)
    exists = conn.execute("SELECT 1 FROM players WHERE match_id=? AND name=?",
                          (match_id, winner)).fetchone()
    if not exists:
        conn.close()
        return jsonify({"ok": False, "error": "Select a valid player."}), 400
    conn.execute("UPDATE matches SET opening_winner=?, open_card_value=? WHERE id=?",
                 (winner, value, match_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/match/<int:match_id>/delete", methods=["POST"])
@login_required
def delete_match(match_id):
    conn = db()
    conn.execute("DELETE FROM matches WHERE id=? AND user_id=?", (match_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True, port=5001)
