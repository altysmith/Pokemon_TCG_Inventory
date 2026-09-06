(() => {
  const storageKey = 'pokemon-card-collection.desktop-session';
  const parameters = new URLSearchParams(window.location.search);
  const suppliedToken = parameters.get('desktop_session') || '';
  const validToken = /^[0-9a-f]{32}$/i;

  if (validToken.test(suppliedToken)) {
    window.sessionStorage.setItem(storageKey, suppliedToken.toLowerCase());
    parameters.delete('desktop_session');
    const query = parameters.toString();
    const cleanUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
    window.history.replaceState(null, '', cleanUrl);
  }

  const token = window.sessionStorage.getItem(storageKey) || '';
  if (!validToken.test(token) || typeof window.EventSource !== 'function') {
    return;
  }

  const pageToken = window.crypto.randomUUID().replaceAll('-', '');
  let sessionStream = null;

  const connect = () => {
    if (sessionStream && sessionStream.readyState !== EventSource.CLOSED) {
      return;
    }
    sessionStream = new EventSource(
      `/desktop-session/watch?token=${encodeURIComponent(token)}&page=${encodeURIComponent(pageToken)}`,
    );
  };

  connect();
  window.addEventListener('pageshow', connect);
  window.addEventListener('pagehide', () => {
    const body = new Blob(
      [JSON.stringify({token, page: pageToken})],
      {type: 'application/json'},
    );
    window.navigator.sendBeacon('/desktop-session/close', body);
    if (sessionStream) {
      sessionStream.close();
      sessionStream = null;
    }
  });
})();
