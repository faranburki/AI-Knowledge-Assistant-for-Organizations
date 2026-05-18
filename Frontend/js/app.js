/* ═══ App.js — Module loader ═══
   This file is kept minimal — it dynamically loads all JS modules
   in the correct dependency order. Each module is self-contained.
*/
(function() {
  const scripts = ['js/core.js', 'js/chat.js', 'js/documents.js', 'js/pages.js'];
  let loaded = 0;
  scripts.forEach(src => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = () => { loaded++; };
    s.onerror = () => console.error('Failed to load:', src);
    document.body.appendChild(s);
  });
})();
