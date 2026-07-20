(() => {
  "use strict";

  const minimumInterval = 60_000;
  let lastHeartbeat = 0;

  const sendHeartbeat = () => {
    const now = Date.now();
    if (document.hidden || now - lastHeartbeat < minimumInterval) return;
    lastHeartbeat = now;
    fetch("/review/heartbeat", {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      keepalive: true,
    }).catch(() => {});
  };

  for (const eventName of ["click", "keydown", "pointermove", "scroll", "touchstart"]) {
    window.addEventListener(eventName, sendHeartbeat, { passive: true });
  }
  document.addEventListener("visibilitychange", sendHeartbeat);
  sendHeartbeat();
})();
