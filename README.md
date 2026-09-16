# Rummy Scorekeeper

A colorful Flask + SQLite web app for keeping scores for your daily rummy matches.

## Features
- Login-based persistent history using SQLite.
- Create a match with 2–6 players.
- Each player gets a fixed color throughout the match.
- Configurable losing/set score (200 by default).
- Record the opening/highest-card player and open-card value.
- Add round-by-round losing points.
- Automatically eliminates a player when cumulative score reaches/crosses the set score.
- When only one player remains, that player is recorded as the match winner.
- Match history is stored permanently in `rummy.db`.
- Leaderboard counts full-match wins for the current login.
- A crown appears beside a player once they have 2 or more wins.

## Rule implementation
The app treats the entered round score as each player's losing points. Scores accumulate across rounds. A player is eliminated at `score >= set score`.

For the opening card rule, the UI calculates:
`target score = 200 + open card value`

You can also override the target directly in the new-match form if your table uses a different target.

## Run
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:
   `python -m pip install -r requirements.txt`
4. Start:
   `python app.py`
5. Open:
   `http://127.0.0.1:5000`

For a LAN game, Flask can be run with host `0.0.0.0` after changing the final line in `app.py`.

## Important
This is a scorekeeper, not a card-dealing engine. It does not simulate the 52/54-card deck because your request focused on score keeping, player persistence, and winner history.
