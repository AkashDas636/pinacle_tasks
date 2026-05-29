from app.extensions import db
from app.models import CartItem, Product
from app.services.coupon import validate_coupon


def get_or_create_cart_item(user_id: int, product_id: int):
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item is None:
        item = CartItem(user_id=user_id, product_id=product_id, quantity=0)
    return item


def add_to_cart(user_id: int, product_id: int, quantity: int):
    product = db.session.get(Product, product_id)
    if not product:
        return False, "Product not found."
    quantity = max(1, int(quantity))
    item = get_or_create_cart_item(user_id, product_id)
    if item.quantity + quantity > product.stock:
        return False, f"Only {product.stock} unit(s) available."
    item.quantity += quantity
    db.session.add(item)
    db.session.commit()
    return True, "Added to cart."


def update_cart_quantity(user_id: int, product_id: int, quantity: int):
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item is None:
        return False, "Item not in cart."
    quantity = int(quantity)
    if quantity <= 0:
        db.session.delete(item)
        db.session.commit()
        return True, "Removed from cart."
    if quantity > item.product.stock:
        return False, f"Only {item.product.stock} unit(s) available."
    item.quantity = quantity
    db.session.commit()
    return True, "Cart updated."


def remove_from_cart(user_id: int, product_id: int):
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if not item:
        return True, "Item removed."
    db.session.delete(item)
    db.session.commit()
    return True, "Item removed."


def get_cart_summary(user_id: int, coupon_code: str = ""):
    items = CartItem.query.filter_by(user_id=user_id).all()
    subtotal = sum(item.product.price * item.quantity for item in items)
    coupon, coupon_message = validate_coupon(coupon_code, subtotal)
    discount = round(subtotal * (coupon.discount_percent / 100), 2) if coupon else 0.0
    after_discount = subtotal - discount
    shipping = 0.0 if after_discount >= 999 else (79.0 if after_discount > 0 else 0.0)
    tax = round(after_discount * 0.18, 2)
    total = round(after_discount + shipping + tax, 2)
    return {
        "items": [
            {
                "id": item.id,
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "price": item.product.price,
                    "image": item.product.image,
                },
                "quantity": item.quantity,
                "subtotal": round(item.product.price * item.quantity, 2),
            }
            for item in items
        ],
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "shipping": shipping,
        "tax": tax,
        "total": total,
        "coupon_code": coupon.code if coupon else "",
        "coupon_message": "" if coupon else coupon_message,
    }
