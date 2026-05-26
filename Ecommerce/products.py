# ============================================================
#  products.py  –  Product catalog & management
# ============================================================
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    id:          int
    name:        str
    category:    str
    price:       float
    stock:       int
    description: str
    rating:      float = 4.0
    image_url:   str   = ""

    def is_available(self) -> bool:
        return self.stock > 0

    def formatted_price(self) -> str:
        return f"${self.price:.2f}"


# ── Seed catalogue ───────────────────────────────────────────
PRODUCTS: list[Product] = [
    # Electronics
    Product(1,  "Wireless Headphones",     "Electronics",  79.99, 15,
            "Premium sound quality, 30-hour battery, noise cancellation.", 4.7),
    Product(2,  "Mechanical Keyboard",     "Electronics",  129.99, 8,
            "RGB backlit, tactile switches, compact TKL layout.", 4.5),
    Product(3,  "USB-C Hub 7-in-1",        "Electronics",   34.99, 25,
            "HDMI, SD card, 3× USB-A, PD charging.", 4.3),
    Product(4,  "Smart Watch Pro",         "Electronics",  199.99, 6,
            "Heart rate, GPS, AMOLED display, 7-day battery.", 4.6),
    Product(5,  "Portable Charger 20000mAh","Electronics",  49.99, 20,
            "Dual USB-A + USB-C, fast charge, LED indicator.", 4.4),

    # Books
    Product(6,  "Clean Code",              "Books",         35.00, 30,
            "Robert C. Martin's guide to writing readable code.", 4.8),
    Product(7,  "The Pragmatic Programmer","Books",         40.00, 22,
            "Classic software craftsmanship advice.", 4.7),
    Product(8,  "Python Crash Course",     "Books",         29.99, 40,
            "Hands-on beginner guide to Python.", 4.6),
    Product(9,  "Design Patterns",         "Books",         44.99, 18,
            "Gang of Four – patterns every developer should know.", 4.5),

    # Clothing
    Product(10, "Cotton Crew-Neck T-Shirt","Clothing",      19.99, 50,
            "100% organic cotton, pre-shrunk, 8 colours.", 4.2),
    Product(11, "Slim-Fit Chino Trousers", "Clothing",      44.99, 30,
            "Stretch fabric, multiple pockets, machine washable.", 4.3),
    Product(12, "Puffer Jacket",           "Clothing",      89.99, 12,
            "Water-resistant shell, recycled fill, packable.", 4.6),

    # Home & Kitchen
    Product(13, "French Press Coffee Maker","Home",         24.99, 35,
            "1L capacity, double-wall stainless, easy clean.", 4.4),
    Product(14, "Air Purifier HEPA",       "Home",         119.99, 9,
            "True HEPA + carbon filter, quiet mode, 500 sq-ft coverage.", 4.7),
    Product(15, "Bamboo Cutting Board Set","Home",          29.99, 28,
            "3-piece set, juice groove, non-slip feet.", 4.3),

    # Sports
    Product(16, "Yoga Mat Premium",        "Sports",        39.99, 20,
            "6mm thick, non-slip, carrying strap included.", 4.5),
    Product(17, "Resistance Band Set",     "Sports",        22.99, 45,
            "5 resistance levels, door anchor + handles.", 4.4),
    Product(18, "Water Bottle 1L",         "Sports",        18.99, 60,
            "BPA-free Tritan, leak-proof, time markers.", 4.6),
]


def get_all_products() -> list[Product]:
    return PRODUCTS


def get_product_by_id(pid: int) -> Optional[Product]:
    return next((p for p in PRODUCTS if p.id == pid), None)


def get_categories() -> list[str]:
    return sorted(set(p.category for p in PRODUCTS))


def search_products(query: str) -> list[Product]:
    q = query.lower()
    return [p for p in PRODUCTS
            if q in p.name.lower() or q in p.category.lower()
            or q in p.description.lower()]


def filter_by_category(category: str) -> list[Product]:
    return [p for p in PRODUCTS if p.category.lower() == category.lower()]


def reduce_stock(pid: int, qty: int) -> bool:
    """Deduct qty from product stock. Returns False if insufficient."""
    product = get_product_by_id(pid)
    if product is None or product.stock < qty:
        return False
    product.stock -= qty
    return True
