// Trade ticket helpers: show the selected hub's mark and a live notional estimate.
(function () {
  const form = document.querySelector('[data-testid="trade-form"]');
  if (!form) return;
  const marks = JSON.parse(form.dataset.marks);
  const hours = JSON.parse(form.dataset.hours);
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

  const hub = form.querySelector("#hub");
  const product = form.querySelector("#product");
  const qty = form.querySelector("#quantity_mw");
  const price = form.querySelector("#price");
  const markOut = document.querySelector('[data-testid="hub-mark"]');
  const notionalOut = document.querySelector('[data-testid="notional"]');

  function refresh() {
    markOut.textContent = usd.format(marks[hub.value]);
    const q = parseFloat(qty.value) || 0;
    const p = parseFloat(price.value) || 0;
    notionalOut.textContent = usd.format(q * hours[product.value] * p);
  }

  [hub, product, qty, price].forEach((el) => el.addEventListener("input", refresh));
  refresh();
})();
