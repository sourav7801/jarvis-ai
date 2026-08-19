(() => {
  const expiredMarkers = [
    "token is expired",
    "token expired",
    "could not authenticate the user",
    "invalid token",
    "code: -99",
    '"code":-99',
  ];

  function text(id) {
    const node = document.getElementById(id);
    return node ? String(node.textContent || "") : "";
  }

  function looksExpired() {
    const combined = `${text("providerMessage")} ${text("providerState")} ${text("providerButton")}`.toLowerCase();
    return expiredMarkers.some(marker => combined.includes(marker));
  }

  function repairProviderState() {
    if (!looksExpired()) return;

    const button = document.getElementById("providerButton");
    const state = document.getElementById("providerState");
    const message = document.getElementById("providerMessage");
    const login = document.getElementById("loginButton");

    if (button) {
      button.textContent = "FYERS · SESSION EXPIRED";
      button.className = "status-pill error";
      button.title = "Click to re-authenticate FYERS read-only market data";
    }
    if (state) state.textContent = "SESSION EXPIRED";
    if (message) {
      message.textContent = "FYERS token expired. Re-authenticate locally to restore Indian-market candles and live snapshots.";
    }
    if (login) {
      login.textContent = "RE-AUTHENTICATE FYERS";
      login.classList.add("attention");
    }
  }

  const observer = new MutationObserver(repairProviderState);
  ["providerMessage", "providerState", "providerButton"].forEach(id => {
    const node = document.getElementById(id);
    if (node) observer.observe(node, { childList: true, characterData: true, subtree: true });
  });

  const providerButton = document.getElementById("providerButton");
  if (providerButton) {
    providerButton.addEventListener("click", () => {
      if (looksExpired()) document.getElementById("loginButton")?.click();
    });
  }

  repairProviderState();
  window.setInterval(repairProviderState, 1200);
})();