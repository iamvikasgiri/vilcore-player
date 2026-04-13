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
from dotenv import load_dotenv
import boto3
from database import init_db, get_connection


# ─── Loading Env ────────────────────────────────────────────────────────
load_dotenv()

R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME")
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")

s3 = boto3.client(
    service_name='s3',
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY
)


# ─── App & Login Setup ────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY")
CORS(app)

# ─── Initializing the DB ───────────────────────────────────────────────────────
init_db()

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # redirect to /login if @login_required fails


# ─── Funtion to retrieve songs from R2 Bucket ────────────────────────────────────
def get_r2_file(filename):
    try:
        obj = s3.get_object(Bucket=R2_BUCKET, Key=filename)
        return obj
    except Exception as e:
        app.logger.error(f"R2 fetch error: {e}")
        return None

# ─── In‑Memory User Store ────────────────────────────────────────────────────
users = {
  'vilero': {'password': 'vilero', 'is_admin': True},
  'uttam': {'password': 'uttam', 'is_admin': False},
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
ALLOWED_EXT = {'mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/delete-song/<filename>', methods=['DELETE'])
@login_required
def delete_song(filename):
    if not current_user.is_admin:
        abort(403)

    try:
        s3.delete_object(Bucket=R2_BUCKET, Key=filename)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM songs WHERE filename = ?", (filename,))
        conn.commit()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        filename = os.path.basename(f.filename.strip())
        if not filename or not allowed_file(filename):
            results.append({"filename": f.filename, "status": "invalid_type"})
            continue

        dest = os.path.join(UPLOAD_FOLDER, filename)
        try:
            s3.upload_fileobj(f, R2_BUCKET, filename) #uploading to R2 Bucket
            results.append({"filename": filename, "status": "ok"})

            title = os.path.splitext(filename)[0]

            # Saving songs into DB
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR IGNORE INTO songs (filename, title, artist)
            VALUES (?, ?, ?)
            """, (filename, title, ''))
            conn.commit()
            conn.close()

            s3.upload_fileobj(f, R2_BUCKET, filename)

        except Exception as e:
            app.logger.exception("Failed saving file %s: %s", filename, e)
            results.append({"filename": filename, "status": "error", "error": str(e)})

    return jsonify({"results": results}), 200


@app.route('/songs')
@login_required
def list_songs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT filename, title, artist
    FROM songs
    ORDER BY title COLLATE NOCASE ASC
    """)

    songs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(songs)

@app.route('/admin/songs')
@login_required
def admin_songs():
    if not current_user.is_admin:
        abort(403)

    sort = request.args.get("sort", "title_asc")

    sort_map = {
        "title_asc": "title COLLATE NOCASE ASC",
        "title_desc": "title COLLATE NOCASE DESC",
        "newest": "uploaded_at DESC",
        "oldest": "uploaded_at ASC"
    }

    order_by = sort_map.get(sort, "title COLLATE NOCASE ASC")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT filename, title, artist
        FROM songs
        ORDER BY {order_by}
    """)

    songs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(songs)


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
    range_header = request.headers.get('Range', None)

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        if match[0]:
            byte1 = int(match[0])
        if len(match) > 1 and match[1]:
            byte2 = int(match[1])

        range_value = f"bytes={byte1}-{byte2 if byte2 is not None else ''}"

        obj = s3.get_object(
            Bucket=R2_BUCKET,
            Key=filename,
            Range=range_value
        )

        data = obj['Body'].read()
        file_size = obj['ContentLength']

        resp = Response(data, 206, mimetype='audio/mpeg')
        resp.headers['Content-Range'] = obj['ContentRange']
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(len(data))
        return resp

    obj = s3.get_object(Bucket=R2_BUCKET, Key=filename)
    data = obj['Body'].read()

    resp = Response(data, mimetype='audio/mpeg')
    resp.headers['Accept-Ranges'] = 'bytes'
    return resp

@app.route('/art/<filename>')
@login_required
def art(filename):
    return send_file(
        os.path.join(app.static_folder, 'images/default.png'),
        mimetype='image/png'
    )

@app.route('/metadata/<filename>')
@login_required
def metadata(filename):
    title = os.path.splitext(filename)[0]
    artist = 'Unknown Artist'
    return jsonify({
        'title': title,
        'artist': artist
    })

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)

    return render_template('admin.html')


if __name__ == '__main__':
    app.run()
