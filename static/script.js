document.addEventListener("DOMContentLoaded", () => {
  const fileInput    = document.getElementById('fileInput');
  const uploadBtn    = document.getElementById('uploadBtn');
  const tableBody    = document.querySelector('#songTable tbody');
  const audioPlayer  = new Audio();
  const playPauseBtn = document.getElementById('playPauseBtn');
  const prevBtn      = document.getElementById('prevBtn');
  const nextBtn      = document.getElementById('nextBtn');
  const progressBar  = document.getElementById('progressBar');
  const currentTrack = document.getElementById('currentTrack');
  const logoutBtn    = document.getElementById('logoutBtn');
  const dmToggle     = document.getElementById('dmToggle');
  const albumArt      = document.getElementById('albumArt');
  const elapsedTimeEl = document.getElementById('elapsedTime');
  const durationTimeEl= document.getElementById('durationTime');
  const playModeBtn = document.getElementById('playModeBtn');
  playModeBtn.onclick = togglePlayMode;



  let playlist = [];
  let currentIndex = -1;
  let playMode = 'repeat-all';  // Modes: 'repeat-one', 'repeat-all', 'shuffle'
  let shuffledIndices = [];       // Tracks played songs in shuffle mode


  // Helper to format seconds as M:SS
  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  // ─── Upload Handler ───────────────────────────────────────────────────────────
  if (uploadBtn && fileInput) {
    uploadBtn.onclick = async () => {
      if (!fileInput.files[0]) {
        return alert('Select a file first');
      }
      const form = new FormData();
      form.append('file', fileInput.files[0]);

      const res = await fetch('/upload', {
        method: 'POST',
        body: form
      });

      if (res.ok) {
        window.location.reload();  // Let Flask flash handle the message

        fileInput.value = '';
        loadSongs();
      } else {
        const msg = document.createElement('div');
        msg.className = 'alert alert-danger';
        msg.textContent = 'Upload failed';
        document.body.prepend(msg);
        setTimeout(() => msg.remove(), 3000);
      }

    };
  }

  // ─── Load & Render Song List ─────────────────────────────────────────────────
  async function loadSongs() {
    const res = await fetch('/songs');  
    if (!res.ok) {
      console.error('Failed to fetch songs');
      return;
    }

    const files = await res.json();

    // Store full metadata (not just filename)
    playlist = files.map(f => ({
      filename: f.filename,
      title: f.title,
      artist: f.artist,
      url: f.public_url
    }));
    shuffledIndices = generateShuffledIndices(playlist.length);

    tableBody.innerHTML = '';

    files.forEach((file, i) => {
      const row = tableBody.insertRow();
      row.innerHTML = `
        <th scope="row">${i + 1}</th>
        <td class="d-flex align-items-center" style="cursor: pointer;">
          <img src="/art/${encodeURIComponent(file.filename)}"
               alt="Art"
               class="me-2"
               style="width: 32px; height: 32px; object-fit: cover; border-radius: 4px;">
          <div>
            <strong>${file.title}</strong><br>
            ${file.artist && file.artist.toLowerCase() !== 'unknown'
              ? `<small class="text-muted">${file.artist}</small>`
              : ''}
         </div>
        </td>
      `;
      row.onclick = () => playTrack(i);
    });
  }


  function generateShuffledIndices(length) {
    const indices = Array.from({ length }, (_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  }


  // ─── Playback Controls ────────────────────────────────────────────────────────
  async function playTrack(i) {
    if (i < 0 || i >= playlist.length) return;
    currentIndex = i;
    
    // Remove existing highlight
    document.querySelectorAll('#songTable tbody tr').forEach(row => {
    row.classList.remove('table-active');
    });

    // Highlight current row
    const rows = document.querySelectorAll('#songTable tbody tr');
    if (rows[i]) {
      rows[i].classList.add('table-active');
    }

    // Scroll into view
    if (rows[i]) {
      rows[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    
    const name = playlist[i];

    // 1️⃣ Fetch metadata
    let meta = { title: name.replace(/\.\w+$/, ''), artist: '' };
    try {
      const res = await fetch(`/metadata/${encodeURIComponent(name)}`);
      if (res.ok) {
        meta = await res.json();
      }
    } catch (e) {
      console.warn('Metadata fetch failed, using filename');
    }

    // 2️⃣ Update UI
    const artistClean = meta.artist?.toLowerCase().trim();
    currentTrack.textContent =
      artistClean && artistClean !== 'unknown artist'
        ? `${meta.title} — ${meta.artist}`
        : meta.title;

    // 3️⃣ Load and play
    audioPlayer.src = playlist[i].url;
    audioPlayer.play();
    // currentTrack.textContent = formatTitle(playlist[i]);

    playPauseBtn.textContent = '⏸️';

    // 4️⃣ Reset times
    elapsedTimeEl.textContent  = '0:00';
    durationTimeEl.textContent = '0:00';

    // 5️⃣ When metadata is loaded, set duration
    audioPlayer.onloadedmetadata = () => {
      durationTimeEl.textContent = formatTime(audioPlayer.duration);
    };

    // 6️⃣ Fetch album art (you already have this)
    albumArt.src = `/art/${encodeURIComponent(name)}`;
  }

  function togglePlayMode() {
    if (playMode === 'repeat-one') {
      playMode = 'repeat-all';
      playModeBtn.textContent = '🔁';
      playModeBtn.title = 'Repeat All';
    } else if (playMode === 'repeat-all') {
      playMode = 'shuffle';
      playModeBtn.textContent = '🔀';
      playModeBtn.title = 'Shuffle';
    } else {
      playMode = 'repeat-one';
      playModeBtn.textContent = '🔂';
      playModeBtn.title = 'Repeat One';
    }
  }


  if (playPauseBtn) {
    playPauseBtn.onclick = () => {
      if (audioPlayer.paused) {
        audioPlayer.play();
        playPauseBtn.textContent = '⏸️';
      } else {
        audioPlayer.pause();
        playPauseBtn.textContent = '▶️';
      }
    };
  }

  if (nextBtn) {
    nextBtn.onclick = () => {
      playTrack((currentIndex + 1) % playlist.length);
    };
  }

  if (prevBtn) {
    prevBtn.onclick = () => {
      playTrack((currentIndex - 1 + playlist.length) % playlist.length);
    };
  }

  audioPlayer.ontimeupdate = () => {
    if (!audioPlayer.duration) return;
    const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
    progressBar.style.width = pct + '%';
    elapsedTimeEl.textContent = formatTime(audioPlayer.currentTime);
  };

  audioPlayer.onended = () => {
    if (playMode === 'repeat-one') {
      playTrack(currentIndex);

    } else if (playMode === 'repeat-all') {
      if (currentIndex + 1 < playlist.length) {
        playTrack(currentIndex + 1);
      }

    } else if (playMode === 'shuffle') {
      const nextIndexInShuffle = shuffledIndices.indexOf(currentIndex) + 1;
      if (nextIndexInShuffle < shuffledIndices.length) {
        playTrack(shuffledIndices[nextIndexInShuffle]);
      }
    }
  };


  // Keyboard Shortcuts _________________________________________________________
  document.addEventListener('keydown', (e) => {
    const tag = document.activeElement.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;

    // Use e.code for Space, and handle shift+arrows
    if (e.code === 'Space') {
      e.preventDefault();
      if (audioPlayer.paused) {
        audioPlayer.play();
        playPauseBtn.textContent = '⏸️';
      } else {
        audioPlayer.pause();
        playPauseBtn.textContent = '▶️';
      }
    } else if (e.shiftKey && e.code === 'ArrowRight') {
      e.preventDefault();
      audioPlayer.currentTime = Math.min(audioPlayer.currentTime + 5, audioPlayer.duration);
    } else if (e.shiftKey && e.code === 'ArrowLeft') {
      e.preventDefault();
      audioPlayer.currentTime = Math.max(audioPlayer.currentTime - 5, 0);
    } else if (e.code === 'ArrowRight') {
      e.preventDefault();
      nextBtn?.click();
    } else if (e.code === 'ArrowLeft') {
      e.preventDefault();
      prevBtn?.click();
    } else if (e.code === 'ArrowUp') {
      e.preventDefault();
      audioPlayer.volume = Math.min(audioPlayer.volume + 0.1, 1);
      localStorage.setItem('volume', audioPlayer.volume);
    } else if (e.code === 'ArrowDown') {
      e.preventDefault();
      audioPlayer.volume = Math.max(audioPlayer.volume - 0.1, 0);
      localStorage.setItem('volume', audioPlayer.volume);
    }
  });


  // Seek functionality on progress bar
  const progressContainer = document.getElementById('progressContainer');
  if (progressContainer) {
    progressContainer.onclick = function (e) {
      if (!audioPlayer.duration) return;

        const rect = progressContainer.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const width = rect.width;
        const percent = clickX / width;
      audioPlayer.currentTime = percent * audioPlayer.duration;
    };
  }


  // ─── Logout Handler ───────────────────────────────────────────────────────────
  if (logoutBtn) {
    logoutBtn.onclick = async () => {
      await fetch('/logout');
      window.location.href = '/login';
    };
  }

  // ─── Dark Mode Toggle ────────────────────────────────────────────────────────

  // Dark Mode Toggle Logic
  function applyMode(mode) {
    document.body.classList.toggle('dark-mode', mode === 'dark');
  }
  const savedMode = localStorage.getItem('mode') || 'light';
  applyMode(savedMode);

  if (dmToggle) {
    dmToggle.onclick = () => {
      const newMode = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
      localStorage.setItem('mode', newMode);
      applyMode(newMode);
    };
  }

  // ─── Initial Load ─────────────────────────────────────────────────────────────
  loadSongs();
});
