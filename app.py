import os
import datetime

from helpers import chk, get_rndm, scramble, set_wrds

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from flask import Flask, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


@app.route('/clear', methods=["POST"])
def clear():
    session['wrd'] = None # 'Reset' game session upon redirect to homepage
    return '', 204 # Return HTTP 204 No Content


@app.route('/', methods=["GET", "POST"])
def index():
    # Check if user authenticated
    if session.get("user_id"):
        user_id = session["user_id"]
        r = db.session.execute(
            text("SELECT optn FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        optn = r[0] # Fetch saved difficulty option for specific user

    else:
        optn = session.get("optn", "standard")

    return render_template("index.html", optn=optn)


@app.route('/info')
def info():
    return render_template("info.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    session.clear() # Clear existing session data
    alert = None

    try:
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            if not username:
                alert = "No username provided."
                return render_template("login.html", alert=alert)
            
            elif not password:
                alert = "No password provided."
                return render_template("login.html", alert=alert)
            
            # Query database for entered username
            r = db.session.execute(
                text("SELECT * FROM users WHERE username = :username"),
                {"username": username}
            )
            rows = r.mappings().all() # Map query results to dictionary structure

            # Validate user password
            if len(rows) != 1 or not check_password_hash(
                rows[0]["hash"], password
            ):
                alert = "Password incorrect."
                return render_template("login.html", alert=alert)
            
            # Establish user session
            session["user_id"] = rows[0]["id"]
            session.modified = True

            return redirect("/")
        
        else:
            return render_template("login.html")
    
    except Exception as e:

        alert = f"{e} error encountered."
        return render_template("register.html", alert=alert)
    

@app.route('/logout')
def logout():
    session.clear() # Clear user session

    return redirect('/')


@app.route('/main', methods=["GET", "POST"])
def main():
    WRDS = set_wrds() # Set organized dictionary of words

    alert = None

    # Check if user authenticated
    if session.get("user_id"):
        user_id = session["user_id"]
        r = db.session.execute(
            text("SELECT optn FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        optn = r[0] # Fetch saved difficulty option for specific user

    else:
        optn = session.get("optn", "standard")
    
    if request.method == "GET":
        # 'Reset' game session when page is loaded initially
        session['wrd'] = None

    if not session.get('wrd'):
        # Fetch random new word if none exists in session
        result = get_rndm(WRDS, optn)

        if not result:
            return redirect('/')
        
        # Retrieve word details
        wrd, defn, scr = result
        scrmb_wrd = scramble(wrd)

        session['wrd'] = wrd
        session['defn'] = defn
        session['scrmb_wrd'] = scrmb_wrd
        session['scr'] = scr
        session['pts'] = 0
        session['trys'] = 3
    
    # Track user attempts, end game if none are left
    if session['trys'] <= 0:
        if session.get("user_id"):
            # Query to retreive user's current high score
            user_id = session["user_id"]
            r = db.session.execute(
                text(f"SELECT score_{optn} FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()
            
            h_scr = r[0] if r else 0
            
            if pts > h_scr:
                alert = f"{pts} is a new high score!"
                # Query to update user's high score if score higher than current high score
                db.session.execute(
                    text(f"UPDATE users SET score_{optn} = :pts WHERE id = :user_id"),
                    {"pts": pts, "user_id": user_id}
                )
                db.session.commit()

            timestamp = datetime.datetime.now()
            # Query to record user's score to history of scores
            db.session.execute(
                text("INSERT INTO scores (user_id, score, difficulty, timestamp) VALUES (:user_id, :pts, :optn, :timestamp)"),
                {"user_id": user_id, "pts": pts, "optn": optn, "timestamp": timestamp}
            )

            db.session.commit()
                        
        return render_template('score.html', pts=session['pts'], optn=optn, alert=alert)
    
    # Fetch new word upon user submission
    if request.method == "POST":
        wrd = session.get('wrd')
        defn = session.get('defn')
        scrmb_wrd = session.get('scrmb_wrd')
        scr = session.get('scr')
        pts = session.get('pts')

        ans = request.form.get("ans", "")

        # Increase user points based on word's 'difficulty score' upon correct submission
        if chk(ans, wrd):
            pts += scr
            alert = f"+ {scr} points!"

        # Decrease user 'trys' upon incorrect submission       
        else:
            session["trys"] -= 1
            alert = f"wrong! {session["trys"]} more try/tries."

            # Track user attempts, end game if none are left 
            if session['trys'] <= 0:
                if session.get("user_id"):
                    user_id = session["user_id"]
                    r = db.session.execute(
                        text(f"SELECT score_{optn} FROM users WHERE id = :user_id"),
                            {"user_id": user_id}
                        ).fetchone()
                    
                    h_scr = r[0] if r else 0
                    
                    if pts > h_scr:
                        alert = f"{pts} is a new high score for {optn} difficulty!"
                        db.session.execute(
                            text(f"UPDATE users SET score_{optn} = :pts WHERE id = :user_id"),
                            {"pts": pts, "user_id": user_id}
                        )
                        db.session.commit()
                    
                    timestamp = datetime.datetime.now()
                    db.session.execute(
                        text("INSERT INTO scores (user_id, score, difficulty, timestamp) VALUES (:user_id, :pts, :optn, :timestamp)"),
                        {"user_id": user_id, "pts": pts, "optn": optn, "timestamp": timestamp}
                    )

                    db.session.commit()
                                
                return render_template('score.html', pts=session['pts'], optn=optn, alert=alert)
        
        result = get_rndm(WRDS, optn)

        if not result:
            return redirect('/')
                
        wrd, defn, scr = result
        scrmb_wrd = scramble(wrd)

        session['wrd'] = wrd
        session['defn'] = defn
        session['scrmb_wrd'] = scrmb_wrd
        session['scr'] = scr
        session['pts'] = pts
    
    return render_template('main.html', scrmb_wrd=session.get('scrmb_wrd'), defn=session.get('defn'), pts=session.get('pts'), trys=session.get('trys'), 
                           optn=optn, alert=alert)


@app.route('/register', methods=["GET", "POST"])
def register():
    session.clear()

    try: 
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            confirmation = request.form.get("confirmation")

            if not username:
                alert = "No username provided."
                return render_template("register.html", alert=alert)

            elif not password:
                alert = "No password provided."
                return render_template("register.html", alert=alert)
            
            elif len(password) < 8:
                alert = "Password length must be greater than 8 characters."
                return render_template("register.html", alert=alert)

            elif not confirmation:
                alert = "Must confirm password."
                return render_template("register.html", alert=alert)

            elif password != confirmation:
                alert = "Passwords do not match."
                return render_template("register.html", alert=alert)
            
            # Query database for exisiting usernames
            r = db.session.execute(
                text("SELECT * FROM users WHERE username = :username"),
                {"username": username}
            )
            rows = r.mappings().all() # Map query results to dictionary structure

            if len(rows) != 0:
                alert = "Username already exists."
            
            db.session.execute(
                text("INSERT INTO users (username, hash) VALUES (:username, :hash)"),
                {"username": username, "hash": generate_password_hash(password)}
            )
            db.session.commit()

            # Query to save username to database for new user
            r = db.session.execute(
                text("SELECT * FROM users WHERE username = :username"),
                {"username": username}
            )
            rows = r.mappings().all()

            # Assign session to 'id'
            session["user_id"] = rows[0]["id"]
            session.modified = True

            return redirect("/")

        else:
            return render_template("register.html")
    
    except Exception as e:
        
        alert = f"{e}Error encountered."
        return render_template("register.html", alert=alert)


@app.route('/scores', methods=["GET", "POST"])
def scores():
    if session.get("user_id"):
        user_id = session["user_id"]

        # Query to retrieve user scores from history of scores
        scores = db.session.execute(
            text("""
                SELECT 
                    score, 
                    difficulty, 
                    timestamp 
                FROM scores
                WHERE user_id = :user_id
                ORDER BY score DESC
            """),
            {"user_id": user_id}
        ).fetchall()

    return render_template("scores.html", scores=scores) # Display scores in tabular format


@app.route('/set', methods=["GET", "POST"])
def set():
    # Check if user authenticated
    if session.get("user_id"):
        user_id = session["user_id"]
        r = db.session.execute(
            text("SELECT optn FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        optn = r[0] # Fetch saved difficulty option for specific user

    else:
        optn = session.get("optn", "standard")

    alert = None

    if request.method == "POST":

        optn = request.form.get("optn")

        if optn in ("easy", "standard", "hard", "expert"):
            session['optn'] = optn
            alert = f"Difficulty set to: {optn}."

            # Query to save user selected difficulty upon user submission
            if session.get("user_id"):
                db.session.execute(
                    text("UPDATE users SET optn = :optn WHERE id = :user_id"),
                    {"optn": optn, "user_id": user_id}
                )
                db.session.commit()

        else:
            alert = "Error editing difficulty."
            optn = session.get('optn', 'standard')

    return render_template("set.html", optn=optn, alert=alert)
