/* =========================================================
   LADLI Admin Portal — shared helpers
   ========================================================= */

const Admin = (() => {
  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      credentials: 'same-origin',
      ...options,
    });
    if (res.status === 401) {
      window.location.href = '/admin/login';
      throw new Error('Not authenticated');
    }
    let body = null;
    try { body = await res.json(); } catch (e) { /* no body */ }
    if (res.status === 403 && body && body.must_change_password) {
      // Account is locked to the change-password screen until it sets a
      // new password (fresh install, or an admin-forced reset).
      if (!/\/admin\/settings/.test(window.location.pathname)) {
        window.location.href = '/admin/settings';
      }
      throw new Error('Password change required.');
    }
    if (!res.ok) {
      throw new Error((body && body.error) || 'Request failed');
    }
    return body;
  }

  async function requireAuth() {
    try {
      const me = await api('/api/admin/me');
      if (!me.logged_in) {
        window.location.href = '/admin/login';
        return null;
      }
      if (me.must_change_password && !/\/admin\/settings/.test(window.location.pathname)) {
        window.location.href = '/admin/settings';
        return null;
      }
      return me;
    } catch (e) {
      window.location.href = '/admin/login';
      return null;
    }
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function timeAgo(iso) {
    if (!iso) return '';
    const then = new Date(iso + 'Z').getTime();
    const diff = Math.max(0, Date.now() - then);
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  function wireLogout(el) {
    if (!el) return;
    el.addEventListener('click', async (e) => {
      e.preventDefault();
      try { await api('/api/admin/logout', { method: 'POST' }); } catch (err) { /* ignore */ }
      window.location.href = '/admin/login';
    });
  }

  function wireMobileSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (!toggle || !sidebar) return;
    toggle.addEventListener('click', () => sidebar.classList.toggle('is-open'));
  }

  /**
   * Wires every password input on the page with a show/hide toggle button.
   * Expects markup of the form:
   *   <div class="password-field">
   *     <input type="password" ...>
   *     <button type="button" class="password-toggle" aria-label="Show password">…icons…</button>
   *   </div>
   * Safe to call on any page — it's a no-op if there are no .password-field wrappers.
   */
  function wirePasswordToggles() {
    document.querySelectorAll('.password-field').forEach((wrapper) => {
      const input = wrapper.querySelector('input');
      const btn = wrapper.querySelector('.password-toggle');
      if (!input || !btn) return;
      btn.addEventListener('click', () => {
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        btn.classList.toggle('is-visible', !showing);
        btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
        // Keep focus + cursor position on the field rather than the button,
        // so the person can keep typing right where they left off.
        input.focus();
      });
    });
  }

  return { api, requireAuth, escapeHtml, timeAgo, wireLogout, wireMobileSidebar, wirePasswordToggles };
})();


/* =========================================================
   LADLI Admin Portal — "Oil Lab" micro-interactions
   ---------------------------------------------------------
   Purely additive/decorative. Does not read, write, or
   otherwise touch application data. Never calls
   preventDefault() and never removes existing listeners,
   so it runs safely alongside the Admin helpers above and
   each page's own inline bootstrap script.
   ========================================================= */

(function () {
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  /* ---------- 1. Liquid ripple on buttons ---------- */
  function wireRipples() {
    document.addEventListener('pointerdown', function (e) {
      if (reduceMotion) return;
      var btn = e.target.closest && e.target.closest('.btn');
      if (!btn) return;

      var rect = btn.getBoundingClientRect();
      var ripple = document.createElement('span');
      var size = Math.max(rect.width, rect.height) * 1.4;

      ripple.setAttribute('aria-hidden', 'true');
      ripple.style.position = 'absolute';
      ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
      ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
      ripple.style.width = size + 'px';
      ripple.style.height = size + 'px';
      ripple.style.borderRadius = '50%';
      ripple.style.pointerEvents = 'none';
      ripple.style.background = 'radial-gradient(circle, rgba(255,255,255,0.55), rgba(255,255,255,0) 70%)';
      ripple.style.transform = 'scale(0)';
      ripple.style.opacity = '0.9';
      ripple.style.transition = 'transform 550ms cubic-bezier(0.23,1,0.32,1), opacity 550ms ease';

      var prevPosition = getComputedStyle(btn).position;
      if (prevPosition === 'static') btn.style.position = 'relative';
      btn.appendChild(ripple);

      requestAnimationFrame(function () {
        ripple.style.transform = 'scale(1)';
        ripple.style.opacity = '0';
      });

      setTimeout(function () {
        if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
      }, 600);
    }, { passive: true });
  }

  /* ---------- 2. Flash stat values when their text changes ---------- */
  function wireStatValuePulses() {
    var targets = document.querySelectorAll('.stat-value');
    if (!targets.length || !window.MutationObserver) return;

    targets.forEach(function (el) {
      var lastText = el.textContent;
      var observer = new MutationObserver(function () {
        if (el.textContent === lastText) return;
        lastText = el.textContent;
        if (reduceMotion) return;
        el.classList.remove('is-updated');
        // eslint-disable-next-line no-unused-expressions
        void el.offsetWidth; // restart animation
        el.classList.add('is-updated');
      });
      observer.observe(el, { characterData: true, childList: true, subtree: true });
    });
  }

  /* ---------- 3. Gentle tilt on report/document cards ---------- */
  function wireCardTilt() {
    if (reduceMotion || !window.matchMedia || !window.matchMedia('(hover: hover)').matches) return;

    document.addEventListener('pointermove', function (e) {
      var card = e.target.closest && e.target.closest('.doc-card');
      if (!card) return;
      var rect = card.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = 'translateY(-4px) rotateX(' + (py * -4).toFixed(2) + 'deg) rotateY(' + (px * 4).toFixed(2) + 'deg)';
    }, { passive: true });

    document.addEventListener('pointerleave', function (e) {
      var card = e.target.closest && e.target.closest('.doc-card');
      if (!card) return;
      card.style.transform = '';
    }, true);
  }

  ready(function () {
    wireRipples();
    wireStatValuePulses();
    wireCardTilt();
  });
})();
