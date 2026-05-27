"""
🛒 PyStore - Premium E-Commerce Storefront (Amazon-Inspired)
Flask Web UI with modern design, product filters, wishlist & secure checkout

Usage:
    python ecommerce_display.py          # Launch web UI on port 5006
    python ecommerce_display.py --cli    # Original terminal interface
"""

import os
import sys
import json
import uuid
import webbrowser
import threading

# Make sure sibling modules are importable when run from any CWD
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template_string, request, jsonify, session
from products import get_all_products, get_product_by_id, get_categories, filter_by_category, search_products, reduce_stock, get_reviews, Product
from cart import ShoppingCart, CartItem
from payment import PaymentDetails, process_payment, generate_receipt

# ── Flask App ──────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "pystore-ecommerce-premium-secret-2026"

# Session-based shopping carts & wishlists
CARTS = {}
WISHLISTS = {}

def get_cart():
    if 'session_id' not in session:
        session['session_id'] = uuid.uuid4().hex
    session_id = session['session_id']
    if session_id not in CARTS:
        CARTS[session_id] = ShoppingCart()
    return CARTS[session_id]

def get_wishlist():
    if 'session_id' not in session:
        session['session_id'] = uuid.uuid4().hex
    session_id = session['session_id']
    if session_id not in WISHLISTS:
        WISHLISTS[session_id] = set()
    return WISHLISTS[session_id]

