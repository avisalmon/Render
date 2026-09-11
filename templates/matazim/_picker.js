{% comment %}
  The person picker, shared by the admin screen and the leaders screen.
  Kept as one file rather than two copies: the first page to drift would be the
  one nobody noticed.
{% endcomment %}
(function () {
  const box = document.getElementById("mzUserSearch");
  const list = document.getElementById("mzResults");
  const chosen = document.getElementById("mzChosen");
  const hidden = document.getElementById("mzChosenEmail");
  const submit = document.getElementById("mzGrantBtn");
  if (!box) return;

  const URL_BASE = "{% url 'matazim:staff_user_search' %}";
  let timer = null;
  let controller = null;

  function clearChoice() {
    hidden.value = "";
    chosen.hidden = true;
    submit.disabled = true;
  }

  function choose(person) {
    hidden.value = person.email;
    box.value = person.name ? person.name + " · " + person.email : person.email;
    chosen.textContent = person.is_admin
      ? person.email + " כבר מנהל/ת. אפשר להוסיף שוב, זה לא ישנה כלום."
      : "נבחר: " + person.email;
    chosen.hidden = false;
    submit.disabled = false;
    list.hidden = true;
    box.setAttribute("aria-expanded", "false");
  }

  function render(results) {
    list.innerHTML = "";
    if (!results.length) {
      list.hidden = true;
      box.setAttribute("aria-expanded", "false");
      return;
    }
    for (const person of results) {
      const item = document.createElement("li");
      item.setAttribute("role", "option");
      item.tabIndex = 0;
      item.innerHTML =
        '<span class="mz-picker-name"></span><span class="mz-picker-email"></span>';
      item.querySelector(".mz-picker-name").textContent = person.name || person.email;
      item.querySelector(".mz-picker-email").textContent =
        person.is_admin ? person.email + " · כבר מנהל/ת" : person.email;
      item.addEventListener("click", function () { choose(person); });
      item.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(person); }
      });
      list.appendChild(item);
    }
    list.hidden = false;
    box.setAttribute("aria-expanded", "true");
  }

  box.addEventListener("input", function () {
    clearChoice();
    clearTimeout(timer);
    const q = box.value.trim();
    // Matches the server: under two characters there is nothing to look for,
    // and it keeps a keystroke from becoming a request.
    if (q.length < 2) { render([]); return; }
    timer = setTimeout(async function () {
      if (controller) controller.abort();
      controller = new AbortController();
      try {
        const res = await fetch(URL_BASE + "?q=" + encodeURIComponent(q),
                                { signal: controller.signal });
        const data = await res.json();
        render(data.results || []);
      } catch (e) { /* aborted or offline: leave the last list alone */ }
    }, 200);
  });

  document.addEventListener("click", function (e) {
    if (!list.contains(e.target) && e.target !== box) { list.hidden = true; }
  });
})();
