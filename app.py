import os
from flask import (
    Flask, request, send_file, jsonify, render_template,
    abort, Response, redirect, url_for, flash
)
from flask_cors import CORS
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user, current_user
)
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
import requests
from io import BytesIO
from supabase_client import supabase
import bcrypt


# ─── App & Login Setup ────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'S0m3$up3r$3cr3tK3y!'   # ← change to your own long random string
CORS(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # redirect to /login if @login_required fails

# ─── In‑Memory User Store ────────────────────────────────────────────────────
# users = {
#   'vilero': {'password': 'vilero', 'is_admin': True},
#   # other prebuilt users…
# }

class User(UserMixin):
    def __init__(self, id: str, username: str, is_admin: bool):
        self.id = id            # uuid from Supabase
        self.username = username
        self.is_admin = is_admin

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    # Query Supabase for this user by id
    resp = supabase.from_("users").select("id, username, is_admin")\
                    .eq("id", user_id).single().execute()
    data = resp.data
    if data:
        return User(data["id"], data["username"], data["is_admin"])
    return None

# ─── Routes: Register, Login, Logout ─────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd   = request.form['password'].encode('utf-8')

        # ─── ① Check username uniqueness ─────────────────────────────────
        try:
            check = (
                supabase
                .from_("users")
                .select("id")
                .eq("username", uname)
                .execute()
            )
            existing = check.data or []
        except Exception as e:
            app.logger.error("Supabase register-check error: %s", e)
            flash('Registration service unavailable. Please try again.', 'danger')
            return redirect(url_for('register'))

        if existing:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))

        # ─── ② Hash + insert new user ───────────────────────────────────
        pw_hash = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')
        try:
            insert = (
                supabase
                .from_("users")
                .insert({"username": uname, "password": pw_hash, "is_admin": False})
                .execute()
            )
            new_rows = insert.data or []
        except Exception as e:
            app.logger.error("Supabase register-insert error: %s", e)
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('register'))

        if not new_rows:
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('register'))

        new_user = new_rows[0]
        user = User(new_user["id"], new_user["username"], new_user["is_admin"])
        login_user(user)
        flash('Registration successful! Welcome, ' + uname, 'success')
        return redirect(url_for('index'))

    return render_template('register.html')




@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd   = request.form['password'].encode('utf-8')

        # ─── ① Try to fetch the user row ─────────────────────────────────
        try:
            resp = (
                supabase
                .from_("users")
                .select("id, username, password, is_admin")
                .eq("username", uname)
                .execute()
            )
            users_list = resp.data or []
        except Exception as e:
            app.logger.error("Supabase login error: %s", e)
            flash('Login service unavailable. Please try again later.', 'danger')
            return redirect(url_for('login'))

        # ─── ② No matching user? ──────────────────────────────────────────
        if not users_list:
            flash('Invalid credentials, please try again.', 'danger')
            return redirect(url_for('login'))

        user_row = users_list[0]
        stored_pw = user_row["password"].encode('utf-8')

        # ─── ③ Check password ─────────────────────────────────────────────
        if bcrypt.checkpw(pwd, stored_pw):
            user = User(user_row["id"], user_row["username"], user_row["is_admin"])
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))

        flash('Invalid credentials, please try again.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')




@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ─── Music Player Routes ──────────────────────────────────────────────────────
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXT = {'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if not current_user.is_admin:
        abort(403)

    files = request.files.getlist('files')
    if not files:
        flash("No files selected", "warning")
        return redirect(url_for("index"))

    # Limit to 50 at a time
    if len(files) > 50:
        flash("Please select at most 50 files at once", "warning")
        return redirect(url_for("index"))

    success = 0
    for f in files:
        if not allowed_file(f.filename):
            continue

        filename = f.filename
        data = f.read()
        storage_path = f"songs/{filename}"

        # 1) Upload to Supabase Storage
        try:
            supabase.storage.from_("songs") \
                .upload(storage_path, data, {"content-type": f.mimetype})
        except Exception as e:
            app.logger.error("Storage upload error for %s: %s", filename, e)
            continue  # skip recording in DB

        # 2) Public URL
        public_url = supabase.storage.from_("songs") \
                         .get_public_url(storage_path)

        # 3) Record metadata in DB
        song_meta = {
            "filename": filename,
            "title": os.path.splitext(filename)[0],
            "artist": "",
            "file_path": storage_path,
            "file_size": len(data),
            "public_url": public_url,
            "uploaded_by": current_user.id
        }
        try:
            supabase.from_("songs").insert(song_meta).execute()
            success += 1
        except Exception as e:
            app.logger.error("DB insert error for %s: %s", filename, e)
            # we don’t abort—we just keep going

    flash(f"{success} out of {len(files)} uploaded & recorded", "success")
    return redirect(url_for("index"))


@app.route('/songs')
@login_required
def list_songs():
    try:
        resp = (
            supabase
            .from_("songs")
            .select("filename, title, artist, public_url")
            .order("created_at", desc=True)
            .execute()
        )
        songs = resp.data or []
    except Exception as e:
        app.logger.error("Supabase songs-fetch error: %s", e)
        abort(500, "Could not fetch songs")

    return jsonify(songs)





def get_range(request):
    range_header = request.headers.get('Range', None)
    if not range_header:
        return None
    _, range_spec = range_header.split('=', 1)
    start_str, end_str = range_spec.split('-', 1)
    return int(start_str), int(end_str) if end_str else None

@app.route('/art/<filename>')
@login_required
def art(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    # 1️⃣ Try embedded artwork
    try:
        audio = MutagenFile(path)
        for tag in audio.tags.values():
            if hasattr(tag, 'data'):  # e.g. APIC frames in MP3
                img_data = tag.data
                return Response(img_data, mimetype='image/jpeg')
    except Exception:
        pass

    # 2️⃣ Fallback: search iTunes API
    term = os.path.splitext(filename)[0]
    itunes = requests.get(
        'https://itunes.apple.com/search',
        params={'term': term, 'media': 'music', 'limit': 1}
    ).json()
    if itunes.get('results'):
        art_url = itunes['results'][0].get('artworkUrl100')
        if art_url:
            img = requests.get(art_url).content
            return Response(img, mimetype='image/jpeg')

    # 3️⃣ Final fallback: default image
    return send_file(
        os.path.join(app.static_folder, 'images/default.png'),
        mimetype='image/png'
    )

@app.route('/metadata/<filename>')
@login_required
def metadata(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    title = os.path.splitext(filename)[0]  # fallback: filename without extension
    artist = 'Unknown Artist'

    # Try to read ID3 tags
    try:
        tags = EasyID3(path)
        title = tags.get('title', [title])[0]
        artist = tags.get('artist', [artist])[0]
    except Exception:
        pass  # if no tags or error, keep our defaults

    return jsonify({'title': title, 'artist': artist})

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    songs = os.listdir(UPLOAD_FOLDER)
    return render_template('admin.html', songs=songs)


if __name__ == '__main__':
    app.run()