# ── HTML Template ──────────────────────────────────────────────
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛒 PyStore - Premium E-Commerce</title>
    <style>
        :root {
            --bg: #0d1117;
            --card: rgba(22, 27, 34, 0.7);
            --border: rgba(255, 255, 255, 0.08);
            --accent: #58a6ff;
            --green: #3fb950;
            --red: #f85149;
            --yellow: #d29922;
            --text: #c9d1d9;
            --muted: #8b949e;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(135deg, var(--accent), var(--green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .cart-info {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .cart-badge {
            background: var(--red);
            color: white;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        
        .search-box input {
            flex: 1;
            padding: 12px 16px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 1em;
        }
        
        .search-box button {
            padding: 12px 24px;
            background: var(--accent);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .search-box button:hover {
            background: var(--green);
        }
        
        .categories {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .category-btn {
            padding: 8px 16px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 20px;
            color: var(--text);
            cursor: pointer;
            transition: 0.3s;
        }
        
        .category-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .product-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: 0.3s;
            cursor: pointer;
        }
        
        .product-card:hover {
            border-color: var(--accent);
            transform: translateY(-5px);
        }
        
        .product-image {
            width: 100%;
            min-height: 200px;
            background: linear-gradient(135deg, rgba(88,166,255,0.2), rgba(63,185,80,0.2));
            background-size: cover;
            background-position: center;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffffcc;
            font-size: 3em;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        
        .product-info {
            padding: 16px;
        }
        
        .product-name {
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 1.1em;
        }
        
        .product-category {
            color: var(--muted);
            font-size: 0.85em;
            margin-bottom: 8px;
        }
        
        .product-price {
            font-size: 1.3em;
            color: var(--yellow);
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .product-rating {
            color: var(--muted);
            margin-bottom: 12px;
            font-size: 0.9em;
        }
        
        .product-stock {
            font-size: 0.85em;
            margin-bottom: 12px;
        }
        
        .product-stock.in-stock {
            color: var(--green);
        }
        
        .product-stock.out-of-stock {
            color: var(--red);
        }
        
        .product-actions {
            display: flex;
            gap: 8px;
        }
        
        .btn {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            transition: 0.3s;
            font-size: 0.9em;
        }
        
        .btn-primary {
            background: var(--accent);
            color: white;
        }
        
        .btn-primary:hover {
            background: var(--green);
        }
        
        .btn-secondary {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent);
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 30px;
            max-width: 90%;
            width: 500px;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        .modal-close {
            float: right;
            font-size: 2em;
            font-weight: bold;
            color: var(--muted);
            cursor: pointer;
            line-height: 1;
        }
        
        .modal-close:hover {
            color: var(--text);
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-size: 1em;
        }
        
        .cart-container {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .cart-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .cart-item:last-child {
            border-bottom: none;
        }
        
        .cart-summary {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 2px solid var(--border);
        }
        
        .summary-line {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 1.1em;
        }
        
        .summary-total {
            font-weight: bold;
            color: var(--yellow);
            font-size: 1.3em;
            margin-top: 16px;
        }
        
        .message {
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-weight: bold;
        }
        
        .message.success {
            background: var(--green)30;
            color: var(--green);
        }
        
        .message.error {
            background: var(--red)30;
            color: var(--red);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛒 PyStore</h1>
            <div class="cart-info">
                <span>Your Cart</span>
                <div class="cart-badge" id="cart-count">0</div>
                <button class="btn btn-primary" onclick="openCart()">View Cart</button>
            </div>
        </header>
        
        <div class="search-box">
            <input type="text" id="search-input" placeholder="Search products, brands, or categories..." />
            <button onclick="searchProducts()">Search</button>
        </div>
        
        <div class="layout">
            <aside class="sidebar">
                <div class="filter-panel">
                    <div class="filter-title">Shop by category</div>
                    <div id="categories-container" class="filter-list"></div>
                </div>
                <div class="filter-panel">
                    <div class="filter-title">Refine results</div>
                    <div class="filter-choice" data-group="price">
                        <div class="filter-label">Price range</div>
                        <button class="filter-option active" onclick="setPriceRange('all', event)">All</button>
                        <button class="filter-option" onclick="setPriceRange('under_1000', event)">Under ₹1,000</button>
                        <button class="filter-option" onclick="setPriceRange('1000_4999', event)">₹1,000–₹4,999</button>
                        <button class="filter-option" onclick="setPriceRange('5000_14999', event)">₹5,000–₹14,999</button>
                        <button class="filter-option" onclick="setPriceRange('15000_plus', event)">₹15,000+</button>
                    </div>
                    <div class="filter-choice" data-group="rating">
                        <div class="filter-label">Customer ratings</div>
                        <button class="filter-option active" onclick="setRating(0, event)">All ratings</button>
                        <button class="filter-option" onclick="setRating(4, event)">4★ &amp; up</button>
                        <button class="filter-option" onclick="setRating(3, event)">3★ &amp; up</button>
                    </div>
                    <div class="filter-choice">
                        <div class="filter-label">Availability</div>
                        <button id="stock-filter" class="filter-option" onclick="toggleInStock(event)">In stock only</button>
                    </div>
                </div>
            </aside>
            <main class="main-content">
                <div class="results-header">
                    <div id="results-summary" class="results-summary">Showing top offers</div>
                    <div class="sort-row">
                        <label for="sort-select">Sort by</label>
                        <select id="sort-select" class="sort-select" onchange="applySortFilter()">
                            <option value="best">Featured</option>
                            <option value="price_asc">Price: Low to High</option>
                            <option value="price_desc">Price: High to Low</option>
                            <option value="rating_desc">Avg. Customer Review</option>
                            <option value="newest">Newest Arrivals</option>
                        </select>
                        <button class="btn btn-secondary" onclick="clearFilters()">Clear filters</button>
                    </div>
                </div>
                <div id="message-container"></div>
                <div class="products-grid" id="products-container"></div>
            </main>
        </div>
    </div>
    
    <!-- Product Details Modal -->
    <div id="product-modal" class="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeModal('product-modal')">&times;</span>
            <div id="modal-body"></div>
        </div>
    </div>
    
    <!-- Cart Modal -->
    <div id="cart-modal" class="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeModal('cart-modal')">&times;</span>
            <h2>🛒 Shopping Cart</h2>
            <div id="cart-container"></div>
        </div>
    </div>
    
    <!-- Checkout Modal -->
    <div id="checkout-modal" class="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeModal('checkout-modal')">&times;</span>
            <h2>💳 Checkout</h2>
            <form id="checkout-form" onsubmit="submitCheckout(event)">
                <div class="form-group">
                    <label>Card Holder Name</label>
                    <input type="text" name="card_holder" required />
                </div>
                <div class="form-group">
                    <label>Card Number</label>
                    <input type="text" name="card_number" placeholder="4242 4242 4242 4242" required />
                </div>
                <div class="form-group">
                    <label>Expiry (MM/YY)</label>
                    <input type="text" name="expiry" placeholder="12/28" required />
                </div>
                <div class="form-group">
                    <label>CVV</label>
                    <input type="password" name="cvv" placeholder="123" required />
                </div>
                <div class="form-group">
                    <label>Billing ZIP</label>
                    <input type="text" name="billing_zip" required />
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">Complete Purchase</button>
            </form>
        </div>
    </div>
    
    <script>
        let currentCart = null;
        let filters = {
            search: "",
            category: null,
            price_range: "all",
            rating: 0,
            in_stock: false,
            sort: "best"
        };

        function buildQuery() {
            const params = new URLSearchParams();
            if (filters.search) params.set('search', filters.search);
            if (filters.category) params.set('category', filters.category);
            if (filters.price_range) params.set('price_range', filters.price_range);
            if (filters.rating) params.set('rating', filters.rating);
            if (filters.in_stock) params.set('in_stock', '1');
            if (filters.sort) params.set('sort', filters.sort);
            return params.toString() ? `?${params.toString()}` : '';
        }

        function updateSummary(count) {
            const summary = document.getElementById('results-summary');
            if (count === 0) {
                summary.textContent = 'No products match your filters';
            } else {
                const category = filters.category ? `${filters.category} ` : '';
                summary.textContent = `Showing ${count} ${category}products`;
            }
        }

        function loadProducts() {
            const query = buildQuery();
            fetch(`/api/products${query}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('products-container');
                    container.innerHTML = '';
                    if (data.products.length === 0) {
                        container.innerHTML = '<p style="color: var(--muted);">No products found. Try changing filters or search terms.</p>';
                        updateSummary(0);
                        return;
                    }
                    data.products.forEach(p => {
                        const card = document.createElement('div');
                        card.className = 'product-card';
                        const imageStyle = p.image_url ? `background-image: url('${p.image_url}')` : '';
                        const fallbackEmoji = ['🎮', '📱', '💻', '🎧', '⌚', '📷', '🎥', '📚'][p.id % 8];
                        card.innerHTML = `
                            <div class="product-image" style="${imageStyle}">${p.image_url ? '' : fallbackEmoji}</div>
                            <div class="product-info">
                                <div class="product-name">${p.name}</div>
                                <div class="product-category">${p.category}</div>
                                <div class="product-price">₹${p.price.toFixed(2)}</div>
                                <div class="product-rating">⭐ ${p.rating}</div>
                                <div class="product-stock ${p.stock > 0 ? 'in-stock' : 'out-of-stock'}">
                                    ${p.stock > 0 ? `${p.stock} in stock` : 'Out of stock'}
                                </div>
                                <div class="product-actions">
                                    <button class="btn btn-primary" onclick="window.open('/product/${p.id}', '_blank')">View</button>
                                    ${p.stock > 0 ? `<button class="btn btn-secondary" onclick="quickAdd(${p.id})">Add</button>` : ''}
                                </div>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                    updateSummary(data.products.length);
                });
        }

        function loadCategories() {
            fetch('/api/categories')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('categories-container');
                    container.innerHTML = '<button class="category-btn active" onclick="filterCategory(event, null)">All</button>';
                    data.categories.forEach(cat => {
                        const btn = document.createElement('button');
                        btn.className = 'category-btn';
                        btn.textContent = cat;
                        btn.onclick = (evt) => filterCategory(evt, cat);
                        container.appendChild(btn);
                    });
                });
        }

        function filterCategory(event, category) {
            filters.category = category;
            document.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('active'));
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            } else if (event && event.target) {
                event.target.classList.add('active');
            }
            loadProducts();
        }

        function setPriceRange(range, event) {
            filters.price_range = range;
            document.querySelectorAll('.filter-choice[data-group="price"] .filter-option').forEach(btn => btn.classList.remove('active'));
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            }
            loadProducts();
        }

        function setRating(minRating, event) {
            filters.rating = minRating;
            document.querySelectorAll('.filter-choice[data-group="rating"] .filter-option').forEach(btn => btn.classList.remove('active'));
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            }
            loadProducts();
        }

        function toggleInStock(event) {
            filters.in_stock = !filters.in_stock;
            if (event && event.currentTarget) {
                event.currentTarget.classList.toggle('active', filters.in_stock);
            }
            loadProducts();
        }

        function applySortFilter() {
            filters.sort = document.getElementById('sort-select').value;
            loadProducts();
        }

        function searchProducts() {
            filters.search = document.getElementById('search-input').value.trim();
            loadProducts();
        }

        function clearFilters() {
            filters = {
                search: "",
                category: null,
                price_range: "all",
                rating: 0,
                in_stock: false,
                sort: "best"
            };
            document.getElementById('search-input').value = '';
            const categoryButtons = document.querySelectorAll('.category-btn');
            categoryButtons.forEach((btn, index) => {
                btn.classList.toggle('active', index === 0);
            });
            document.querySelectorAll('.filter-choice[data-group="price"] .filter-option').forEach((btn, index) => {
                btn.classList.toggle('active', index === 0);
            });
            document.querySelectorAll('.filter-choice[data-group="rating"] .filter-option').forEach((btn, index) => {
                btn.classList.toggle('active', index === 0);
            });
            const stockFilter = document.getElementById('stock-filter');
            if (stockFilter) {
                stockFilter.classList.remove('active');
            }
            document.getElementById('sort-select').value = 'best';
            loadProducts();
        }

        function showMessage(msg, type) {
            const container = document.getElementById('message-container');
            container.innerHTML = `<div class="message ${type}">${msg}</div>`;
            setTimeout(() => { container.innerHTML = ''; }, 3000);
        }
        
        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }
        
        // Initialize
        loadProducts();
        loadCategories();
        updateCartCount();
    </script>
