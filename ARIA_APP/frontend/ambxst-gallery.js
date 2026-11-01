(function(){
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.style.display = 'none';
  document.body.appendChild(input);
  window.AURA_BG_PICK_IMAGE = function() {
    input.onchange = function(e) {
      const f = e.target.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = function(ev) {
        const dataUrl = ev.target.result;
        if (window.AURA_BG_CUSTOM_SET) window.AURA_BG_CUSTOM_SET(dataUrl, {mode:'cover', anim:'kenburns'});
      };
      reader.readAsDataURL(f);
    };
    input.click();
  };
  window.AURA_BG_ENHANCE = function(opts){
    opts = opts||{};
    const cur = localStorage.getItem('aura-bg-custom')||'';
    if (!cur) return {status:'no_bg'};
    // simulate enhancement: keep same, enable subtle anim
    if (window.AURA_BG_CUSTOM_SET) window.AURA_BG_CUSTOM_SET(cur, {mode: opts.mode||'cover', anim: opts.anim||'kenburns'});
    return {status:'enhanced', anim: opts.anim||'kenburns'};
  };
})();
