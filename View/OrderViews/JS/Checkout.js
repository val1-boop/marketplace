// Confirmación del pago (CSP script-src 'self': sin JavaScript en línea).
// Si el navegador no soporta <dialog>, el formulario se envía normal y el servidor valida igual.
(function () {
  var form = document.getElementById("checkout-form");
  var dialog = document.getElementById("pay-dialog");
  if (!form || !dialog || typeof dialog.showModal !== "function") {
    return;
  }
  var confirmed = false;
  form.addEventListener("submit", function (event) {
    if (confirmed) {
      return;
    }
    event.preventDefault();
    dialog.showModal();
  });
  document.getElementById("pay-cancel").addEventListener("click", function () {
    dialog.close();
  });
  document.getElementById("pay-confirm").addEventListener("click", function () {
    confirmed = true;
    document.getElementById("pay-confirm").disabled = true; // evita pagar dos veces con doble clic
    dialog.close();
    form.submit();
  });
})();