</body>
</html>
"""

DETAIL_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ product.name }} - PyStore</title>
    <style>
        :root {
            --bg: #0d1117;
            --card: rgba(22, 27, 34, 0.95);
            --border: rgba(255, 255, 255, 0.08);
            --accent: #58a6ff;
            --green: #3fb950;
            --yellow: #d29922;
            --text: #c9d1d9;
            --muted: #8b949e;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            min-height: 100vh;
            padding: 24px;
        }
        a { color: var(--accent); text-decoration: none; }
        a:hover { text-decoration: underline; }
        .page { max-width: 1120px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .breadcrumb { color: var(--muted); font-size: 0.95em; }
        .grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 28px; }
        .product-panel, .details-panel { background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 26px; }
        .hero-image { width: 100%; min-height: 360px; border-radius: 18px; background: var(--border); background-size: cover; background-position: center; margin-bottom: 20px; }
        .title { font-size: 2.4rem; margin-bottom: 8px; }
        .meta { color: var(--muted); margin-bottom: 18px; }
        .price { font-size: 2rem; font-weight: bold; color: var(--yellow); margin-bottom: 12px; }
        .badge { display: inline-flex; gap: 8px; align-items: center; padding: 10px 14px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--text); font-size: 0.92em; margin-right: 10px; }
        .rating { font-size: 1rem; color: var(--text); margin-bottom: 16px; }
        .description { line-height: 1.75; margin-bottom: 20px; }
        .btn-primary { display: inline-flex; align-items: center; gap: 10px; padding: 14px 24px; background: var(--accent); color: white; border: none; border-radius: 14px; cursor: pointer; font-weight: bold; transition: 0.25s; }
        .btn-primary:hover { background: var(--green); }
        .section-title { font-size: 1.1rem; margin-bottom: 14px; letter-spacing: 0.04em; color: var(--text); }
        .review { border-top: 1px solid rgba(255,255,255,0.08); padding: 18px 0; }
        .review:first-child { border-top: none; }
        .review-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .review-author { color: var(--muted); font-size: 0.95em; }
        .review-comment { line-height: 1.7; color: var(--text); }
        .info-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
        .info-card { flex: 1; min-width: 140px; border-radius: 16px; border: 1px solid var(--border); background: rgba(255,255,255,0.03); padding: 18px; }
    </style>
</head>
<body>
    <div class="page">
        <div class="header">
            <div>
                <div class="breadcrumb"><a href="/">Home</a> / {{ product.category }} / {{ product.name }}</div>
                <h1 class="title">{{ product.name }}</h1>
            </div>
            <a class="btn-primary" href="/">Back to Store</a>
        </div>
        <div class="grid">
            <section class="product-panel">
                <div class="hero-image" style="background-image: url('{{ product.image_url }}');"></div>
                <div class="meta">{{ product.category }} · {{ product.stock }} in stock · Rating {{ product.rating }} ★</div>
                <div class="price">₹{{ product.price }}</div>
                <div class="info-row">
                    <div class="info-card"><strong>{{ product.stock }}</strong><br/>Units available</div>
                    <div class="info-card"><strong>{{ reviews | length }}</strong><br/>Customer reviews</div>
                    <div class="info-card"><strong>{{ product.rating }}</strong><br/>Average rating</div>
                </div>
                <div class="description">{{ product.description }}</div>
                <div class="form-group">
                    <label for="qty">Quantity</label>
                    <input id="qty" type="number" min="1" max="{{ product.stock }}" value="1" style="width: 100%; padding: 12px; border-radius: 12px; border: 1px solid var(--border); background: var(--bg); color: var(--text);" />
                </div>
                <button class="btn-primary" onclick="addToCart({{ product.id }})">Add to Cart</button>
                <div id="message-container" style="margin-top: 18px;"></div>
            </section>
            <aside class="details-panel">
                <div class="section-title">Product Overview</div>
                <p class="description">{{ product.description }}</p>
                <div class="section-title">Customer reviews</div>
                {% if reviews %}
                    {% for review in reviews %}
                        <div class="review">
                            <div class="review-title">
                                <strong>{{ review.title }}</strong>
                                <span>{{ review.rating }} ★</span>
                            </div>
                            <div class="review-author">{{ review.author }}</div>
                            <p class="review-comment">{{ review.comment }}</p>
                        </div>
                    {% endfor %}
                {% else %}
                    <p style="color: var(--muted);">No reviews yet. Be the first to review this product.</p>
                {% endif %}
            </aside>
        </div>
    </div>
    <script>
        function addToCart(productId) {
            const qty = parseInt(document.getElementById('qty').value, 10) || 1;
            fetch('/api/add-to-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: productId, quantity: qty})
            })
            .then(r => r.json())
            .then(data => {
                const container = document.getElementById('message-container');
                container.innerHTML = `<div style="padding: 12px; border-radius: 10px; background: ${data.success ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)'}; color: ${data.success ? '#3fb950' : '#f85149'};">${data.message}</div>`;
            });
        }
    </script>
</body>
</html>
"""

