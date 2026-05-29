from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Order, Product, User

admin_bp = Blueprint("admin", __name__)


def admin_only():
    return current_user.is_authenticated and current_user.is_admin


@admin_bp.route("/")
@login_required
def dashboard():
    if not admin_only():
        return redirect(url_for("web.home"))
    stats = {
        "users": User.query.count(),
        "products": Product.query.count(),
        "orders": Order.query.count(),
        "revenue": round(sum(o.total for o in Order.query.all()), 2),
    }
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template("admin/dashboard.html", stats=stats, recent_orders=recent_orders)


@admin_bp.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if not admin_only():
        return redirect(url_for("web.home"))
    if request.method == "POST":
        db.session.add(
            Product(
                name=request.form.get("name", "").strip(),
                category=request.form.get("category", "").strip(),
                price=float(request.form.get("price", 0)),
                mrp=float(request.form.get("mrp", 0)),
                rating=float(request.form.get("rating", 4)),
                stock=int(request.form.get("stock", 0)),
                image=request.form.get("image", "").strip(),
                description=request.form.get("description", "").strip(),
            )
        )
        db.session.commit()
        return redirect(url_for("admin.products"))
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=products)


@admin_bp.route("/orders")
@login_required
def orders():
    if not admin_only():
        return redirect(url_for("web.home"))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    if not admin_only():
        return redirect(url_for("web.home"))
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get("status", "Placed")
    db.session.commit()
    return redirect(url_for("admin.orders"))
