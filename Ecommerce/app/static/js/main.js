async function addToCart(productId) {
  const res = await fetch("/api/cart/add", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({product_id: productId, quantity: 1}),
  });
  const data = await res.json();
  alert(data.message);
}

async function updateCart(productId, quantity) {
  const res = await fetch("/api/cart/update", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({product_id: productId, quantity}),
  });
  const data = await res.json();
  alert(data.message);
  window.location.reload();
}

async function removeFromCart(productId) {
  const res = await fetch("/api/cart/remove", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({product_id: productId}),
  });
  const data = await res.json();
  alert(data.message);
  window.location.reload();
}

async function toggleWishlist(productId) {
  const res = await fetch("/api/wishlist/toggle", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({product_id: productId}),
  });
  const data = await res.json();
  alert(data.message);
}