# ── Rich Terminal UI (Legacy CLI) ──────────────────────────────

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich.prompt  import Prompt, Confirm
from rich         import box
from rich.columns import Columns
from rich.align   import Align

console = Console()


# ── Flask API Routes ──────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    p = get_product_by_id(product_id)
    if not p:
        return render_template_string("<h1>Product not found</h1><p><a href='/'>Back to store</a></p>"), 404
    reviews = get_reviews(product_id)
    return render_template_string(DETAIL_TEMPLATE, product={
        'id': p.id,
        'name': p.name,
        'price': f"{p.price:,.2f}",
        'category': p.category,
        'stock': p.stock,
        'rating': p.rating,
        'description': p.description,
        'image_url': p.image_url or 'https://images.unsplash.com/photo-1513708923556-7dc0fcf2f98c?w=900&q=80',
    }, reviews=reviews)

@app.route('/api/products')
def api_products():
    category = request.args.get('category', '').strip()
    search_term = request.args.get('search', '').strip()
    price_range = request.args.get('price_range', 'all')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    rating = request.args.get('rating')
    in_stock = request.args.get('in_stock', '0')
    sort = request.args.get('sort', 'best')

    if category:
        products = filter_by_category(category)
    else:
        products = get_all_products()

    if search_term:
        search_results = search_products(search_term)
        products = [p for p in products if p in search_results]

    if price_range != 'all':
        if price_range == 'under_1000':
            min_price, max_price = 0, 999
        elif price_range == '1000_4999':
            min_price, max_price = 1000, 4999
        elif price_range == '5000_14999':
            min_price, max_price = 5000, 14999
        elif price_range == '15000_plus':
            min_price, max_price = 15000, None

    try:
        if min_price is not None and min_price != '':
            min_value = float(min_price)
            products = [p for p in products if p.price >= min_value]
        if max_price is not None and max_price != '':
            max_value = float(max_price)
            products = [p for p in products if p.price <= max_value]
    except ValueError:
        pass

    if rating:
        try:
            min_rating = float(rating)
            products = [p for p in products if p.rating >= min_rating]
        except ValueError:
            pass

    if in_stock == '1':
        products = [p for p in products if p.stock > 0]

    if sort == 'price_asc':
        products = sorted(products, key=lambda p: p.price)
    elif sort == 'price_desc':
        products = sorted(products, key=lambda p: p.price, reverse=True)
    elif sort == 'rating_desc':
        products = sorted(products, key=lambda p: p.rating, reverse=True)
    elif sort == 'newest':
        products = sorted(products, key=lambda p: p.id, reverse=True)
    else:
        products = sorted(products, key=lambda p: (p.rating, p.stock), reverse=True)

    return jsonify({"products": [
        {"id": p.id, "name": p.name, "price": p.price, "category": p.category,
         "stock": p.stock, "rating": p.rating, "description": p.description,
         "image_url": p.image_url}
        for p in products
    ]})

