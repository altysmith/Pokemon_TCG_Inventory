(() => {
  const storageKey = 'pokemon-inventory-theme';
  const systemPreference = window.matchMedia('(prefers-color-scheme: dark)');

  function savedTheme() {
    try {
      const value = window.localStorage.getItem(storageKey);
      return value === 'light' || value === 'dark' ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function effectiveTheme() {
    const pageDefault = document.documentElement.dataset.theme;
    return savedTheme() || (pageDefault === 'light' || pageDefault === 'dark' ? pageDefault : null) || (systemPreference.matches ? 'dark' : 'light');
  }

  function updateButton(theme) {
    const button = document.querySelector('#theme_toggle');
    if (!button) return;
    const dark = theme === 'dark';
    button.textContent = dark ? 'Light mode' : 'Dark mode';
    button.setAttribute('aria-pressed', String(dark));
    button.setAttribute('aria-label', dark ? 'Use light mode' : 'Use dark mode');
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    updateButton(theme);
  }

  applyTheme(effectiveTheme());

  window.addEventListener('DOMContentLoaded', () => {
    applyTheme(effectiveTheme());
    document.querySelector('#theme_toggle')?.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try {
        window.localStorage.setItem(storageKey, next);
      } catch (_error) {
        // The selected theme still applies for this page when storage is unavailable.
      }
      applyTheme(next);
    });
  });

  systemPreference.addEventListener?.('change', () => {
    if (!savedTheme()) applyTheme(effectiveTheme());
  });
})();
