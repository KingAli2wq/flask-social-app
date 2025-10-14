from flask import Flask, render_template, request, redirect, url_for, session
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Load users and posts
try:
    with open("data.json", "r") as file:
        users = json.load(file)
except:
    users = {}

try:
    with open("posts.json", "r") as file:
        posts = json.load(file)
except:
    posts = {}

@app.route('/')
def home():
    return render_template("home.html", posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users:
            return "Username already exists."

        if password in [info["password"] for info in users.values()]:
            return "Password already exists."

        users[username] = {
            "password": password,
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open("data.json", "w") as file:
            json.dump(users, file, indent=4)

        session['username'] = username
        return redirect(url_for('profile'))

    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username]["password"] == password:
            session['username'] = username
            return redirect(url_for('profile'))
        else:
            return "Invalid username or password."

    return render_template("login.html")

@app.route('/profile')
def profile():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    user_data = users.get(username)
    user_posts = posts.get(username, [])
    return render_template("profile.html", username=username, user_data=user_data, user_posts=user_posts)

@app.route('/post', methods=['POST'])
def post():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    new_post = {
        "post": request.form['post'],
        "posted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if username in posts:
        posts[username].append(new_post)
    else:
        posts[username] = [new_post]

    with open("posts.json", "w") as file:
        json.dump(posts, file, indent=4)

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)