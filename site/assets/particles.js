/* =========================================================
   LADLI — particles.js
   A very sparse, slow-drifting ambient particle layer behind
   every hero section, in brand colors. Intentionally subtle:
   this is a premium accent, not a focal effect — it must never
   compete with the headline or the 3D component for attention.
   ========================================================= */
(() => {
  const mounts = document.querySelectorAll('.hero-particles-mount');
  if (!mounts.length || typeof tsParticles === 'undefined') return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (window.matchMedia('(max-width: 640px)').matches) return; // skip on phones — keep it light

  const config = {
    fullScreen: { enable: false },
    background: { color: { value: 'transparent' } },
    // The particles drift very slowly, so a lower fps ceiling is visually
    // identical but roughly halves the idle CPU/GPU cost of this layer.
    fpsLimit: 30,
    detectRetina: true,
    particles: {
      number: { value: 16, density: { enable: true, area: 900 } },
      color: { value: ['#1F6FE5', '#67C5F8', '#E95AA5', '#F9A825'] },
      shape: { type: 'circle' },
      opacity: { value: { min: 0.12, max: 0.32 } },
      size: { value: { min: 1.5, max: 4 } },
      links: { enable: false },
      move: {
        enable: true,
        speed: 0.35,
        direction: 'none',
        random: true,
        straight: false,
        outModes: { default: 'out' },
      },
    },
    interactivity: { events: { onHover: { enable: false }, onClick: { enable: false } } },
  };

  const containers = [];
  mounts.forEach((el, i) => {
    const id = `tsparticles-hero-${i}`;
    el.id = id;
    tsParticles.load(id, config).then((container) => {
      if (container) containers.push(container);
      if (document.hidden) container && container.pause();
    });
  });

  // Pause the (already very light) particle animation while the tab is in
  // the background instead of letting it keep ticking unseen.
  document.addEventListener('visibilitychange', () => {
    containers.forEach((c) => (document.hidden ? c.pause() : c.play()));
  });
})();
