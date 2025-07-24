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

  // When metadata (incl. duration) is loaded, update the total time
  audioPlayer.addEventListener('loadedmetadata', () => {
    durationTimeEl.textContent = formatTime(audioPlayer.duration);
  });



  // ─── Upload Handler ───────────────────────────────────────────────────────────
  if (uploadBtn && fileInput) {
    uploadBtn.onclick = () => {
      const fileList = fileInput.files;
      if (!fileList.length) {
        return alert("Select at least one file first");
      }
      if (fileList.length > 50) {
        return alert("Please select up to 50 files");
      }

      // Build FormData
      const form = new FormData();
      for (const f of fileList) {
        form.append("files", f);
      }

      // Show progress bar
      const container = document.getElementById("uploadProgressContainer");
      const bar       = document.getElementById("uploadProgressBar");
      container.style.display = "block";
      bar.style.width = "0%";
      bar.textContent = "0%";

      // Send via XHR to get upload progress events
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/upload", true);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          bar.style.width = pct + "%";
          bar.textContent = pct + "%";
        }
      };
      xhr.onload = () => {
        // on success, reload to show flash and updated list
        window.location.reload();
      };
      xhr.onerror = () => {
        alert("Upload failed due to a network error.");
      };
      xhr.send(form);
    };
  }

  // ─── Load & Render Song List ─────────────────────────────────────────────────
  async function loadSongs() {
    const res = await fetch('/songs');
    if (!res.ok) {
      console.error('Failed to fetch songs');
      return;
    }
    const songs = await res.json();
    playlist = songs.map(s => ({
      ...s,
      url: s.public_url   // <-- use the bucket URL
    }));
    tableBody.innerHTML = '';
    songs.forEach((song, i) => {
      const row = tableBody.insertRow();
      row.innerHTML = `
        <th scope="row">${i + 1}</th>
        <td class="d-flex align-items-center" style="cursor: pointer;">
         <img src="/art/${encodeURIComponent(song.filename)}"
            alt="Art"
             class="table-art me-2">
          <div>
            <strong>${song.title}</strong><br>
            ${song.artist ? `<small>${song.artist}</small>` : ''}
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

    // 1) Highlight the selected row
    document.querySelectorAll('#songTable tbody tr')
      .forEach(r => r.classList.remove('table-active'));
    const rows = document.querySelectorAll('#songTable tbody tr');
    if (rows[i]) {
      rows[i].classList.add('table-active');
      rows[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // 2) Grab our track object
    const track = playlist[i];  // { filename, title, artist, url }

    // 3) Update UI
    currentTrack.textContent = track.artist
      ? `${track.title} — ${track.artist}`
      : track.title;
    albumArt.src = `/art/${encodeURIComponent(track.filename)}`;

    // 4) Load & play from the bucket URL
    audioPlayer.src = track.url;
    await audioPlayer.play();
    playPauseBtn.textContent = '⏸️';

    // 5) Reset & display duration
    elapsedTimeEl.textContent = '0:00';
    
    audioPlayer.onloadedmetadata = () => {
      durationTimeEl.textContent = formatTime(audioPlayer.duration);
    };
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
