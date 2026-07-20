(() => {
  "use strict";

  const config = window.dswReview;
  if (!config) {
    document.body.textContent = "Review configuration is unavailable.";
    return;
  }

  document.querySelector("#review-email").textContent = config.reviewer.email;
  document.querySelector("#review-password").textContent = config.reviewer.password;

  const metadata = config.metadata;
  document.querySelector("#review-dsw-version").textContent = metadata.dswVersion;
  document.querySelector("#review-translation-ref").textContent = metadata.translationRef;
  document.querySelector("#review-revision").textContent = metadata.revision.slice(0, 12);
  document.querySelector("#review-lifetime").textContent =
    `${metadata.idleTimeoutMinutes} min idle · ${metadata.hardTimeoutMinutes} min maximum`;
  document.querySelector("#review-hard-expiry").textContent =
    new Date(metadata.hardExpiresAt).toLocaleString();
  if (metadata.pullRequestUrl) {
    const pullRequest = document.querySelector("#review-pull-request");
    pullRequest.href = metadata.pullRequestUrl;
    pullRequest.hidden = false;
  }

  const groups = new Map();
  for (const page of config.pages) {
    if (!groups.has(page.group)) groups.set(page.group, []);
    groups.get(page.group).push(page);
  }

  const root = document.querySelector("#review-groups");
  for (const [name, pages] of groups) {
    const section = document.createElement("section");
    section.className = "review-card review-page-group";

    const heading = document.createElement("h3");
    heading.textContent = name;
    section.append(heading);

    const links = document.createElement("ul");
    for (const page of pages) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = page.path;
      link.textContent = page.title;
      item.append(link);
      links.append(item);
    }
    section.append(links);
    root.append(section);
  }
})();
