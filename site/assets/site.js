(() => {
  // --- Mobile & Tablet Navigation Drawer Controller ---
  function initMobileNav() {
    const menuToggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('.nav');
    if (!menuToggle || !nav) return;

    // Create backdrop overlay if it doesn't already exist
    let backdrop = document.querySelector('.nav-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.className = 'nav-backdrop';
      document.body.appendChild(backdrop);
    }

    function openMenu() {
      menuToggle.setAttribute('aria-expanded', 'true');
      menuToggle.classList.add('is-active');
      nav.classList.add('is-open');
      backdrop.classList.add('is-visible');
      document.body.classList.add('menu-open');
    }

    function closeMenu() {
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.classList.remove('is-active');
      nav.classList.remove('is-open');
      backdrop.classList.remove('is-visible');
      document.body.classList.remove('menu-open');
      document.querySelectorAll('.nav-item.is-open').forEach(item => item.classList.remove('is-open'));
    }

    menuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = nav.classList.contains('is-open');
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    backdrop.addEventListener('click', closeMenu);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) {
        closeMenu();
      }
    });

    // Unified event delegation on nav
    nav.addEventListener('click', (e) => {
      e.stopPropagation();

      // Check if clicking the dropdown parent link or header area (e.g. Services)
      const navItem = e.target.closest('.nav-item');
      if (navItem && !e.target.closest('.mega')) {
        const isMobile = window.innerWidth <= 1024;
        if (isMobile) {
          e.preventDefault();
          e.stopPropagation();
          const wasOpen = navItem.classList.contains('is-open');
          document.querySelectorAll('.nav-item.is-open').forEach(other => {
            if (other !== navItem) other.classList.remove('is-open');
          });
          navItem.classList.toggle('is-open', !wasOpen);
          return;
        }
      }

      // If clicking any actual navigation link (e.g. Home, About Us, or a link inside .mega)
      const link = e.target.closest('a');
      if (link) {
        if (window.innerWidth <= 1024) {
          closeMenu();
        }
      }
    });

    // Close dropdowns on desktop when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.nav-item') && !e.target.closest('.menu-toggle')) {
        document.querySelectorAll('.nav-item.is-open').forEach(item => item.classList.remove('is-open'));
      }
    });

    // Close mobile nav automatically if window is resized above tablet breakpoint
    window.addEventListener('resize', () => {
      if (window.innerWidth > 1024 && nav.classList.contains('is-open')) {
        closeMenu();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileNav);
  } else {
    initMobileNav();
  }

  document.querySelectorAll('[data-year]').forEach(n => n.textContent = new Date().getFullYear());
  // Form submission is handled by assets/enhance.js (live FormSubmit integration).

  // --- Visitor Management: render the running visitor count ----------------
  // The badge shows a running total that goes up by one every time the site
  // is opened in a NEW browser tab — but not on a refresh or reload of a tab
  // that's already been counted. Each tab gets one random id
  // (crypto.randomUUID()) stored in sessionStorage ("ladli_visitor_id"),
  // which is scoped to that single tab: a refresh or in-tab navigation keeps
  // the same id (so it's not recounted), but a new tab always starts with
  // empty sessionStorage, so it's always treated as a new visit and
  // increments the total. Closing a tab does not decrement anything — this
  // is a running total, not a "currently open tabs" live count.
  (function initVisitorBadge() {
    const STORAGE_KEY = 'ladli_visitor_id';
    const CACHE_KEY = 'ladli_visitor_count_cache';

    const style = document.createElement('style');
    style.textContent = `
      .visitor-count-badge {
        position: fixed;
        bottom: 24px;
        left: 24px;
        z-index: 90;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 999px;
        background: var(--royal, #1f6fe5);
        color: #ffffff;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: .01em;
        white-space: nowrap;
        box-shadow: 0 4px 20px rgba(31, 111, 229, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.15);
        transition: opacity 0.3s ease, bottom 0.3s ease;
      }
      @media (max-width: 768px) {
        .visitor-count-badge {
          bottom: calc(74px + env(safe-area-inset-bottom, 0px));
          left: 12px;
          font-size: 11px;
          padding: 5px 10px;
        }
      }
      .visitor-count-badge .icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: none;
      }
      .visitor-count-badge .icon svg {
        width: 14px;
        height: 14px;
        display: block;
      }
    `;
    document.head.appendChild(style);

    let textSpan = null;
    let badge = null;

    function label(count) {
      return count.toLocaleString() + ' Total Visitors';
    }

    // Renders (or creates, on first call) the badge. Also called
    // immediately with a locally-cached number — if we have one — before
    // the network request resolves, so the badge appears fully formed on
    // first paint instead of popping in a moment later or flashing "0".
    function renderCount(count) {
      if (typeof count !== 'number' || Number.isNaN(count)) return;
      const text = label(count);
      if (!badge) {
        badge = document.createElement('div');
        badge.className = 'visitor-count-badge';
        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
        icon.setAttribute('aria-hidden', 'true');
        textSpan = document.createElement('span');
        textSpan.textContent = text;
        badge.appendChild(icon);
        badge.appendChild(textSpan);
        document.body.appendChild(badge);
      } else {
        textSpan.textContent = text;
      }
      try {
        localStorage.setItem(CACHE_KEY, String(count));
      } catch (e) { /* localStorage unavailable (private mode, quota, etc.) — non-critical */ }
    }

    // Paint instantly from whatever we displayed last time, so the badge
    // never flickers in empty and then jumps to a number a moment later.
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached !== null) renderCount(parseInt(cached, 10));
    } catch (e) { /* non-critical */ }

    let visitorId = null;
    let isNewVisitor = false;
    try {
      // sessionStorage (not localStorage) is deliberate here: it is scoped
      // to this ONE tab only. A refresh or in-tab navigation keeps the same
      // value (so it does not recount), but every new tab — even to the
      // same site, even in the same window — starts with empty
      // sessionStorage and so is always treated as a new visit.
      visitorId = sessionStorage.getItem(STORAGE_KEY);
      if (!visitorId) {
        visitorId = (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
          : 'visitor-' + Date.now() + '-' + Math.random().toString(16).slice(2);
        sessionStorage.setItem(STORAGE_KEY, visitorId);
        isNewVisitor = true;
      }
    } catch (e) {
      // No sessionStorage available at all — fall back to a per-page-load id.
      // This tab just won't be recognized as returning next time, but
      // the badge still renders a real total.
      visitorId = (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
        : 'visitor-' + Date.now() + '-' + Math.random().toString(16).slice(2);
      isNewVisitor = true;
    }

    if (isNewVisitor) {
      // Brand-new tab: record it. The backend only increments
      // the lifetime total the first time it ever sees this id, so even if
      // this fires more than once for any reason, the count stays correct.
      fetch('/api/visitor-register', {
        method: 'POST',
        cache: 'no-store',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visitor_id: visitorId }),
      })
        .then(res => (res.ok ? res.json() : null))
        .then(data => { if (data && data.ok) renderCount(data.count); })
        .catch(() => { /* non-critical */ });
    } else {
      // Already-known device: never re-report it as a visit, just fetch
      // and display the current lifetime total.
      fetch('/api/visitor-count', { cache: 'no-store', credentials: 'same-origin' })
        .then(res => (res.ok ? res.json() : null))
        .then(data => { if (data) renderCount(data.count); })
        .catch(() => { /* non-critical */ });
    }
  })();
})();