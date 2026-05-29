from app.models import Product, RecentlyViewed


def get_deals(limit=8):
    products = Product.query.all()
    products.sort(key=lambda p: ((p.mrp - p.price) / p.mrp) if p.mrp else 0, reverse=True)
    return products[:limit]


def get_top_rated(limit=8):
    return Product.query.order_by(Product.rating.desc()).limit(limit).all()


def get_recently_viewed(user_id: int, limit=8):
    viewed = (
        RecentlyViewed.query.filter_by(user_id=user_id)
        .order_by(RecentlyViewed.viewed_at.desc())
        .limit(limit)
        .all()
    )
    return [v.product for v in viewed]
