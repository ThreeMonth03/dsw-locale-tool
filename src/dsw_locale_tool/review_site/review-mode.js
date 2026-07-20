(() => {
  "use strict";

  const config = window.dswReview;
  if (!config) return;
  const allowed = new Set(config.allowedPaths);
  const isReviewPath = (url) => {
    const destination = new URL(url, window.location.href);
    return destination.origin === window.location.origin && allowed.has(destination.pathname);
  };
  let returningToPortal = false;
  const returnToPortal = () => {
    if (returningToPortal) return;
    returningToPortal = true;
    window.location.replace("/");
  };

  for (const method of ["pushState", "replaceState"]) {
    const original = history[method].bind(history);
    history[method] = (state, unused, url) => {
      if (url !== undefined && !isReviewPath(url)) {
        returnToPortal();
        return;
      }
      original(state, unused, url);
    };
  }

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest("a[href]");
      if (link && !isReviewPath(link.href)) {
        event.preventDefault();
        returnToPortal();
      }
    },
    true,
  );

  const updatePage = () => {
    if (!document.querySelector("#dsw-review-banner")) {
      const banner = document.createElement("aside");
      banner.id = "dsw-review-banner";
      banner.setAttribute("role", "status");
      const link = document.createElement("a");
      link.href = "/";
      link.textContent = "Translation review";
      const details = document.createElement("span");
      const revision = config.metadata.revision.slice(0, 12);
      details.textContent =
        `DSW ${config.metadata.dswVersion} · ${config.metadata.translationRef} · ` +
        `${revision} · changes are blocked`;
      banner.append(link, details);
      document.body.prepend(banner);
    }
    for (const link of document.querySelectorAll("a[href]")) {
      if (!isReviewPath(link.href)) {
        link.setAttribute("aria-disabled", "true");
        link.setAttribute("tabindex", "-1");
        link.classList.add("dsw-review-unavailable");
      }
    }
  };

  new MutationObserver(updatePage).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updatePage, { once: true });
  } else {
    updatePage();
  }
})();
