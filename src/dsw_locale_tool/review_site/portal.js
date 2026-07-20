(() => {
  "use strict";

  const config = window.dswReview;
  if (!config) {
    document.body.textContent = "Review configuration is unavailable.";
    return;
  }

  document.querySelector("#review-email").textContent = config.reviewer.email;
  document.querySelector("#review-password").textContent = config.reviewer.password;

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
