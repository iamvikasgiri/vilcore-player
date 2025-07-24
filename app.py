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

    f = request.files.get('file')
    if not f or not allowed_file(f.filename):
        abort(400, "Invalid file type")

    filename = f.filename
    # 1) Upload to Supabase Storage
    try:
        # read file bytes
        data = f.read()
        # choose a path, e.g. "songs/<filename>"
        storage_path = f"songs/{filename}"
        res = (
            supabase
            .storage
            .from_("songs")
            .upload(storage_path, data, {"content-type": f.mimetype})
        )
        if res.get("error"):
            app.logger.error("Supabase Storage error: %s", res["error"])
            raise Exception(res["error"]["message"])
    except Exception as e:
        flash("Failed to upload to storage: " + str(e), "danger")
        return redirect(url_for("index"))

    # 2) Make the file publicly accessible
    public_url = supabase.storage.from_("songs").get_public_url(storage_path)["publicUrl"]

    # 3) Record metadata + URL in your songs table
    stat = len(data)
    song_meta = {
        "filename": filename,
        "title": os.path.splitext(filename)[0],
        "artist": "",
        "file_path": storage_path,
        "file_size": stat,
        "public_url": public_url,
        "uploaded_by": current_user.id
    }
    print("Recording song_meta to DB:", song_meta)

    try:
        insert = supabase.from_("songs").insert(song_meta).execute()
        if insert.get("error"):
            app.logger.error("Supabase DB insert error: %s", insert["error"])
            flash("Upload successful, but failed to record in DB", "warning")
        else:
            flash(f"{filename} uploaded and saved to database", "success")
    except Exception as e:
        app.logger.error("Exception during DB insert: %s", str(e))
        flash("Failed to record song metadata to DB", "danger")

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

# Remove this /stream part
@app.route('/stream/<filename>')
@login_required
def stream(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(path):
        abort(404)
    file_size = os.path.getsize(path)
    byte_range = get_range(request)
    if byte_range:
        start, end = byte_range
        end = end or file_size - 1
        length = end - start + 1
        with open(path, 'rb') as f:
            f.seek(start)
            chunk = f.read(length)
        resp = Response(chunk, 206, mimetype='audio/mpeg', direct_passthrough=True)
        resp.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
        return resp
    return send_file(path, mimetype='audio/mpeg')

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
