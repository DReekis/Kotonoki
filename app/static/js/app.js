// Kotonoki Core Client Application
document.addEventListener('DOMContentLoaded', () => {
  // 1. Configure HTMX CSRF protection
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta && window.htmx) {
    document.body.addEventListener('htmx:configRequest', (event) => {
      event.detail.headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
    });
  }

  // 2. Mobile Navigation Pane Drawer Toggle
  const navToggle = document.getElementById('nav-toggle-btn');
  const navClose = document.getElementById('nav-close-btn');
  const navPane = document.getElementById('navigation-pane');
  const navBackdrop = document.getElementById('nav-backdrop');

  function toggleNav(open) {
    if (!navPane) return;
    const shouldOpen = open !== undefined ? open : !navPane.classList.contains('open');
    navPane.classList.toggle('open', shouldOpen);
    if (navBackdrop) navBackdrop.classList.toggle('visible', shouldOpen);
    document.body.classList.toggle('nav-locked', shouldOpen);
  }

  if (navToggle) {
    navToggle.addEventListener('click', () => toggleNav(true));
  }
  if (navClose) {
    navClose.addEventListener('click', () => toggleNav(false));
  }
  if (navBackdrop) {
    navBackdrop.addEventListener('click', () => toggleNav(false));
  }

  // Auto-close drawer when branch link tapped on small screens
  if (navPane) {
    navPane.addEventListener('click', (e) => {
      if (e.target.closest('a') && window.innerWidth < 768) {
        toggleNav(false);
      }
    });
  }

  // 3. Local Draft Management (for /write)
  const writeForm = document.getElementById('dispatch-write-form');
  if (writeForm) {
    const titleInput = document.getElementById('dispatch-title-input');
    const branchInput = document.getElementById('dispatch-branch-input');
    const contentInput = document.getElementById('dispatch-content-input');
    const draftNotice = document.getElementById('draft-restore-banner');
    const restoreBtn = document.getElementById('restore-draft-btn');
    const discardBtn = document.getElementById('discard-draft-btn');

    const STORAGE_KEY = 'kotonoki_local_draft_v1';

    // Check for existing draft
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const data = JSON.parse(saved);
        if (data.title || data.content) {
          if (draftNotice) draftNotice.style.display = 'flex';
          if (restoreBtn) {
            restoreBtn.addEventListener('click', () => {
              if (titleInput && data.title) titleInput.value = data.title;
              if (branchInput && data.branch) branchInput.value = data.branch;
              if (contentInput && data.content) {
                contentInput.value = data.content;
                if (window.kotonokiEditor) {
                  window.kotonokiEditor.commands.setContent(data.content);
                }
              }
              if (draftNotice) draftNotice.style.display = 'none';
            });
          }
          if (discardBtn) {
            discardBtn.addEventListener('click', () => {
              localStorage.removeItem(STORAGE_KEY);
              if (draftNotice) draftNotice.style.display = 'none';
            });
          }
        }
      }
    } catch (e) {
      console.warn('LocalStorage error:', e);
    }

    // Auto-save draft on input (debounced)
    let saveTimeout = null;
    function saveDraft() {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        try {
          const draftData = {
            title: titleInput ? titleInput.value : '',
            branch: branchInput ? branchInput.value : '',
            content: contentInput ? contentInput.value : '',
            savedAt: new Date().toISOString()
          };
          // Don't save if totally blank
          if (draftData.title.trim() || draftData.content.trim()) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(draftData));
          }
        } catch (e) {}
      }, 500);
    }

    if (titleInput) titleInput.addEventListener('input', saveDraft);
    if (branchInput) branchInput.addEventListener('input', saveDraft);
    if (contentInput) contentInput.addEventListener('input', saveDraft);

    // Clear draft on successful submit
    writeForm.addEventListener('submit', () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (e) {}
    });
  }

  // 4. Sticky Desk Modal & Dragging Logic
  window.openStickyModal = function(url) {
    const container = document.getElementById('sticky-modal-container');
    if (!container) return;

    fetch(url, { headers: { 'HX-Request': 'true' } })
      .then(res => res.text())
      .then(html => {
        container.innerHTML = html;
        container.classList.add('active');
        document.body.classList.add('sticky-active');
        initStickyDraggable();
      })
      .catch(err => console.error('Failed to load sticky note:', err));
  };

  window.closeStickyModal = function() {
    const container = document.getElementById('sticky-modal-container');
    if (!container) return;
    container.classList.remove('active');
    container.innerHTML = '';
    document.body.classList.remove('sticky-active');
  };

  function initStickyDraggable() {
    const note = document.querySelector('.sticky-desk-note');
    const header = document.querySelector('.sticky-note-header');
    if (!note || !header) return;

    // Only allow drag on desktop screens (pointer device without touch coarse and >= 768px)
    if (window.matchMedia('(pointer: coarse)').matches || window.innerWidth < 768) return;

    let isDragging = false;
    let startX = 0, startY = 0;
    let initialLeft = 0, initialTop = 0;

    header.style.cursor = 'grab';

    header.addEventListener('pointerdown', (e) => {
      if (e.target.closest('button') || e.target.closest('a')) return;
      isDragging = true;
      header.style.cursor = 'grabbing';
      header.setPointerCapture(e.pointerId);

      const rect = note.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      initialLeft = rect.left;
      initialTop = rect.top;

      // Unset centering transform to prevent jump
      note.style.position = 'fixed';
      note.style.left = `${initialLeft}px`;
      note.style.top = `${initialTop}px`;
      note.style.transform = 'none';
      note.style.margin = '0';
    });

    header.addEventListener('pointermove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      let newLeft = initialLeft + dx;
      let newTop = initialTop + dy;

      // Keep inside viewport bounds
      const maxLeft = window.innerWidth - note.offsetWidth - 10;
      const maxTop = window.innerHeight - note.offsetHeight - 10;

      newLeft = Math.max(10, Math.min(newLeft, maxLeft));
      newTop = Math.max(10, Math.min(newTop, maxTop));

      note.style.left = `${newLeft}px`;
      note.style.top = `${newTop}px`;
    });

    function stopDrag(e) {
      if (isDragging) {
        isDragging = false;
        header.style.cursor = 'grab';
        try {
          header.releasePointerCapture(e.pointerId);
        } catch (err) {}
      }
    }

    header.addEventListener('pointerup', stopDrag);
    header.addEventListener('pointercancel', stopDrag);
  }

  // 5. Close sticky on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      window.closeStickyModal();
    }
  });

  // 6. Flash Alert Auto-dismissal
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    }, 6000);
  });

  // 7. Register Service Worker for PWA
  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  // 8. Clipped Memos (Private Local Reading Binder)
  window.toggleClipMemo = function(btn) {
    if (!btn) return;
    const id = btn.getAttribute('data-dispatch-id');
    const title = btn.getAttribute('data-dispatch-title') || 'Untitled';
    const branch = btn.getAttribute('data-dispatch-branch') || 'all';
    const author = btn.getAttribute('data-dispatch-author') || 'anonymous';
    const date = btn.getAttribute('data-dispatch-date') || '';

    try {
      let memos = JSON.parse(localStorage.getItem('kotonoki_clipped_memos') || '[]');
      const existsIndex = memos.findIndex(m => m.id === id);

      if (existsIndex >= 0) {
        // Unclip
        memos.splice(existsIndex, 1);
        btn.classList.remove('clipped');
        const label = btn.querySelector('.clip-btn-label');
        if (label) label.textContent = 'Clip';
      } else {
        // Clip
        memos.unshift({ id, title, branch, author, date, savedAt: new Date().toISOString() });
        btn.classList.add('clipped');
        const label = btn.querySelector('.clip-btn-label');
        if (label) label.textContent = 'Clipped';
      }

      localStorage.setItem('kotonoki_clipped_memos', JSON.stringify(memos));
      window.updateAllClipButtons();

      const badge = document.getElementById('clipped-count-badge');
      if (badge) badge.textContent = memos.length;
    } catch (e) {
      console.warn('Clip memo error:', e);
    }
  };

  window.updateAllClipButtons = function() {
    try {
      const memos = JSON.parse(localStorage.getItem('kotonoki_clipped_memos') || '[]');
      const clipIds = new Set(memos.map(m => m.id));

      document.querySelectorAll('.clip-memo-btn').forEach(btn => {
        const id = btn.getAttribute('data-dispatch-id');
        const isClipped = clipIds.has(id);
        btn.classList.toggle('clipped', isClipped);
        const label = btn.querySelector('.clip-btn-label');
        if (label) label.textContent = isClipped ? 'Clipped' : 'Clip';
      });

      const badge = document.getElementById('clipped-count-badge');
      if (badge) badge.textContent = memos.length;
    } catch (e) {}
  };

  window.updateAllClipButtons();

  // Re-run clip button state on HTMX partial content swaps
  document.body.addEventListener('htmx:afterSwap', () => {
    window.updateAllClipButtons();
  });

  // 9. Retro Reading Themes (Daylight -> Late-Night Lamp -> Amber CRT)
  const THEMES = ['default', 'lamp', 'amber'];
  const THEME_ICONS = {
    'default': '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0zm0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13zm8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5zM3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8zm10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0zm-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0zm9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707zM4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708z"/></svg>',
    'lamp': '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M5.5 2A2.5 2.5 0 0 1 8 .5 2.5 2.5 0 0 1 10.5 2h2a.5.5 0 0 1 .455.707l-2 4A.5.5 0 0 1 10.5 7h-5a.5.5 0 0 1-.455-.293l-2-4A.5.5 0 0 1 3.5 2h2zM7.5 8v4H5a.5.5 0 0 0 0 1h6a.5.5 0 0 0 0-1H8.5V8h-1zM2 15a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v.5a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5V15z"/></svg>',
    'amber': '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9.5l.5 2h2a.5.5 0 0 1 0 1h-8a.5.5 0 0 1 0-1h2l.5-2H2a2 2 0 0 1-2-2V4zm2-1a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H2z"/></svg>'
  };
  const THEME_LABELS = {
    'default': 'Daylight',
    'lamp': 'Lamp',
    'amber': 'Amber CRT'
  };

  window.cycleKotonokiTheme = function() {
    try {
      const current = localStorage.getItem('kotonoki_theme') || 'default';
      const currentIndex = THEMES.indexOf(current);
      const nextTheme = THEMES[(currentIndex + 1) % THEMES.length];

      if (nextTheme === 'default') {
        document.documentElement.removeAttribute('data-theme');
        localStorage.removeItem('kotonoki_theme');
      } else {
        document.documentElement.setAttribute('data-theme', nextTheme);
        localStorage.setItem('kotonoki_theme', nextTheme);
      }

      applyThemeLabels(nextTheme);
    } catch (e) {}
  };

  function applyThemeLabels(theme) {
    const iconHtml = THEME_ICONS[theme] || THEME_ICONS['default'];
    const labelText = THEME_LABELS[theme] || THEME_LABELS['default'];
    const iconEl = document.getElementById('theme-toggle-icon');
    const labelEl = document.getElementById('theme-toggle-label');
    if (iconEl) iconEl.innerHTML = iconHtml;
    if (labelEl) labelEl.textContent = labelText;
  }

  // Initialize theme label on page load
  const activeTheme = localStorage.getItem('kotonoki_theme') || 'default';
  applyThemeLabels(activeTheme);

  // 10. Web Audio API Tactile Typewriter Sound Synthesizer (for /write)
  class TypewriterSynthesizer {
    constructor() {
      this.ctx = null;
      this.enabled = localStorage.getItem('kotonoki_typewriter_sound') === 'true';
    }

    init() {
      if (!this.ctx && (window.AudioContext || window.webkitAudioContext)) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.ctx = new AudioCtx();
      }
      if (this.ctx && this.ctx.state === 'suspended') {
        this.ctx.resume();
      }
    }

    playKey() {
      if (!this.enabled) return;
      this.init();
      if (!this.ctx) return;

      try {
        const sampleRate = this.ctx.sampleRate;
        const bufferSize = Math.floor(sampleRate * 0.032); // 32ms micro-burst
        const buffer = this.ctx.createBuffer(1, bufferSize, sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
          const decay = Math.exp(-i / (sampleRate * 0.006));
          data[i] = (Math.random() * 2 - 1) * decay;
        }

        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1750 + Math.random() * 350;
        filter.Q.value = 2.8;

        const gain = this.ctx.createGain();
        gain.gain.value = 0.10;

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.ctx.destination);

        noise.start();
      } catch (e) {}
    }

    playEnter() {
      if (!this.enabled) return;
      this.init();
      if (!this.ctx) return;

      try {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(1760, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, this.ctx.currentTime + 0.16);

        gain.gain.setValueAtTime(0.07, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.16);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.16);
      } catch (e) {}
    }

    toggle() {
      this.enabled = !this.enabled;
      localStorage.setItem('kotonoki_typewriter_sound', this.enabled ? 'true' : 'false');
      if (this.enabled) {
        this.init();
        this.playKey();
      }
      return this.enabled;
    }
  }

  const typewriter = new TypewriterSynthesizer();
  const soundBtn = document.getElementById('typewriter-sound-btn');
  const soundLabel = document.getElementById('typewriter-sound-label');

  if (soundBtn) {
    if (typewriter.enabled) {
      soundBtn.classList.add('active');
      if (soundLabel) soundLabel.textContent = 'Sound: On';
    }

    soundBtn.addEventListener('click', () => {
      const isNowOn = typewriter.toggle();
      soundBtn.classList.toggle('active', isNowOn);
      if (soundLabel) soundLabel.textContent = isNowOn ? 'Sound: On' : 'Sound: Off';
    });
  }

  // Listen for typing events on editor & inputs
  document.addEventListener('keydown', (e) => {
    // Check if target is inside editor, input, or textarea
    const isEditing = e.target.closest('#tiptap-editor') ||
                      e.target.closest('#dispatch-title-input') ||
                      e.target.closest('#dispatch-branch-input') ||
                      e.target.tagName === 'INPUT' ||
                      e.target.tagName === 'TEXTAREA';

    if (isEditing && typewriter.enabled) {
      if (e.key === 'Enter') {
        typewriter.playEnter();
      } else if (!['Shift', 'Control', 'Alt', 'Meta', 'CapsLock', 'Tab'].includes(e.key)) {
        typewriter.playKey();
      }
    }

    // Global keyboard shortcut: Ctrl+K or / (when not focused in an input) opens Search
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !isEditing)) {
      e.preventDefault();
      const searchPageInput = document.getElementById('search-input');
      const headerInput = document.getElementById('global-header-search-input');
      if (searchPageInput) {
        searchPageInput.focus();
        searchPageInput.select();
      } else if (headerInput && window.innerWidth >= 768) {
        headerInput.focus();
        headerInput.select();
      } else if (window.location.pathname !== '/search') {
        window.location.href = '/search';
      }
    }
  });
});
