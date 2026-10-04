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
});
