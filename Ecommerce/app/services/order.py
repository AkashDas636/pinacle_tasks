import uuid

from app.extensions import db
from app.models import Address, CartItem, Order, OrderItem
from app.services.cart import get_cart_summary
from app.services.coupon import validate_coupon


def place_order(user_id: int, address_id: int, coupon_code: str = ""):
    address = Address.query.filter_by(id=address_id, user_id=user_id).first()
    if not address:
        return False, "Invalid address.", None

    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return False, "Cart is empty.", None

    for item in cart_items:
        if item.quantity > item.product.stock:
            return False, f"{item.product.name} is out of stock.", None

    summary = get_cart_summary(user_id, coupon_code=coupon_code)
    coupon, _ = validate_coupon(coupon_code, summary["subtotal"])

    order = Order(
        order_code=f"ODR-{uuid.uuid4().hex[:10].upper()}",
        user_id=user_id,
        address_id=address.id,
        subtotal=summary["subtotal"],
        discount=summary["discount"],
        shipping=summary["shipping"],
        tax=summary["tax"],
        total=summary["total"],
        status="Placed",
    )
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.product.price,
            )
        )
        item.product.stock -= item.quantity
        db.session.delete(item)

    if coupon:
        coupon.used_count += 1

    db.session.commit()
    return True, "Order placed.", order
