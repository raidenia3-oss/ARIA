(function () {
  'use strict';

  function optimizePrompt(raw) {
    const trimmed = (raw || '').trim();
    if (!trimmed) return '';

    const templates = [
      `Actúa como experto senior en el tema: "${trimmed}".\nProporciona una respuesta estructurada en 3 partes: (1) resumen claro, (2) pasos accionables, (3) precauciones importantes.`,
      `Eres un consultor especializado en "${trimmed}".\nNecesito un análisis breve con: contexto, 2 alternativas de solución y una recomendación final.`,
      `Como profesor experto en "${trimmed}", explica el concepto como si yo fuera un principiante. Incluye un ejemplo práctico y una métrica de validación.`,
    ];

    return templates[Math.floor(Math.random() * templates.length)];
  }

  function init() {
    const input = document.getElementById('prompt-input');
    const btn = document.getElementById('prompt-generate-btn');
    const output = document.getElementById('prompt-output');
    const pre = output ? output.querySelector('pre') : null;

    if (!input || !btn || !output || !pre) return;

    btn.addEventListener('click', function () {
      const raw = input.value;
      if (!raw) {
        pre.textContent = 'Escribe una idea primero para crear tu Prompt Maestro.';
        output.classList.remove('hidden');
        return;
      }

      btn.disabled = true;
      pre.textContent = 'Optimizando tu prompt...';
      output.classList.remove('hidden');

      setTimeout(function () {
        pre.textContent = optimizePrompt(raw);
        btn.disabled = false;
        try {
          if (typeof window.__adsterraTrigger === 'function') window.__adsterraTrigger('prompt_generated');
        } catch (e) {}
      }, 3000);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
