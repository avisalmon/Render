/* The header menus (More, and the account menu): one open at a time, closed by a click
   elsewhere or Escape. Mouse and touch only: the piano control keys keep their screen jobs. */
(function () {
  var menus = Array.prototype.slice.call(document.querySelectorAll("details.im-menu"));
  if (!menus.length) return;

  menus.forEach(function (menu) {
    menu.addEventListener("toggle", function () {
      if (!menu.open) return;
      menus.forEach(function (other) {
        if (other !== menu && other.open) other.open = false;
      });
    });
  });

  document.addEventListener("click", function (event) {
    menus.forEach(function (menu) {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    menus.forEach(function (menu) {
      if (!menu.open) return;
      var hadFocus = menu.contains(document.activeElement);
      menu.open = false;
      var summary = menu.querySelector("summary");
      if (hadFocus && summary) summary.focus();
    });
  });
})();
