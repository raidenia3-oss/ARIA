(function() {
  const KEY = 'aura-bg-custom';
  const KEY_MODE = 'aura-bg-custom-mode';
  const KEY_ANIM = 'aura-bg-custom-anim';
  const el = document.createElement('div');
  el.id = 'ambxst-bg';
  el.className = 'ambxst-bg-custom';
  document.body.prepend(el);

  const overlay = document.createElement('div');
  overlay.id = 'ambxst-bg-overlay';
  overlay.className = 'ambxst-bg-overlay';
  document.body.prepend(overlay);

  function apply() {
    const v = localStorage.getItem(KEY) || '';
    const mode = localStorage.getItem(KEY_MODE) || 'cover';
    const anim = localStorage.getItem(KEY_ANIM) || 'none';
    if (v) {
      let bg = v;
      if (!(v.startsWith('url(') || v.startsWith('linear-gradient') || v.startsWith('radial-gradient'))) {
        bg = url("");
      }
      el.style.backgroundImage = bg;
      el.style.backgroundSize = mode === 'contain' ? 'contain' : 'cover';
      el.style.backgroundPosition = 'center';
      el.classList.remove('ambxst-anim-fade','ambxst-anim-kenburns','ambxst-anim-zoom');
      if (anim === 'fade') el.classList.add('ambxst-anim-fade');
      else if (anim === 'kenburns') el.classList.add('ambxst-anim-kenburns');
      else if (anim === 'zoom') el.classList.add('ambxst-anim-zoom');
      el.style.display = 'block';
      overlay.style.display = 'block';
    } else {
      el.style.display = 'none';
      overlay.style.display = 'none';
      el.classList.remove('ambxst-anim-fade','ambxst-anim-kenburns','ambxst-anim-zoom');
    }
  }
  apply();
  window.addEventListener('storage', apply);
  window.AURA_BG_CUSTOM_SET = function(v, opts) {
    opts = opts || {};
    if (v) localStorage.setItem(KEY, v); else localStorage.removeItem(KEY);
    if (opts.mode) localStorage.setItem(KEY_MODE, opts.mode);
    if (opts.anim) localStorage.setItem(KEY_ANIM, opts.anim);
    apply();
  };
  window.AURA_BG_CUSTOM_CLEAR = function() { localStorage.removeItem(KEY); localStorage.removeItem(KEY_MODE); localStorage.removeItem(KEY_ANIM); apply(); };
  window.AURA_BG_CUSTOM_LIST = function() { return {bg: localStorage.getItem(KEY), mode: localStorage.getItem(KEY_MODE), anim: localStorage.getItem(KEY_ANIM)}; };
})();
