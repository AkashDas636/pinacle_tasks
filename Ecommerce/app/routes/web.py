from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Address, Order, Product, Review, WishlistItem
from app.services.catalog import list_products, product_reviews, serialize_product, track_view
from app.services.cart import get_cart_summary
from app.services.recommendation import get_deals, get_recently_viewed, get_top_rated

web_bp = Blueprint("web", __name__)


@web_bp.route("/")
def home():
    page = int(request.args.get("page", 1))
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    sort = request.args.get("sort", "featured")
    products = list_products(query=query, category=category, sort=sort, page=page, per_page=12)
    categories = [row[0] for row in Product.query.with_entities(Product.category).distinct().all()]
    deals = [serialize_product(p) for p in get_deals()]
    top_rated = [serialize_product(p) for p in get_top_rated()]
    return render_template(
        "index.html",
        products=products,
        categories=sorted(categories),
        query=query,
        category=category,
        sort=sort,
        deals=deals,
        top_rated=top_rated,
    )


@web_bp.route("/product/<int:product_id>")
def product_page(product_id: int):
    product = Product.query.get_or_404(product_id)
    if current_user.is_authenticated:
        track_view(current_user.id, product.id)
    reviews = product_reviews(product.id)
    related = (
        Product.query.filter(Product.category == product.category, Product.id != product.id)
        .limit(8)
        .all()
    )
    return render_template(
        "product.html",
        product=serialize_product(product),
        reviews=reviews,
        related=[serialize_product(p) for p in related],
    )


@web_bp.route("/cart")
@login_required
def cart_page():
    summary = get_cart_summary(current_user.id, request.args.get("coupon", ""))
    return render_template("cart.html", summary=summary)


@web_bp.route("/wishlist")
@login_required
def wishlist_page():
    items = WishlistItem.query.filter_by(user_id=current_user.id).all()
    return render_template("wishlist.html", items=[serialize_product(i.product) for i in items])


@web_bp.route("/orders")
@login_required
def orders_page():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)


@web_bp.route("/checkout")
@login_required
def checkout_page():
    summary = get_cart_summary(current_user.id, request.args.get("coupon", ""))
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    if not summary["items"]:
        return redirect(url_for("web.cart_page"))
    return render_template("checkout.html", summary=summary, addresses=addresses)


@web_bp.route("/addresses", methods=["GET", "POST"])
@login_required
def addresses_page():
    if request.method == "POST":
        is_default = bool(request.form.get("is_default"))
        if is_default:
            Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
        from app.extensions import db

        db.session.add(
            Address(
                user_id=current_user.id,
                full_name=request.form.get("full_name", "").strip(),
                phone=request.form.get("phone", "").strip(),
                line1=request.form.get("line1", "").strip(),
                city=request.form.get("city", "").strip(),
                state=request.form.get("state", "").strip(),
                pin=request.form.get("pin", "").strip(),
                is_default=is_default,
            )
        )
        db.session.commit()
        return redirect(url_for("web.addresses_page"))
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    return render_template("addresses.html", addresses=addresses)


@web_bp.route("/review/<int:product_id>", methods=["POST"])
@login_required
def add_review(product_id: int):
    from app.extensions import db

    db.session.add(
        Review(
            user_id=current_user.id,
            product_id=product_id,
            rating=float(request.form.get("rating", 4)),
            title=request.form.get("title", "Review"),
            comment=request.form.get("comment", ""),
        )
    )
    db.session.commit()
    return redirect(url_for("web.product_page", product_id=product_id))
