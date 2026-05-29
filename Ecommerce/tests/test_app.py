from app.__init__ import create_app
from app.extensions import db
from app.models import Address, Product, User


def make_client():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(name="Test User", email="test@example.com", is_admin=False)
        user.set_password("pass1234")
        db.session.add(user)
        admin = User(name="Admin", email="admin@example.com", is_admin=True)
        admin.set_password("admin1234")
        db.session.add(admin)
        p = Product(
            name="Test Product",
            category="Electronics",
            price=1000,
            mrp=1500,
            rating=4.2,
            stock=10,
            image="https://example.com/x.jpg",
            description="Test item",
        )
        db.session.add(p)
        db.session.commit()
    return app.test_client(), app


def login(client, email, password):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_home_page_loads():
    client, _ = make_client()
    res = client.get("/")
    assert res.status_code == 200
    assert b"Welcome to India" in res.data


def test_auth_and_cart_checkout_flow():
    client, app = make_client()
    login(client, "test@example.com", "pass1234")
    with app.app_context():
        product = Product.query.first()
    add = client.post("/api/cart/add", json={"product_id": product.id, "quantity": 2})
    assert add.get_json()["success"] is True
    cart = client.get("/api/cart")
    assert cart.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        address = Address(
            user_id=user.id,
            full_name="Test User",
            phone="9999999999",
            line1="Street 1",
            city="Mumbai",
            state="MH",
            pin="400001",
            is_default=True,
        )
        db.session.add(address)
        db.session.commit()
        address_id = address.id
    checkout = client.post("/api/checkout", json={"address_id": address_id, "coupon_code": ""})
    assert checkout.get_json()["success"] is True
    orders = client.get("/orders")
    assert orders.status_code == 200


def test_admin_dashboard_access():
    client, _ = make_client()
    login(client, "admin@example.com", "admin1234")
    res = client.get("/admin/")
    assert res.status_code == 200
    assert b"Admin Dashboard" in res.data
