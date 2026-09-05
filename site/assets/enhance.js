/* =========================================================
   LADLI — Enhancement layer: scroll reveal, 3D tilt, header
   shrink, counters, back-to-top, page transitions, forms.
   Loaded after assets/site.js.
   ========================================================= */
(() => {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const body = document.body;

  if ('scrollRestoration' in window.history) {
    window.history.scrollRestoration = 'manual';
  }

  if (body) {
    body.classList.add('is-ready');
  }

  /* ---------- 0. LADLI Page Loader ---------- */
  // The inline <script> in each HTML page handles the initial loader fade-out smoothly.

  /* ---------- 1. Auto-tag elements for scroll reveal ---------- */
  const revealSelectors = [
    '.card', '.test-card', '.industry-card', '.article-card', '.download-item',
    '.split-copy', '.split-media', '.section-head', '.process-step', '.gas',
    '.contact-card', '.faq-list details', '.value-item', '.notice', '.stats-panel',
    '.cta-panel', '.photo-band', '.check-item', '.data-table'
  ];

  if (!reduceMotion && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.08,
      rootMargin: '0px 0px -20px 0px'
    });

    const vh = window.innerHeight;
    document.querySelectorAll(revealSelectors.join(',')).forEach((el, i) => {
      if (el.closest('.hero')) return;
      const rect = el.getBoundingClientRect();
      // If already in the initial viewport on page load, keep it naturally visible with no jump!
      if (rect.top < vh * 0.88) {
        el.classList.add('is-visible');
        return;
      }
      el.classList.add('reveal');
      el.style.setProperty('--d', (i % 4));
      el.classList.add('reveal-stagger');
      // Clean up will-change after the reveal transition completes to free GPU memory
      el.addEventListener('transitionend', function cleanup() {
        el.style.willChange = 'auto';
        el.removeEventListener('transitionend', cleanup);
      }, { once: true });
      io.observe(el);
    });
  } else {
    document.querySelectorAll(revealSelectors.join(',')).forEach(el => el.classList.add('is-visible'));
  }

  /* ---------- 2. Sticky header shrink on scroll ---------- */
  const header = document.querySelector('.site-header');
  if (header) {
    let headerTicking = false;
    const updateHeaderState = () => {
      header.classList.toggle('is-scrolled', window.scrollY > 24);
      headerTicking = false;
    };
    const onScroll = () => {
      if (!headerTicking) {
        headerTicking = true;
        window.requestAnimationFrame(updateHeaderState);
      }
    };
    updateHeaderState();
    window.addEventListener('scroll', onScroll, {
      passive: true
    });
  }

  /* ---------- 2b. Remove #site-loader from DOM after fade-out ---------- */
  const siteLoader = document.getElementById('site-loader');
  if (siteLoader) {
    if (siteLoader.classList.contains('loaded')) {
      // Already hidden — remove immediately
      siteLoader.remove();
    } else {
      siteLoader.addEventListener('transitionend', function onFade() {
        siteLoader.remove();
      }, { once: true });
      // Fallback: if transitionend never fires (e.g. instant), remove after 1s
      setTimeout(() => {
        if (siteLoader.parentNode) siteLoader.remove();
      }, 1000);
    }
  }

  /* ---------- 3. 3D tilt on cards (pointer-fine devices only) ---------- */
  if (!reduceMotion && window.matchMedia('(hover:hover) and (pointer:fine)').matches) {
    const tiltEls = document.querySelectorAll(
      '.card, .test-card, .industry-card, .article-card, .float-card, .contact-card, .gas'
    );
    tiltEls.forEach(el => {
      el.classList.add('tilt-3d');
      const strength = 10;
      el.addEventListener('mousemove', (e) => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        el.style.setProperty('--ry', (px * strength).toFixed(2) + 'deg');
        el.style.setProperty('--rx', (-py * strength).toFixed(2) + 'deg');
        el.style.setProperty('--tz', '6px');
      });
      el.addEventListener('mouseleave', () => {
        el.style.setProperty('--ry', '0deg');
        el.style.setProperty('--rx', '0deg');
        el.style.setProperty('--tz', '0px');
      });
    });

    // Cursor glow across the entire page
    const glow = document.createElement('div');
    glow.className = 'cursor-glow';
    document.body.appendChild(glow);
    document.addEventListener('mouseenter', () => glow.classList.add('is-active'));
    document.addEventListener('mouseleave', () => glow.classList.remove('is-active'));
    document.addEventListener('mousemove', (e) => {
      glow.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%,-50%)`;
    });
  }

  /* ---------- 3b. 3D tilt on the header logo ---------- */
  const brandStage = document.querySelector('[data-brand-logo]');
  if (brandStage && !reduceMotion) {
    const brandImg = brandStage.querySelector('img');
    if (brandImg) {
      const restTransform = 'perspective(700px) rotateX(0deg) rotateY(-8deg) translateZ(0) scale(1)';
      let leaveTimer = null;

      const applyTilt = (px, py, strength) => {
        clearTimeout(leaveTimer);
        brandStage.classList.add('is-tracking');
        brandImg.style.transform =
          `perspective(700px) rotateX(${(-py * strength).toFixed(2)}deg) rotateY(${(px * strength).toFixed(2)}deg) translateZ(10px) scale(1.05)`;
        brandImg.style.filter = 'drop-shadow(' + (-px * 10).toFixed(1) + 'px ' + (10 - py * 6).toFixed(1) + 'px 18px rgba(31,111,229,.32))';
      };
      const resetTilt = () => {
        brandImg.style.transform = restTransform;
        brandImg.style.filter = '';
        leaveTimer = setTimeout(() => {
          brandStage.classList.remove('is-tracking');
          brandImg.style.transform = '';
        }, 260);
      };

      if (window.matchMedia('(hover:hover) and (pointer:fine)').matches) {
        // Desktop / mouse — tilt follows the cursor while hovering.
        brandStage.addEventListener('mousemove', (e) => {
          const r = brandStage.getBoundingClientRect();
          applyTilt((e.clientX - r.left) / r.width - 0.5, (e.clientY - r.top) / r.height - 0.5, 14);
        });
        brandStage.addEventListener('mouseleave', resetTilt);
      } else {
        // Touch — no hover to hook into, so a tap/press tilts the logo
        // toward the finger, then eases back on release. This is what
        // makes the 3D effect actually visible on a phone, on top of
        // the continuous idle wobble in the CSS.
        brandStage.addEventListener('touchstart', (e) => {
          const t = e.touches[0];
          if (!t) return;
          const r = brandStage.getBoundingClientRect();
          applyTilt((t.clientX - r.left) / r.width - 0.5, (t.clientY - r.top) / r.height - 0.5, 20);
        }, { passive: true });
        brandStage.addEventListener('touchmove', (e) => {
          const t = e.touches[0];
          if (!t) return;
          const r = brandStage.getBoundingClientRect();
          applyTilt((t.clientX - r.left) / r.width - 0.5, (t.clientY - r.top) / r.height - 0.5, 20);
        }, { passive: true });
        brandStage.addEventListener('touchend', resetTilt);
        brandStage.addEventListener('touchcancel', resetTilt);
      }
    }
  }

  /* ---------- 4. Animated number counters ---------- */
  // Stat counter animation is handled exclusively by motion.js (anime.js).
  // Previously duplicated here, causing a double-flash race condition.

  /* ---------- 5. Back to top ---------- */
  const backBtn = document.createElement('button');
  backBtn.className = 'back-to-top';
  backBtn.setAttribute('aria-label', 'Back to top');
  backBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  document.body.appendChild(backBtn);
  window.addEventListener('scroll', () => {
    backBtn.classList.toggle('is-visible', window.scrollY > 500);
  }, {
    passive: true
  });
  backBtn.addEventListener('click', () => window.scrollTo({
    top: 0,
    behavior: reduceMotion ? 'auto' : 'smooth'
  }));

  /* ---------- 6. Form handling (contact / request-quote) ---------- */
  // Forms post to the local Flask backend at /api/contact and /api/quote.
  // Static action/method + name attributes in the HTML are a fallback for
  // when JS is unavailable; here we upgrade to a smooth AJAX submission.
  document.querySelectorAll('[data-demo-form]').forEach(form => {
    if (!form.getAttribute('action')) return; // safety: skip if unwired

    const statusEl = form.querySelector('.form-status');
    if (statusEl) {
      statusEl.classList.add('form-toast');
      statusEl.textContent = '';
    }

    const setToast = (msg, type) => {
      if (!statusEl) return;
      statusEl.textContent = msg;
      statusEl.className = 'form-toast is-visible ' + type;
    };

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        if (!submitBtn.querySelector('.btn-label')) {
          submitBtn.innerHTML = `<span class="btn-label">${submitBtn.innerHTML}</span>`;
        }
        submitBtn.classList.add('is-loading');
      }
      setToast('Sending your enquiry…', 'sending');

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {
            'Accept': 'application/json'
          }
        });
        if (res.ok) {
          setToast('Thank you — your enquiry has been sent. Our team will contact you shortly.', 'success');
          form.reset();
        } else {
          throw new Error('Submission failed');
        }
      } catch (err) {
        setToast('We could not send this automatically. Please call +91 84908 38981 or email ladlielec@gmail.com.', 'error');
      } finally {
        if (submitBtn) submitBtn.classList.remove('is-loading');
      }
    });
  });

  // --- 8. Number inputs: clamp to declared min/max as the user leaves the field ---
  document.querySelectorAll('input[type="number"][min], input[type="number"][max]').forEach(input => {
    input.addEventListener('blur', () => {
      if (input.value === '') return;
      const num = Number(input.value);
      if (Number.isNaN(num)) return;
      const min = input.min !== '' ? Number(input.min) : null;
      const max = input.max !== '' ? Number(input.max) : null;
      if (min !== null && num < min) input.value = String(min);
      else if (max !== null && num > max) input.value = String(max);
    });
  });

  // --- 9. Animated favicon ---
  // Chrome/Edge/Safari intentionally freeze favicon animation (CSS keyframes,
  // SMIL, even animated GIFs all show only the first frame — this is a known,
  // deliberate browser limitation, not a bug in the SVG). The reliable
  // cross-browser workaround is to cycle pre-rendered static frames through a
  // JS-controlled <link> element instead of relying on the browser to animate
  // one image internally.
  // Limited to 3 full cycles to reduce idle CPU load.
  (function animatedFavicon() {
    const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    const FRAME_COUNT = 12;
    const INTERVAL_MS = 150;
    const MAX_CYCLES = 3;
    const base = 'assets/images/favicon-frames/frame-';

    const frames = [];
    for (let i = 0; i < FRAME_COUNT; i++) {
      frames.push(base + String(i).padStart(2, '0') + '.png');
    }
    frames.forEach(src => { const img = new Image(); img.src = src; });

    const iconLinks = Array.from(document.querySelectorAll('link[rel="icon"], link[rel="shortcut icon"]'));
    if (iconLinks.length === 0) {
      const link = document.createElement('link');
      link.rel = 'icon';
      link.type = 'image/png';
      document.head.appendChild(link);
      iconLinks.push(link);
    }

    let i = 0;
    let timer = null;
    let totalTicks = 0;
    const maxTicks = MAX_CYCLES * FRAME_COUNT;

    function tick() {
      const frame = frames[i];
      iconLinks.forEach(link => {
        link.href = frame;
      });
      i = (i + 1) % frames.length;
      totalTicks++;
      if (totalTicks >= maxTicks) {
        stop();
      }
    }

    function start() {
      if (timer || totalTicks >= maxTicks) return;
      tick();
      timer = setInterval(tick, INTERVAL_MS);
    }

    function stop() {
      if (timer) { clearInterval(timer); timer = null; }
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop(); else start();
    });

    if (!document.hidden) start();
  })();
})();