@app.route('/api/product/<int:product_id>')
def api_product(product_id):
    p = get_product_by_id(product_id)
    if not p:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"id": p.id, "name": p.name, "price": p.price, "category": p.category,
                    "stock": p.stock, "rating": p.rating, "description": p.description,
                    "image_url": p.image_url})

@app.route('/api/categories')
def api_categories():
    return jsonify({"categories": get_categories()})

@app.route('/api/add-to-cart', methods=['POST'])
def api_add_to_cart():
    data = request.json
    cart = get_cart()
    msg = cart.add_item(data['product_id'], data.get('quantity', 1))
    success = not any(keyword in msg.lower() for keyword in ["not found", "out of stock", "only"])
    return jsonify({"message": msg, "success": success})

@app.route('/api/remove-from-cart', methods=['POST'])
def api_remove_from_cart():
    data = request.json
    cart = get_cart()
    msg = cart.remove_item(data['product_id'])
    return jsonify({"success": True, "message": msg})

@app.route('/api/cart')
def api_cart():
    cart = get_cart()
    items = [
        {"product": {"id": item.product.id, "name": item.product.name,
                      "price": item.product.price, "image_url": item.product.image_url},
         "quantity": item.quantity, "subtotal": item.subtotal}
        for item in cart.items()
    ]
    return jsonify({"items": items, "summary": cart.summary()})

