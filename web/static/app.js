document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector("[data-shell-menu]");
  if (menuButton) {
    menuButton.addEventListener("click", () => {
      document.body.classList.toggle("shell-nav-open");
    });
  }

  const notificationButton = document.querySelector("[data-notification-toggle]");
  const notificationPopover = document.querySelector("[data-notification-popover]");
  if (notificationButton && notificationPopover) {
    notificationButton.addEventListener("click", () => {
      const expanded = notificationButton.getAttribute("aria-expanded") === "true";
      notificationButton.setAttribute("aria-expanded", String(!expanded));
      notificationPopover.hidden = expanded;
    });

    document.addEventListener("click", (event) => {
      if (
        !notificationPopover.hidden &&
        !notificationPopover.contains(event.target) &&
        !notificationButton.contains(event.target)
      ) {
        notificationButton.setAttribute("aria-expanded", "false");
        notificationPopover.hidden = true;
      }
    });
  }

  const search = document.querySelector("#global_search");
  if (search) {
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        search.value = "";
      }
    });
  }
});
