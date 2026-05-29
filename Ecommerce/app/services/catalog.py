from sqlalchemy import desc

from app.models import Product, RecentlyViewed, Review


def serialize_product(p: Product) -> dict:
    discount = int(round((p.mrp - p.price) / p.mrp * 100)) if p.mrp else 0
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "price": p.price,
        "mrp": p.mrp,
        "discount": discount,
        "rating": p.rating,
        "stock": p.stock,
        "image": p.image,
        "description": p.description,
    }


def list_products(query="", category="", sort="featured", page=1, per_page=12):
    q = Product.query
    if category:
        q = q.filter(Product.category == category)
    if query:
        search = f"%{query.strip()}%"
        q = q.filter((Product.name.ilike(search)) | (Product.description.ilike(search)))
    if sort == "price_asc":
        q = q.order_by(Product.price.asc())
    elif sort == "price_desc":
        q = q.order_by(Product.price.desc())
    elif sort == "rating_desc":
        q = q.order_by(Product.rating.desc())
    else:
        q = q.order_by(desc(Product.created_at))
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [serialize_product(p) for p in paginated.items],
        "page": paginated.page,
        "pages": paginated.pages,
        "total": paginated.total,
    }


def track_view(user_id: int, product_id: int):
    if not user_id:
        return
    RecentlyViewed.query.filter_by(user_id=user_id, product_id=product_id).delete()
    rv = RecentlyViewed(user_id=user_id, product_id=product_id)
    from app.extensions import db

    db.session.add(rv)
    db.session.commit()


def product_reviews(product_id: int):
    return Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
