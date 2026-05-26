# ============================================================
#  cart.py  –  Shopping cart logic
# ============================================================
from dataclasses import dataclass, field
from products import Product, get_product_by_id


@dataclass
class CartItem:
    product:  Product
    quantity: int

    @property
    def subtotal(self) -> float:
        return round(self.product.price * self.quantity, 2)


class ShoppingCart:
    TAX_RATE      = 0.08   # 8 %
    SHIPPING_FREE = 50.00  # free shipping above this subtotal
    SHIPPING_FLAT = 5.99

    def __init__(self):
        self._items: dict[int, CartItem] = {}   # product_id → CartItem
        self.coupon_code:  str   = ""
        self.discount_pct: float = 0.0           # e.g. 0.10 = 10 %

    # ── mutation ─────────────────────────────────────────────

    def add_item(self, product_id: int, qty: int = 1) -> str:
        """Add qty units. Returns status message."""
        product = get_product_by_id(product_id)
        if product is None:
            return f"Product #{product_id} not found."
        if not product.is_available():
            return f"'{product.name}' is out of stock."
        current_qty = self._items[product_id].quantity if product_id in self._items else 0
        if current_qty + qty > product.stock:
            return (f"Only {product.stock} unit(s) of '{product.name}' available "
                    f"(already {current_qty} in cart).")
        if product_id in self._items:
            self._items[product_id].quantity += qty
        else:
            self._items[product_id] = CartItem(product, qty)
        return f"✓ Added {qty}× '{product.name}' to cart."

    def remove_item(self, product_id: int) -> str:
        if product_id not in self._items:
            return "Item not in cart."
        name = self._items.pop(product_id).product.name
        return f"✓ Removed '{name}' from cart."

    def update_quantity(self, product_id: int, qty: int) -> str:
        if qty <= 0:
            return self.remove_item(product_id)
        if product_id not in self._items:
            return "Item not in cart."
        product = self._items[product_id].product
        if qty > product.stock:
            return f"Only {product.stock} unit(s) available."
        self._items[product_id].quantity = qty
        return f"✓ Updated '{product.name}' quantity to {qty}."

    def clear(self):
        self._items.clear()
        self.coupon_code  = ""
        self.discount_pct = 0.0

    def apply_coupon(self, code: str) -> str:
        coupons = {
            "SAVE10": 0.10,
            "SAVE20": 0.20,
            "TECH15": 0.15,
            "WELCOME5": 0.05,
        }
        code = code.upper().strip()
        if code in coupons:
            self.coupon_code  = code
            self.discount_pct = coupons[code]
            pct = int(self.discount_pct * 100)
            return f"✓ Coupon '{code}' applied – {pct}% off!"
        return f"✗ Coupon '{code}' is not valid."

    # ── read-only accessors ──────────────────────────────────

    def items(self) -> list[CartItem]:
        return list(self._items.values())

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def item_count(self) -> int:
        return sum(i.quantity for i in self._items.values())

    # ── price calculations ───────────────────────────────────

    def subtotal(self) -> float:
        return round(sum(i.subtotal for i in self._items.values()), 2)

    def discount_amount(self) -> float:
        return round(self.subtotal() * self.discount_pct, 2)

    def after_discount(self) -> float:
        return round(self.subtotal() - self.discount_amount(), 2)

    def shipping(self) -> float:
        return 0.0 if self.after_discount() >= self.SHIPPING_FREE else self.SHIPPING_FLAT

    def tax(self) -> float:
        return round(self.after_discount() * self.TAX_RATE, 2)

    def total(self) -> float:
        return round(self.after_discount() + self.shipping() + self.tax(), 2)

    def summary(self) -> dict:
        return {
            "subtotal":        self.subtotal(),
            "discount_pct":    self.discount_pct,
            "discount_amount": self.discount_amount(),
            "after_discount":  self.after_discount(),
            "shipping":        self.shipping(),
            "tax":             self.tax(),
            "total":           self.total(),
            "item_count":      self.item_count(),
            "coupon_code":     self.coupon_code,
        }
