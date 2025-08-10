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
    const files = fileInput.files;
    if (!files || files.length === 0) {
      return alert('Select a file first');
    }

    // limit to 50 files
    const toUpload = Array.from(files).slice(0, 50);

    // Create a little upload UI container at top of page
    let container = document.getElementById('uploadProgressContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'uploadProgressContainer';
      container.style.margin = '10px';
      document.body.prepend(container);
    }
    container.innerHTML = ''; // clear previous

    // helper to upload a single file and show progress
    function uploadSingleFile(file) {
      return new Promise((resolve, reject) => {
        const row = document.createElement('div');
        row.className = 'mb-2';
        row.innerHTML = `
          <div><strong>${file.name}</strong></div>
          <div class="progress" style="height: 10px;">
            <div class="progress-bar" role="progressbar" style="width:0%"></div>
          </div>
          <div class="small text-muted mt-1 status">Waiting...</div>
        `;
        container.appendChild(row);

        const progressBar = row.querySelector('.progress-bar');
        const status = row.querySelector('.status');

        const form = new FormData();
        // send as single-file field (server accepts 'file' or 'files')
        form.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload', true);

        xhr.upload.onprogress = function (ev) {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            progressBar.style.width = pct + '%';
            progressBar.textContent = pct + '%';
          }
        };

        xhr.onload = function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const json = JSON.parse(xhr.responseText);
              // server responds with results array for this single file request
              const r = (json.results && json.results[0]) || json;
              if (r && r.status === 'ok') {
                status.textContent = 'Uploaded';
                status.classList.add('text-success');
                resolve(r);
              } else {
                status.textContent = 'Failed: ' + (r.error || JSON.stringify(r));
                status.classList.add('text-danger');
                reject(r);
              }
            } catch (e) {
              status.textContent = 'Uploaded (no JSON response)';
              status.classList.add('text-success');
              resolve({status: 'ok'});
            }
          } else {
            status.textContent = 'Upload failed (' + xhr.status + ')';
            status.classList.add('text-danger');
            reject({status: 'error', code: xhr.status});
          }
        };

        xhr.onerror = function () {
          status.textContent = 'Network error';
          status.classList.add('text-danger');
          reject({status: 'error', reason: 'network'});
        };

        xhr.send(form);
      });
    }

    // sequential upload to avoid many simultaneous connections
    for (const f of toUpload) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await uploadSingleFile(f);
      } catch (err) {
        console.warn('Upload error', err);
        // continue to next file (you can stop instead if you prefer)
      }
    }

    // Finished: refresh song list (small delay to allow server)
    setTimeout(loadSongs, 700);
    // clear file input
    fileInput.value = '';
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
    playlist = files.map(f => f.filename); // for playTrack()
    shuffledIndices = generateShuffledIndices(playlist.length);

    tableBody.innerHTML = '';

    files.forEach((file, i) => {
      const row = tableBody.insertRow();
      row.innerHTML = `
        <th scope="row">${i + 1}</th>
        <td class="d-flex align-items-center" style="cursor: pointer;">
          <img src="/art/${encodeURIComponent(file.filename)}"
              alt="Art"
              class="me-2 song-thumb">
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
    // audioPlayer.src = `/stream/${encodeURIComponent(name)}`;
    // audioPlayer.play();
    // playPauseBtn.textContent = '⏸️';
    audioPlayer.src = `/stream/${encodeURIComponent(playlist[i])}`;
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
