# ============================================================
#  products.py  –  Product catalog & management (Indian Market)
# ============================================================
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    id:          int
    name:        str
    category:    str
    price:       float        # Price in Indian Rupees (₹)
    stock:       int
    description: str
    rating:      float = 4.0
    image_url:   str   = ""

    def is_available(self) -> bool:
        return self.stock > 0

    def formatted_price(self) -> str:
        return f"₹{self.price:,.2f}"


# ── Indian Market Product Catalogue ──────────────────────────
PRODUCTS: list[Product] = [
    # ── Electronics ──────────────────────────────────────────
    Product(1, "Sony WH-1000XM5 Headphones", "Electronics", 24990.00, 12,
            "Industry-leading noise cancellation, 30hr battery, Hi-Res Audio, multipoint connection.",
            4.8, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80"),

    Product(2, "Keychron K2 Mechanical Keyboard", "Electronics", 7499.00, 18,
            "75% wireless mechanical keyboard, Gateron switches, RGB backlit, Mac & Windows compatible.",
            4.6, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&q=80"),

    Product(3, "Anker PowerPort USB-C Hub 7-in-1", "Electronics", 3499.00, 30,
            "4K HDMI, 100W PD pass-through, SD/microSD slots, 2× USB-A 3.0 ports.",
            4.4, "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=600&q=80"),

    Product(4, "Samsung Galaxy Watch 6 Classic", "Electronics", 29999.00, 8,
            "46mm Super AMOLED, rotating bezel, BIA body composition, Wear OS, 40hr battery.",
            4.7, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80"),

    Product(5, "Mi Power Bank 3i 20000mAh", "Electronics", 1499.00, 45,
            "20000mAh, 18W fast charging, triple output (USB-C + 2× USB-A), power indicator.",
            4.5, "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=600&q=80"),

    # ── Books ────────────────────────────────────────────────
    Product(6, "Clean Code - Robert C. Martin", "Books", 599.00, 50,
            "The definitive guide to writing clean, readable, and maintainable code. Paperback edition.",
            4.8, "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&q=80"),

    Product(7, "The Pragmatic Programmer", "Books", 749.00, 35,
            "20th Anniversary Edition. Classic software craftsmanship advice by Andrew Hunt & David Thomas.",
            4.7, "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600&q=80"),

    Product(8, "Python Crash Course (3rd Ed.)", "Books", 499.00, 60,
            "Best-selling hands-on Python guide. Project-based approach covering games, data viz, and web apps.",
            4.6, "https://images.unsplash.com/photo-1589998059171-988d887df646?w=600&q=80"),

    Product(9, "Atomic Habits - James Clear", "Books", 399.00, 80,
            "An easy & proven way to build good habits and break bad ones. #1 NYT Bestseller.",
            4.9, "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600&q=80"),

    # ── Clothing ─────────────────────────────────────────────
    Product(10, "Allen Solly Cotton Crew-Neck T-Shirt", "Clothing", 799.00, 60,
            "100% BCI cotton, pre-shrunk, regular fit. Available in 8 colours. Made in India.",
            4.3, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80"),

    Product(11, "Levi's 511 Slim Fit Jeans", "Clothing", 2999.00, 25,
            "Slim from hip to ankle, stretch denim for all-day comfort, classic 5-pocket styling.",
            4.5, "https://images.unsplash.com/photo-1542272454315-4c01d7abdf4a?w=600&q=80"),

    Product(12, "Woodland Leather Jacket", "Clothing", 5999.00, 10,
            "Genuine leather, zip closure, quilted lining, two side pockets. Premium winter wear.",
            4.6, "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&q=80"),

    # ── Home & Kitchen ───────────────────────────────────────
    Product(13, "InstaCuppa French Press 1L", "Home", 1299.00, 40,
            "Borosilicate glass carafe, 4-level filtration, stainless steel plunger, BPA-free.",
            4.4, "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&q=80"),

    Product(14, "Dyson Air Purifier TP07", "Home", 44990.00, 5,
            "HEPA H13 + activated carbon filter, real-time air quality display, Wi-Fi enabled, 600 sq ft.",
            4.8, "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=600&q=80"),

    Product(15, "Prestige Marble Cutting Board Set", "Home", 1199.00, 35,
            "3-piece bamboo set with juice groove, non-slip silicone feet, knife-friendly surface.",
            4.3, "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80"),

    # ── Sports & Fitness ─────────────────────────────────────
    Product(16, "Boldfit Yoga Mat Premium 6mm", "Sports", 899.00, 30,
            "Anti-skid, eco-friendly TPE material, alignment lines, carrying strap included.",
            4.5, "https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=600&q=80"),

    Product(17, "Boldfit Resistance Band Set (5 pcs)", "Sports", 549.00, 55,
            "5 resistance levels (2kg-18kg), latex-free TPE, door anchor + handles included.",
            4.4, "https://images.unsplash.com/photo-1598289431512-b97b0917affc?w=600&q=80"),

    Product(18, "Borosil Hydra Trek Water Bottle 1L", "Sports", 699.00, 70,
            "Vacuum-insulated stainless steel, keeps cold 24hr/hot 12hr, BPA-free, leak-proof.",
            4.6, "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&q=80"),

    # ── Mobile & Accessories ──────────────────────────────────
    Product(19, "Redmi Note 12 Pro", "Mobiles", 16999.00, 22,
            "6.67\" AMOLED display, 108MP camera, 67W fast charge, 8GB RAM, 256GB storage.",
            4.4, "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&q=80"),

    Product(20, "boAt Rockerz 450 Bluetooth Headphones", "Mobiles", 2499.00, 40,
            "40mm drivers, 30hr battery, fast charging, dual pairing with devices.",
            4.2, "https://images.unsplash.com/photo-1518779578993-ec3579fee39f?w=600&q=80"),

    Product(21, "Samsung 32-inch Smart LED TV", "Appliances", 25999.00, 14,
            "Full HD, Tizen OS, multiple voice assistants, Dolby Audio, 3 HDMI ports.",
            4.5, "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&q=80"),

    Product(22, "Philips HL7707/00 Mixer Grinder", "Appliances", 4499.00, 18,
            "750W motor, 3 jars, ripcord technology, stainless steel blades.",
            4.3, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80"),

    Product(23, "Lakme 9 to 5 Primer + Matte Lipstick Combo", "Beauty", 899.00, 25,
            "Soft matte lipsticks and smooth primer for all-day wear and hydration.",
            4.1, "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?w=600&q=80"),

    Product(24, "Ponds Bright Beauty Face Wash", "Beauty", 129.00, 60,
            "Gentle cleanser with Vitamin B3 for brighter, clearer skin.",
            4.3, "https://images.unsplash.com/photo-1542838132-92c53300491e?w=600&q=80"),

    Product(25, "Lego City Police Station Building Kit", "Toys", 3499.00, 16,
            "Creative building set with mini-figures and play-area accessories.",
            4.7, "https://images.unsplash.com/photo-1523413651479-597eb2da0ad6?w=600&q=80"),

    Product(26, "Toys Baby Phone Developmental Toy", "Toys", 499.00, 80,
            "Interactive baby toy with lights, music, and easy grip design.",
            4.2, "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?w=600&q=80"),

    Product(27, "Organic Turmeric Powder 250g", "Grocery", 199.00, 120,
            "Premium Indian turmeric powder for cooking and healthy recipes.",
            4.6, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=600&q=80"),

    Product(28, "Daawat Traditional Basmati Rice 5kg", "Grocery", 329.00, 40,
            "Aromatic long-grain basmati rice for everyday meals and special occasions.",
            4.5, "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=600&q=80"),
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

# ── Sample Review Data ────────────────────────────────────────
REVIEWS_BY_ID: dict[int, list[dict[str, str | float]]] = {
    1: [
        {"author": "Rohit S.", "rating": 5.0, "title": "Excellent noise cancellation", "comment": "The sound clarity is amazing and battery lasts all day."},
        {"author": "Neha K.", "rating": 4.5, "title": "Very comfortable", "comment": "Great fit and premium build quality. Worth the price."}
    ],
    6: [
        {"author": "Amit P.", "rating": 5.0, "title": "Must-read for developers", "comment": "Practical advice and easy to follow examples."},
        {"author": "Meera R.", "rating": 4.5, "title": "Highly recommended", "comment": "Improved my coding style significantly."}
    ],
    19: [
        {"author": "Priya M.", "rating": 4.0, "title": "Great value for money", "comment": "Superb display and fast performance at this price."},
        {"author": "Sandeep J.", "rating": 4.2, "title": "Battery life is good", "comment": "Lasts through a full day with heavy use."}
    ],
    21: [
        {"author": "Gita S.", "rating": 4.5, "title": "Smart TV with crisp picture", "comment": "The smart features are easy to use and picture quality is sharp."}
    ]
}


def get_reviews(product_id: int) -> list[dict[str, str | float]]:
    return REVIEWS_BY_ID.get(product_id, [])
