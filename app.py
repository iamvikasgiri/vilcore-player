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
from werkzeug.utils import secure_filename
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
import requests
from io import BytesIO


# ─── App & Login Setup ────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'S0m3$up3r$3cr3tK3y!'   # ← change to your own long random string
CORS(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # redirect to /login if @login_required fails

# ─── In‑Memory User Store ────────────────────────────────────────────────────
users = {
  'vilero': {'password': 'vilero', 'is_admin': True},
  # other prebuilt users…
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.is_admin = users.get(username, {}).get('is_admin', False)


@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

# ─── Routes: Register, Login, Logout ─────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd   = request.form['password']
        if uname in users:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        users[uname] = {'password': pwd, 'is_admin': False}
        user = User(uname)
        login_user(user)
        flash('Registration successful! Welcome, ' + uname, 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd   = request.form['password']
        if users.get(uname, {}).get('password') == pwd:
            user = User(uname)
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
    # Admin-only upload
    if not current_user.is_admin:
        abort(403)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Accept either: many files under 'files' OR single file under 'file'
    files = request.files.getlist('files') or []
    single = request.files.get('file')
    if single and (not files):
        files = [single]

    if not files:
        # No files uploaded
        return jsonify({"error": "No files uploaded"}), 400

    results = []
    # limit to 50 files per request
    for f in files[:50]:
        filename = secure_filename(f.filename)
        if not filename or not allowed_file(filename):
            results.append({"filename": f.filename, "status": "invalid_type"})
            continue

        dest = os.path.join(UPLOAD_FOLDER, filename)
        try:
            f.save(dest)
            results.append({"filename": filename, "status": "ok"})
        except Exception as e:
            app.logger.exception("Failed saving file %s: %s", filename, e)
            results.append({"filename": filename, "status": "error", "error": str(e)})

    return jsonify({"results": results}), 200


@app.route('/songs')
@login_required
def list_songs():
    from mutagen import File
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    result = []

    for filename in os.listdir(UPLOAD_FOLDER):
        if not allowed_file(filename):
            continue
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        meta = File(filepath, easy=True)
        title = meta.get('title', [os.path.splitext(filename)[0]])[0]
        artist = meta.get('artist', [''])[0]
        result.append({
            'filename': filename,
            'title': title,
            'artist': artist
        })

    return jsonify(result)


def get_range(request):
    range_header = request.headers.get('Range', None)
    if not range_header:
        return None
    _, range_spec = range_header.split('=', 1)
    start_str, end_str = range_spec.split('-', 1)
    return int(start_str), int(end_str) if end_str else None

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
