(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  let attempts = 0;
  const MAX_ATTEMPTS = 80;

  function convergeSurface() {
    attempts += 1;
    const intel = document.querySelector(".intel-panel");
    const primary = document.getElementById("v16AutonomyPrimary");
    const evidence = document.getElementById("v16EvidenceDeck");
    const legacyDesk = document.getElementById("paperDeskV4");
    const reply = document.getElementById("commandReply");

    if (legacyDesk) {
      legacyDesk.hidden = true;
      legacyDesk.dataset.v16Retired = "true";
    }

    if (reply && /^Paper desk refresh:/i.test(String(reply.textContent || "").trim())) {
      reply.textContent = "Canonical V16 Paper Desk active. Legacy paper-desk polling is retired in this workstation.";
    }

    if (intel && primary) {
      if (intel.firstElementChild !== primary) intel.prepend(primary);
      primary.dataset.v16Pinned = "true";
      if (evidence && primary.nextElementSibling !== evidence) primary.insertAdjacentElement("afterend", evidence);
    }

    if ((!intel || !primary) && attempts < MAX_ATTEMPTS) {
      setTimeout(convergeSurface, 125);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", convergeSurface, {once: true});
  } else {
    convergeSurface();
  }

  const observer = new MutationObserver(() => {
    const primary = document.getElementById("v16AutonomyPrimary");
    const intel = document.querySelector(".intel-panel");
    if (primary && intel && intel.firstElementChild !== primary) convergeSurface();
    const legacyDesk = document.getElementById("paperDeskV4");
    if (legacyDesk && !legacyDesk.hidden) convergeSurface();
  });

  const startObserver = () => {
    if (document.body) observer.observe(document.body, {childList: true, subtree: true});
    else setTimeout(startObserver, 50);
  };
  startObserver();

  window.addEventListener("beforeunload", () => observer.disconnect(), {once: true});
})();
