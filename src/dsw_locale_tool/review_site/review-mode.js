(() => {
  "use strict";

  const config = window.dswReview;
  if (!config) return;
  const allowed = new Set(config.allowedPaths);
  const isReviewPath = (url) => {
    const destination = new URL(url, window.location.href);
    return destination.origin === window.location.origin && allowed.has(destination.pathname);
  };
  const returnToPortal = () => window.location.assign("/");

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
      banner.innerHTML =
        '<a href="/">Translation review</a><span>Changes are blocked and not saved</span>';
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
