// Único JS de la app (CSP script-src 'self'): sin innerHTML ni eval.
document.documentElement.classList.add("js");

// Confirmación antes de enviar formularios destructivos (data-confirm="...").
document.addEventListener("submit", function (event) {
  var form = event.target;
  if (form instanceof HTMLFormElement && form.dataset.confirm) {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  }
});

// Los selectores con data-autosubmit aplican el cambio al momento (p. ej. "Ordenar por").
document.addEventListener("change", function (event) {
  var el = event.target;
  if (el instanceof HTMLSelectElement && el.dataset.autosubmit !== undefined && el.form) {
    el.form.submit();
  }
});

// Carrusel "Te recomendamos": las flechas desplazan la fila (sin JS se desplaza con el dedo o la rueda).
document.addEventListener("click", function (event) {
  var button = event.target instanceof Element ? event.target.closest("[data-rail]") : null;
  if (!button) {
    return;
  }
  var rail = document.getElementById(button.dataset.rail);
  if (rail) {
    var step = rail.clientWidth * 0.8 * (button.dataset.dir === "-1" ? -1 : 1);
    rail.scrollBy({ left: step, behavior: "smooth" });
  }
});

// Cerrar menús desplegables (<details>) al hacer clic fuera de ellos.
document.addEventListener("click", function (event) {
  document.querySelectorAll("details.usermenu[open], details.catmenu[open]").forEach(function (menu) {
    if (!(event.target instanceof Node) || !menu.contains(event.target)) {
      menu.removeAttribute("open");
    }
  });
});
