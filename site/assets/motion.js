/* =========================================================
   LADLI — motion.js
   Premium micro-interactions built on anime.js, layered on
   top of the CSS-driven motion system in animations.css.
   Follows the same rules as the rest of the site's motion
   (github.com/emilkowalski/skills, emil-design-eng):
     - strong custom easing, never the library's linear default
     - only animate transform/opacity
     - short durations for anything interactive
   ========================================================= */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (typeof anime === 'undefined') return;

  const EASE_OUT = 'cubicBezier(0.23, 1, 0.32, 1)';

  /* ---------- 1. Hero heading entrance ---------- */
  // Preserved as stable HTML to avoid layout jump on page load

  /* ---------- 2. Animated stat counters (anime.js number tween) --- */
  document.querySelectorAll('.stat strong').forEach((el) => {
    const raw = el.textContent.trim();
    const match = raw.match(/^([\d,.]+)(.*)$/);
    if (!match) return;
    const target = parseFloat(match[1].replace(/,/g, ''));
    if (isNaN(target)) return;
    const suffix = match[2] || '';
    const isInt = Number.isInteger(target);
    el.textContent = '0' + suffix;

    const run = () => {
      const obj = { val: 0 };
      anime({
        targets: obj,
        val: target,
        duration: 1300,
        easing: EASE_OUT,
        round: isInt ? 1 : 10,
        update: () => { el.textContent = obj.val + suffix; },
      });
    };

    if (!reduceMotion && 'IntersectionObserver' in window) {
      const obs = new IntersectionObserver((entries) => {
        entries.forEach((entry) => { if (entry.isIntersecting) { run(); obs.unobserve(entry.target); } });
      }, { threshold: 0.4 });
      obs.observe(el);
    } else {
      el.textContent = raw;
    }
  });

  /* ---------- 3. Magnetic primary buttons (desktop only) ---------- */
  if (!reduceMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    document.querySelectorAll('.btn-primary, .back-to-top').forEach((btn) => {
      let raf = null;
      btn.addEventListener('mousemove', (e) => {
        const r = btn.getBoundingClientRect();
        const mx = (e.clientX - r.left - r.width / 2) * 0.18;
        const my = (e.clientY - r.top - r.height / 2) * 0.28;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          anime({ targets: btn, translateX: mx, translateY: my, duration: 350, easing: EASE_OUT });
        });
      });
      btn.addEventListener('mouseleave', () => {
        anime({ targets: btn, translateX: 0, translateY: 0, duration: 450, easing: 'spring(1, 80, 10, 0)' });
      });
    });
  }

  /* ---------- 4. Scroll progress bar ---------- */
  const progress = document.createElement('div');
  progress.id = 'scroll-progress';
  document.body.appendChild(progress);
  const updateProgress = () => {
    const h = document.documentElement;
    const scrolled = h.scrollTop;
    const height = h.scrollHeight - h.clientHeight;
    const pct = height > 0 ? (scrolled / height) * 100 : 0;
    progress.style.width = pct + '%';
  };
  updateProgress();
  window.addEventListener('scroll', updateProgress, { passive: true });

  /* ---------- 5. Parallax on hero decoration (subtle, capped) ---- */
  if (!reduceMotion) {
    const hero = document.querySelector('.hero');
    if (hero) {
      let ticking = false;
      window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          const rect = hero.getBoundingClientRect();
          const progressInHero = Math.min(1, Math.max(0, -rect.top / (rect.height || 1)));
          const shift = Math.min(40, progressInHero * 60);
          hero.style.setProperty('--parallax-shift', shift.toFixed(1) + 'px');
          ticking = false;
        });
      }, { passive: true });
    }
  }
})();
