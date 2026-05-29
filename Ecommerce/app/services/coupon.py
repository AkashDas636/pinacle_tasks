from datetime import datetime, timezone

from app.models import Coupon


def validate_coupon(code: str, subtotal: float):
    if not code:
        return None, "No coupon selected."
    coupon = Coupon.query.filter_by(code=code.upper().strip()).first()
    if coupon is None:
        return None, "Invalid coupon."
    if not coupon.active:
        return None, "Coupon is inactive."
    if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
        return None, "Coupon expired."
    if coupon.used_count >= coupon.usage_limit:
        return None, "Coupon usage limit reached."
    if subtotal < coupon.min_order_amount:
        return None, f"Minimum order amount for {coupon.code} is ₹{coupon.min_order_amount:.0f}."
    return coupon, ""