@app.route('/api/cart-count')
def api_cart_count():
    cart = get_cart()
    return jsonify({"count": sum(item.quantity for item in cart.items())})

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    products = search_products(query)
    return jsonify({"products": [
        {"id": p.id, "name": p.name, "price": p.price, "category": p.category,
         "stock": p.stock, "rating": p.rating, "description": p.description,
         "image_url": p.image_url}
        for p in products
    ]})

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    cart = get_cart(session.get('session_id', 'default'))
    if cart.is_empty():
        return jsonify({"success": False, "message": "Cart is empty"})
    
    try:
        details = PaymentDetails(
            card_number=request.form.get('card_number'),
            card_holder=request.form.get('card_holder'),
            expiry=request.form.get('expiry'),
            cvv=request.form.get('cvv'),
            billing_zip=request.form.get('billing_zip')
        )
        summary = cart.summary()
        result = process_payment(details, summary['total'])
        
        if result.success:
            for item in cart.items():
                reduce_stock(item.product.id, item.quantity)
            cart.clear()
            return jsonify({"success": True, "transaction_id": result.transaction_id})
        else:
            return jsonify({"success": False, "message": result.message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ── Terminal UI Functions ──────────────────────────────────────

def show_banner():
    title = Text("🛒  PyStore – Python E-Commerce  🛒", style="bold magenta")
    console.print(Panel(Align.center(title), border_style="magenta", expand=False))
    console.print()


# ── main menu ────────────────────────────────────────────────

def show_main_menu() -> str:
    console.print("[bold cyan]═══ MAIN MENU ═══[/]")
    console.print("  [1] Browse all products")
    console.print("  [2] Browse by category")
    console.print("  [3] Search products")
    console.print("  [4] View cart")
    console.print("  [5] Checkout")
    console.print("  [6] Apply coupon")
    console.print("  [0] Exit")
    return Prompt.ask("\n[bold]Your choice[/]").strip()


# ── product listing ──────────────────────────────────────────

def _star_rating(rating: float) -> str:
    full  = int(rating)
    empty = 5 - full
    return "★" * full + "☆" * empty + f"  {rating}"


def show_product_table(products: list[Product], title: str = "Products"):
    if not products:
        console.print("[yellow]No products found.[/]")
        return
    table = Table(
        title=title, box=box.ROUNDED, border_style="magenta",
        header_style="bold white on dark_magenta", show_lines=True,
    )
    table.add_column("ID",          style="bold cyan",   justify="right",  width=4)
    table.add_column("Name",        style="bold white",  justify="left",   width=28)
    table.add_column("Category",    style="green",       justify="left",   width=12)
    table.add_column("Price",       style="bold yellow", justify="right",  width=9)
    table.add_column("Stock",       style="cyan",        justify="center", width=7)
    table.add_column("Rating",      style="yellow",      justify="left",   width=13)

    for p in products:
        stock_str = f"[green]{p.stock}[/]" if p.stock > 5 else (
            f"[yellow]{p.stock}[/]" if p.stock > 0 else "[red]Out[/]"
        )
        table.add_row(
            str(p.id),
            p.name,
            p.category,
            p.formatted_price(),
            stock_str,
            _star_rating(p.rating),
        )
    console.print(table)
    console.print()


def show_product_detail(p: Product):
    stock_label = f"[green]{p.stock} in stock[/]" if p.stock > 0 else "[red]Out of stock[/]"
    body = (
        f"[bold yellow]Category    :[/]  {p.category}\n"
        f"[bold yellow]Price       :[/]  [bold green]{p.formatted_price()}[/]\n"
        f"[bold yellow]Rating      :[/]  {_star_rating(p.rating)}\n"
        f"[bold yellow]Availability:[/]  {stock_label}\n"
        f"[bold yellow]Description :[/]  {p.description}"
    )
    console.print(Panel(body, title=f"#{p.id}  {p.name}", border_style="green"))
    console.print()


# ── category menu ────────────────────────────────────────────

def show_categories(categories: list[str]) -> str:
    console.print("[bold cyan]Categories:[/]")
    for i, cat in enumerate(categories, 1):
        console.print(f"  [{i}] {cat}")
    console.print("  [0] Back")
    return Prompt.ask("[bold]Choose[/]").strip()


# ── cart display ─────────────────────────────────────────────

def show_cart(items: list[CartItem], summary: dict):
    if not items:
        console.print(Panel("[yellow]Your cart is empty.[/]",
                            title="🛒 Shopping Cart", border_style="yellow"))
        console.print()
        return

    table = Table(
        title="🛒 Shopping Cart", box=box.ROUNDED,
        border_style="yellow", header_style="bold white", show_lines=True,
    )
    table.add_column("ID",       style="cyan",        justify="right",  width=4)
    table.add_column("Product",  style="bold white",  justify="left",   width=30)
    table.add_column("Unit $",   style="yellow",      justify="right",  width=8)
    table.add_column("Qty",      style="cyan",        justify="center", width=5)
    table.add_column("Subtotal", style="bold green",  justify="right",  width=10)

    for item in items:
        table.add_row(
            str(item.product.id),
            item.product.name,
            f"${item.product.price:.2f}",
            str(item.quantity),
            f"${item.subtotal:.2f}",
        )
    console.print(table)

    # Summary panel
    lines = [f"[white]Items       :[/]  {summary['item_count']}"]
    lines.append(f"[white]Subtotal    :[/]  [yellow]${summary['subtotal']:.2f}[/]")
    if summary["discount_amount"] > 0:
        pct = int(summary["discount_pct"] * 100)
        lines.append(
            f"[white]Discount ({summary['coupon_code']} {pct}%)[/]  "
            f"[green]-${summary['discount_amount']:.2f}[/]"
        )
    ship_str = "[green]FREE[/]" if summary["shipping"] == 0 else f"${summary['shipping']:.2f}"
    lines.append(f"[white]Shipping    :[/]  {ship_str}")
    lines.append(f"[white]Tax (8%)    :[/]  ${summary['tax']:.2f}")
    lines.append(f"[bold yellow]TOTAL       :[/]  [bold green]${summary['total']:.2f}[/]")
    if summary["shipping"] > 0:
        from cart import ShoppingCart
        lines.append(
            f"[dim]Add ${ShoppingCart.SHIPPING_FREE - summary['after_discount']:.2f} "
            f"more for free shipping[/]"
        )

    console.print(Panel("\n".join(lines), title="Price Summary", border_style="green"))
    console.print()


def show_cart_menu() -> str:
    console.print("[bold cyan]Cart Options:[/]")
    console.print("  [1] Add item by ID")
    console.print("  [2] Remove item")
    console.print("  [3] Update quantity")
    console.print("  [4] Clear cart")
    console.print("  [0] Back to main menu")
    return Prompt.ask("[bold]Choice[/]").strip()


# ── checkout UI ──────────────────────────────────────────────

def collect_payment_details() -> dict:
    """Prompt for payment info; return as dict."""
    console.print(Panel("💳  Payment Details", border_style="blue", expand=False))
    console.print("[dim]Test card: 4242 4242 4242 4242  Exp: 12/28  CVV: 123[/]\n")
    name   = Prompt.ask("[bold]Card Holder Name[/]")
    number = Prompt.ask("[bold]Card Number     [/]")
    expiry = Prompt.ask("[bold]Expiry (MM/YY)  [/]")
    cvv    = Prompt.ask("[bold]CVV             [/]", password=True)
    zipcd  = Prompt.ask("[bold]Billing ZIP     [/]")
    return dict(card_holder=name, card_number=number,
                expiry=expiry, cvv=cvv, billing_zip=zipcd)


def show_payment_processing():
    console.print("\n[bold yellow]⏳ Processing payment …[/]")


def show_payment_result(result):
    if result.success:
        console.print(Panel(
            f"[bold green]✓  {result.message}[/]\n"
            f"Transaction ID: [cyan]{result.transaction_id}[/]",
            title="✅ Payment Successful", border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]✗  {result.message}[/]",
            title="❌ Payment Failed", border_style="red",
        ))
    console.print()


def show_receipt(receipt_text: str):
    console.print()
    console.print(Panel(receipt_text, title="Your Receipt", border_style="cyan",
                        expand=False))
    console.print()


# ── helpers ──────────────────────────────────────────────────

def ask_int(prompt: str, default: int | None = None) -> int | None:
    raw = Prompt.ask(f"[bold]{prompt}[/]",
                     default=str(default) if default is not None else "").strip()
    try:
        return int(raw)
    except ValueError:
        return None


def confirm(prompt: str) -> bool:
    return Confirm.ask(f"[bold]{prompt}[/]")


def info(msg: str):
    console.print(f"[green]{msg}[/]")


def warn(msg: str):
    console.print(f"[yellow]{msg}[/]")


def err(msg: str):
    console.print(f"[bold red]{msg}[/]")


# ─── Main Shopping Loop (CLI Mode) ────────────────────────────

def main_cli():
    cart = ShoppingCart()
    show_banner()

    while True:
        try:
            choice = show_main_menu()
            if choice == '0':
                console.print("[bold cyan]Thank you for visiting PyStore! Goodbye! 🛒[/]")
                break
            elif choice == '1':
                # Browse all products
                products = get_all_products()
                show_product_table(products, "All Products")
                
                pid = ask_int("Enter Product ID to view details / add to cart (or 0 to back)")
                if pid:
                    p = get_product_by_id(pid)
                    if p:
                        show_product_detail(p)
                        if p.stock > 0:
                            if confirm(f"Add '{p.name}' to cart?"):
                                qty = ask_int("Quantity", default=1)
                                if qty and qty > 0:
                                    msg = cart.add_item(pid, qty)
                                    info(msg)
                        else:
                            warn("This product is out of stock.")
                    else:
                        err(f"Product #{pid} not found.")
            elif choice == '2':
                # Browse by category
                cats = get_categories()
                cat_choice = show_categories(cats)
                if cat_choice != '0' and cat_choice.isdigit():
                    idx = int(cat_choice) - 1
                    if 0 <= idx < len(cats):
                        cat_name = cats[idx]
                        products = filter_by_category(cat_name)
                        show_product_table(products, f"Category: {cat_name}")
                        
                        pid = ask_int("Enter Product ID to view details / add to cart (or 0 to back)")
                        if pid:
                            p = get_product_by_id(pid)
                            if p:
                                show_product_detail(p)
                                if p.stock > 0:
                                    if confirm(f"Add '{p.name}' to cart?"):
                                        qty = ask_int("Quantity", default=1)
                                        if qty and qty > 0:
                                            msg = cart.add_item(pid, qty)
                                            info(msg)
                                else:
                                    warn("This product is out of stock.")
                            else:
                                err(f"Product #{pid} not found.")
            elif choice == '3':
                # Search products
                query = Prompt.ask("[bold]Enter search term[/]").strip()
                if query:
                    products = search_products(query)
                    show_product_table(products, f"Search Results for '{query}'")
                    pid = ask_int("Enter Product ID to view details / add to cart (or 0 to back)")
                    if pid:
                        p = get_product_by_id(pid)
                        if p:
                            show_product_detail(p)
                            if p.stock > 0:
                                if confirm(f"Add '{p.name}' to cart?"):
                                    qty = ask_int("Quantity", default=1)
                                    if qty and qty > 0:
                                        msg = cart.add_item(pid, qty)
                                        info(msg)
                            else:
                                warn("This product is out of stock.")
                        else:
                            err(f"Product #{pid} not found.")
            elif choice == '4':
                # View cart
                while True:
                    show_cart(cart.items(), cart.summary())
                    if cart.is_empty():
                        break
                    cart_choice = show_cart_menu()
                    if cart_choice == '0':
                        break
                    elif cart_choice == '1':
                        pid = ask_int("Enter Product ID to add/increment")
                        if pid:
                            qty = ask_int("Quantity to add", default=1)
                            if qty and qty > 0:
                                info(cart.add_item(pid, qty))
                    elif cart_choice == '2':
                        pid = ask_int("Enter Product ID to remove")
                        if pid:
                            info(cart.remove_item(pid))
                    elif cart_choice == '3':
                        pid = ask_int("Enter Product ID to update")
                        if pid:
                            qty = ask_int("New quantity")
                            if qty is not None:
                                info(cart.update_quantity(pid, qty))
                    elif cart_choice == '4':
                        if confirm("Are you sure you want to clear your cart?"):
                            cart.clear()
                            info("Cart cleared.")
                            break
            elif choice == '5':
                # Checkout
                if cart.is_empty():
                    warn("Your cart is empty! Add some products first.")
                    continue
                show_cart(cart.items(), cart.summary())
                if confirm("Proceed to checkout?"):
                    payment_info = collect_payment_details()
                    show_payment_processing()
                    details = PaymentDetails(
                        card_number=payment_info['card_number'],
                        card_holder=payment_info['card_holder'],
                        expiry=payment_info['expiry'],
                        cvv=payment_info['cvv'],
                        billing_zip=payment_info['billing_zip']
                    )
                    summary = cart.summary()
                    res = process_payment(details, summary['total'])
                    show_payment_result(res)
                    if res.success:
                        # reduce stock
                        for item in cart.items():
                            reduce_stock(item.product.id, item.quantity)
                        receipt_text = generate_receipt(res, cart.items(), summary)
                        show_receipt(receipt_text)
                        cart.clear()
            elif choice == '6':
                # Apply coupon
                if cart.is_empty():
                    warn("Add items to your cart first.")
                    continue
                code = Prompt.ask("[bold]Enter coupon code (e.g., SAVE10, SAVE20, TECH15)[/]").strip()
                if code:
                    msg = cart.apply_coupon(code)
                    if "applied" in msg:
                        info(msg)
                    else:
                        err(msg)
        except KeyboardInterrupt:
            console.print("\n[bold cyan]Thank you for visiting PyStore! Goodbye! 🛒[/]")
            break

# ── Main entry point ──────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        # Launch original terminal UI
        main_cli()
    else:
        # Launch Flask web UI
        print("🛒 PyStore Web UI starting on http://localhost:5006")
        print("   Visit the URL above in your browser")
        print("   Press Ctrl+C to stop the server")
        print("\nRun with --cli flag to use the original terminal interface:")
        print("   python ecommerce_display.py --cli\n")
        
        # Open browser automatically
        def open_browser():
            import time
            time.sleep(2)
            webbrowser.open('http://localhost:5006')
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        app.run(host="127.0.0.1", port=5006, debug=False)
