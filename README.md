# Vilcore Player

A lightweight, sleek, and feature-rich web-based music player. Built with a Python/Flask backend and a responsive HTML/vanilla JavaScript frontend using Bootstrap 5. 

## 🌟 Features

- **Audio Playback**: Custom HTML5 audio player with play, pause, skip, and progress bar seeking.
- **Play Modes**: Supports *Repeat All*, *Repeat One*, and *Shuffle*.
- **Metadata & Album Art**: Automatically extracts ID3 tags (Title, Artist, Album Art) from uploaded files using `mutagen`. Falls back to the iTunes API to find missing album art.
- **Audio Streaming**: Efficient file streaming via HTTP `206 Partial Content` Range requests.
- **Authentication**: Built-in login/registration system using `Flask-Login`.
- **Admin Uploads**: Secure, multi-file drag-and-drop uploading restricted to Admin users.
- **Dark Mode**: Beautiful toggleable dark/light mode that remembers your preference.
- **Keyboard Shortcuts**:
  - `Space`: Play/Pause
  - `Left/Right Arrows`: Previous/Next track
  - `Shift + Left/Right Arrows`: Rewind/Fast-forward 5 seconds
  - `Up/Down Arrows`: Volume Up/Down

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Flask-Login, Flask-CORS
- **Audio Processing**: Mutagen (ID3 tags), Werkzeug
- **Frontend**: HTML5, Vanilla JavaScript, CSS3
- **UI Framework**: Bootstrap 5, FontAwesome 6

## 🚀 Getting Started

### Prerequisites
Make sure you have Python 3.7+ installed on your machine.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/vilcore-player.git
   cd vilcore-player
   ```

2. **Set up a virtual environment (Optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the required dependencies:**
   ```bash
   pip install Flask Flask-CORS Flask-Login Werkzeug mutagen requests
   ```
   *(Note: You can also freeze these into a `requirements.txt` file by running `pip freeze > requirements.txt`)*

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Access the web app:**
   Open your browser and navigate to `http://127.0.0.1:5000`

## 🎧 Usage

1. **Upload**: As an admin, use the upload button at the top to select and upload `.mp3` or `.wav` files.
2. **Play**: Click any song in the list to start listening!

## 📁 Project Structure

```text
vilcore-player/
│
├── app.py                 # Main Flask application and API routes
├── uploads/               # Directory where uploaded audio files are stored
├── static/
│   ├── css/style.css      # Custom styles and dark mode overrides
│   ├── script.js          # Player logic, API calls, and UI interactions
│   └── images/            # Default album art and static assets
└── templates/
    ├── base.html          # Base layout, navbar, and sticky footer player
    ├── index.html         # Main playlist and upload UI
    ├── login.html         # Login page
    ├── register.html      # Registration page
    └── admin.html         # Admin dashboard
```

## 📝 License
This project is open-source and available under the MIT License.
