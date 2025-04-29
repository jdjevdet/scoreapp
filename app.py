from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# --- Helper Functions ---

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER,
            name TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            FOREIGN KEY(board_id) REFERENCES boards(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER,
            match_name TEXT NOT NULL,
            options TEXT,
            FOREIGN KEY(board_id) REFERENCES boards(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER,
            match_id INTEGER,
            user_name TEXT NOT NULL,
            pick TEXT NOT NULL,
            FOREIGN KEY(board_id) REFERENCES boards(id),
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    ''')

    conn.commit()
    conn.close()

# --- Public Site Routes ---

@app.route('/')
def public_home():
    conn = get_db_connection()
    boards = conn.execute('SELECT * FROM boards').fetchall()
    conn.close()
    return render_template('public_home.html', boards=boards)

@app.route('/prediction_centre')
def prediction_centre():
    conn = get_db_connection()
    boards = conn.execute('SELECT * FROM boards').fetchall()
    conn.close()
    return render_template('prediction_centre.html', boards=boards)

@app.route('/standings/<int:board_id>')
def public_standings(board_id):
    conn = get_db_connection()
    board = conn.execute('SELECT * FROM boards WHERE id = ?', (board_id,)).fetchone()
    players = conn.execute('SELECT * FROM players WHERE board_id = ? ORDER BY points DESC', (board_id,)).fetchall()
    conn.close()
    if board is None:
        return "Board not found", 404
    return render_template('public_standings.html', board=board, players=players)

@app.route('/prediction_event/<int:board_id>', methods=['GET', 'POST'])
def prediction_event(board_id):
    conn = get_db_connection()

    board = conn.execute('SELECT * FROM boards WHERE id = ?', (board_id,)).fetchone()
    matches = conn.execute('SELECT * FROM matches WHERE board_id = ?', (board_id,)).fetchall()

    matches_list = []
    for match in matches:
        match_dict = dict(match)
        match_dict['options'] = json.loads(match_dict['options']) if match_dict['options'] else []
        matches_list.append(match_dict)

    if request.method == 'POST':
        user_name = request.form.get('user_name', '').strip()

        if not user_name:
            conn.close()
            return render_template('error.html', message="You must enter your name before submitting your picks.")

        for match in matches_list:
            pick_key = f'pick_{match["id"]}'
            pick = request.form.get(pick_key)
            if pick:
                conn.execute('INSERT INTO predictions (board_id, match_id, user_name, pick) VALUES (?, ?, ?, ?)',
                             (board_id, match['id'], user_name, pick))
        conn.commit()
        conn.close()
        return render_template('thank_you.html', board=board)

    conn.close()
    if board is None:
        return "Board not found", 404
    return render_template('prediction_event.html', board=board, matches=matches_list)

@app.route('/global_standings')
def global_standings():
    conn = get_db_connection()
    players = conn.execute('SELECT name, SUM(points) as total_points FROM players GROUP BY name ORDER BY total_points DESC').fetchall()
    conn.close()
    return render_template('global_standings.html', players=players)

@app.route('/hall_of_fame')
def hall_of_fame():
    years = [2025]
    return render_template('hall_of_fame.html', years=years)

@app.route('/hall_of_fame/<int:year>')
def hall_of_fame_year(year):
    hall_data = {
        2025: {
            'image': url_for('static', filename='images/hof_2025.jpg'),
            'caption': "The legendary moment that defined 2025!"
        }
    }
    data = hall_data.get(year)
    if not data:
        return "Entry not found", 404
    return render_template('hall_of_fame_year.html', year=year, data=data)

# --- Admin Routes ---

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    boards = conn.execute('SELECT * FROM boards').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', boards=boards)

@app.route('/create_board', methods=['POST'])
def create_board():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    board_name = request.form['board_name']
    board_image = request.form['board_image']

    conn = get_db_connection()
    conn.execute('INSERT INTO boards (name, image) VALUES (?, ?)', (board_name, board_image))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_board/<int:board_id>', methods=['POST'])
def delete_board(board_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM boards WHERE id = ?', (board_id,))
    conn.execute('DELETE FROM players WHERE board_id = ?', (board_id,))
    conn.execute('DELETE FROM matches WHERE board_id = ?', (board_id,))
    conn.execute('DELETE FROM predictions WHERE board_id = ?', (board_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/manage_board/<int:board_id>')
def manage_board(board_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    board = conn.execute('SELECT * FROM boards WHERE id = ?', (board_id,)).fetchone()
    players = conn.execute('SELECT * FROM players WHERE board_id = ? ORDER BY points DESC', (board_id,)).fetchall()
    matches = conn.execute('SELECT * FROM matches WHERE board_id = ?', (board_id,)).fetchall()
    conn.close()
    if board is None:
        return "Board not found", 404
    return render_template('manage_board.html', board=board, players=players, matches=matches)

@app.route('/add_player/<int:board_id>', methods=['POST'])
def add_player(board_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    player_name = request.form['player_name']

    conn = get_db_connection()
    conn.execute('INSERT INTO players (board_id, name, points) VALUES (?, ?, 0)', (board_id, player_name))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_board', board_id=board_id))

@app.route('/add_match/<int:board_id>', methods=['POST'])
def add_match(board_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    match_name = request.form['match_name']
    options = request.form.getlist('options')
    options = [opt for opt in options if opt.strip() != '']
    options_json = json.dumps(options)

    conn = get_db_connection()
    conn.execute('INSERT INTO matches (board_id, match_name, options) VALUES (?, ?, ?)', (board_id, match_name, options_json))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_board', board_id=board_id))

@app.route('/update_points/<int:player_id>/<action>', methods=['POST'])
def update_points(player_id, action):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if action == 'add':
        conn.execute('UPDATE players SET points = points + 1 WHERE id = ?', (player_id,))
    elif action == 'subtract':
        conn.execute('UPDATE players SET points = points - 1 WHERE id = ?', (player_id,))
    conn.commit()
    conn.close()

    board_id = request.form['board_id']
    return redirect(url_for('manage_board', board_id=board_id))

@app.route('/remove_player/<int:player_id>', methods=['POST'])
def remove_player(player_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    board_id = request.form['board_id']
    conn.execute('DELETE FROM players WHERE id = ?', (player_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_board', board_id=board_id))

@app.route('/delete_match/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    board_id = request.form['board_id']

    conn = get_db_connection()
    conn.execute('DELETE FROM matches WHERE id = ?', (match_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('manage_board', board_id=board_id))

@app.route('/view_match_predictions/<int:match_id>')
def view_match_predictions(match_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    match = conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    predictions = conn.execute('SELECT user_name, pick FROM predictions WHERE match_id = ?', (match_id,)).fetchall()
    conn.close()

    if match is None:
        return "Match not found", 404

    return render_template('view_match_predictions.html', match=match, predictions=predictions)

# --- Login and Logout Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == 'ssj':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return "Incorrect password.", 403
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('public_home'))

# --- Initialize and Run ---

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
