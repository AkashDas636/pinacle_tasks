from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Product, WishlistItem
from app.services.cart import add_to_cart, get_cart_summary, remove_from_cart, update_cart_quantity
from app.services.catalog import list_products, serialize_product
from app.services.order import place_order

api_bp = Blueprint("api", __name__)


@api_bp.get("/products")
def products_api():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 12))
    data = list_products(
        query=request.args.get("q", ""),
        category=request.args.get("category", ""),
        sort=request.args.get("sort", "featured"),
        page=page,
        per_page=per_page,
    )
    return jsonify(data)


@api_bp.get("/product/<int:product_id>")
def product_api(product_id: int):
    product = db.session.get(Product, product_id)
    return jsonify({"product": serialize_product(product) if product else None})


@api_bp.post("/cart/add")
@login_required
def cart_add_api():
    payload = request.get_json(silent=True) or {}
    success, message = add_to_cart(current_user.id, payload.get("product_id"), payload.get("quantity", 1))
    return jsonify({"success": success, "message": message})


@api_bp.post("/cart/update")
@login_required
def cart_update_api():
    payload = request.get_json(silent=True) or {}
    success, message = update_cart_quantity(current_user.id, payload.get("product_id"), payload.get("quantity", 1))
    return jsonify({"success": success, "message": message})


@api_bp.post("/cart/remove")
@login_required
def cart_remove_api():
    payload = request.get_json(silent=True) or {}
    success, message = remove_from_cart(current_user.id, payload.get("product_id"))
    return jsonify({"success": success, "message": message})


@api_bp.get("/cart")
@login_required
def cart_api():
    return jsonify(get_cart_summary(current_user.id, request.args.get("coupon", "")))


@api_bp.post("/wishlist/toggle")
@login_required
def wishlist_toggle_api():
    payload = request.get_json(silent=True) or {}
    product_id = int(payload.get("product_id", 0))
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    from app.extensions import db

    if item:
        db.session.delete(item)
        message = "Removed from wishlist."
    else:
        if db.session.get(Product, product_id) is None:
            return jsonify({"success": False, "message": "Product not found."})
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        message = "Added to wishlist."
    db.session.commit()
    return jsonify({"success": True, "message": message})


@api_bp.post("/checkout")
@login_required
def checkout_api():
    payload = request.get_json(silent=True) or {}
    success, message, order = place_order(
        user_id=current_user.id,
        address_id=int(payload.get("address_id", 0)),
        coupon_code=payload.get("coupon_code", ""),
    )
    return jsonify(
        {
            "success": success,
            "message": message,
            "order_code": order.order_code if order else "",
        }
    )
