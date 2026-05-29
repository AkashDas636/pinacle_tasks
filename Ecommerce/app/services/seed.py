from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Coupon, Product, User


def seed_data():
    if Product.query.count() == 0:
        products = [
            Product(name="boAt Airdopes 311 Pro Bluetooth Earbuds", category="Electronics", price=1499, mrp=3999, rating=4.2, stock=42, image="https://images.unsplash.com/photo-1518444065439-e933c06ce9cd?w=800&q=80", description="ENx calls, 50hr playback, low latency mode."),
            Product(name="OnePlus Nord CE 4 Lite 5G", category="Mobiles", price=19999, mrp=22999, rating=4.4, stock=30, image="https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=80", description="AMOLED display, fast charging and smooth daily performance."),
            Product(name="Samsung 43-inch Crystal 4K Smart TV", category="Appliances", price=32990, mrp=44990, rating=4.5, stock=15, image="https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=800&q=80", description="Ultra HD smart TV with vibrant colors."),
            Product(name="Prestige Electric Kettle 1.5L", category="Home & Kitchen", price=999, mrp=1899, rating=4.3, stock=55, image="https://images.unsplash.com/photo-1606480012103-7ad8f3dc5cb7?w=800&q=80", description="Quick boil, auto cut-off, cool touch handle."),
            Product(name="The Psychology of Money", category="Books", price=319, mrp=499, rating=4.7, stock=120, image="https://images.unsplash.com/photo-1541963463532-d68292c34b19?w=800&q=80", description="Timeless lessons on wealth, greed and happiness."),
            Product(name="USPA Men Solid Cotton T-Shirt", category="Fashion", price=799, mrp=1599, rating=4.1, stock=90, image="https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80", description="Soft cotton fabric with regular fit."),
            Product(name="Maybelline Fit Me Compact", category="Beauty", price=299, mrp=399, rating=4.2, stock=110, image="https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=800&q=80", description="Natural finish for daily makeup look."),
            Product(name="Pampers Baby Diapers Large (74 Count)", category="Baby", price=899, mrp=1299, rating=4.5, stock=46, image="https://images.unsplash.com/photo-1587778082149-bd5b1bf5d3fa?w=800&q=80", description="Soft and absorbent diapers with leak lock."),
            Product(name="Dettol Liquid Handwash Refill 1L", category="Health", price=189, mrp=260, rating=4.6, stock=70, image="https://images.unsplash.com/photo-1583947215259-38e31be8751f?w=800&q=80", description="Trusted germ protection for the family."),
            Product(name="Aashirvaad Atta 10kg", category="Grocery", price=499, mrp=599, rating=4.6, stock=95, image="https://images.unsplash.com/photo-1586201375761-83865001e31c?w=800&q=80", description="Whole wheat flour for soft rotis every day."),
            Product(name="Nivia Football Size 5", category="Sports", price=699, mrp=1099, rating=4.2, stock=38, image="https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=800&q=80", description="Training football with durable stitching."),
            Product(name="Crompton BLDC Ceiling Fan", category="Home Improvement", price=2699, mrp=4199, rating=4.3, stock=27, image="https://images.unsplash.com/photo-1615874959474-d609969a20ed?w=800&q=80", description="Energy efficient and silent operation fan."),
        ]
        db.session.add_all(products)

    if Coupon.query.count() == 0:
        db.session.add_all(
            [
                Coupon(code="WELCOME10", discount_percent=10, min_order_amount=999, active=True, usage_limit=1000, used_count=0, expires_at=datetime.now(timezone.utc) + timedelta(days=365)),
                Coupon(code="FESTIVE15", discount_percent=15, min_order_amount=1999, active=True, usage_limit=500, used_count=0, expires_at=datetime.now(timezone.utc) + timedelta(days=120)),
            ]
        )

    if User.query.filter_by(email="admin@pystore.in").first() is None:
        admin = User(name="Admin", email="admin@pystore.in", is_admin=True)
        admin.set_password("admin123")
        db.session.add(admin)

    db.session.commit()
