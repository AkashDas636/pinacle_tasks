"""
🛒 PyStore - Premium E-Commerce Storefront (Amazon-Inspired)
Enhanced Flask Web UI with modern design, advanced filters, wishlist & secure checkout

Usage:
    python ecommerce_display_enhanced.py          # Launch web UI on port 5006
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

# ── HTML Template (Amazon-Inspired Design) ──────────────────────
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛒 PyStore - Online Shopping</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #131921;
            --secondary: #1a2332;
            --accent: #FF9900;
            --accent-dark: #c67700;
            --text: #0f1419;
            --text-light: #565959;
            --border: #ddd;
            --bg-light: #f5f5f5;
            --success: #28a745;
            --warning: #ff9900;
            --danger: #dc3545;
            --white: #fff;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Amazon Ember', Arial, sans-serif;
            background-color: var(--bg-light);
            color: var(--text);
        }
        
        /* ── HEADER ────────────────────────────────────────────────────── */
        .header {
            background-color: var(--primary);
            color: var(--white);
            padding: 12px 20px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }
        
        .header-top {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 10px;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            text-decoration: none;
            color: var(--white);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .logo:hover { color: var(--accent); }
        
        .search-container {
            flex: 1;
            max-width: 600px;
            display: flex;
        }
        
        .search-select {
            padding: 8px 12px;
            border: none;
            border-radius: 4px 0 0 4px;
            background: var(--white);
            color: var(--text);
            font-size: 12px;
            min-width: 80px;
        }
        
        .search-input {
            flex: 1;
            padding: 8px 12px;
            border: none;
            font-size: 14px;
            background: var(--white);
        }
        
        .search-button {
            padding: 8px 16px;
            background: var(--accent);
            border: none;
            border-radius: 0 4px 4px 0;
            color: var(--text);
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .search-button:hover { background: var(--accent-dark); }
        
        .header-actions {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .nav-item {
            color: var(--white);
            text-decoration: none;
            font-size: 13px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .nav-item:hover { color: var(--accent); }
        
        .cart-icon {
            position: relative;
        }
        
        .cart-count {
            position: absolute;
            top: -8px;
            right: -8px;
            background: var(--accent);
            color: var(--text);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 12px;
        }
        
        .header-bottom {
            display: flex;
            gap: 20px;
            font-size: 13px;
            align-items: center;
        }
        
        .category-link {
            color: var(--white);
            text-decoration: none;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .category-link:hover { color: var(--accent); }
        
        /* ── MAIN LAYOUT ────────────────────────────────────────────────── */
        .container {
            max-width: 1920px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .main-wrapper {
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 20px;
        }
        
        /* ── SIDEBAR FILTERS ──────────────────────────────────────────────── */
        .sidebar {
            background: var(--white);
            border-radius: 8px;
            padding: 16px;
            height: fit-content;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .filter-group {
            border-bottom: 1px solid var(--border);
            padding: 12px 0;
            margin-bottom: 12px;
        }
        
        .filter-group:last-child {
            border-bottom: none;
        }
        
        .filter-title {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 12px;
            color: var(--text);
        }
        
        .filter-option {
            display: block;
            padding: 8px 0;
            font-size: 13px;
            color: var(--text-light);
            text-decoration: none;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .filter-option:hover, .filter-option.active {
            color: var(--accent);
            font-weight: bold;
        }
        
        .price-slider {
            width: 100%;
            margin: 10px 0;
        }
        
        .rating-stars {
            display: flex;
            align-items: center;
            gap: 5px;
            margin: 8px 0;
            cursor: pointer;
            padding: 8px;
            border-radius: 4px;
            transition: 0.3s;
        }
        
        .rating-stars:hover {
            background: rgba(255, 153, 0, 0.1);
        }
        
        /* ── MAIN CONTENT ──────────────────────────────────────────────────── */
        .content {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .results-header {
            background: var(--white);
            border-radius: 8px;
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .results-summary {
            font-size: 14px;
            color: var(--text-light);
        }
        
        .sort-section {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .sort-section label {
            font-size: 13px;
            font-weight: bold;
        }
        
        .sort-select {
            padding: 6px 10px;
            border: 1px solid var(--border);
            border-radius: 4px;
            font-size: 13px;
            cursor: pointer;
        }
        
        /* ── PRODUCTS GRID ──────────────────────────────────────────────────── */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 16px;
        }
        
        .product-card {
            background: var(--white);
            border-radius: 8px;
            padding: 12px;
            text-decoration: none;
            color: var(--text);
            transition: 0.3s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            position: relative;
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        
        .product-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transform: translateY(-2px);
        }
        
        .product-image {
            width: 100%;
            height: 160px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            background-size: cover;
            background-position: center;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255,255,255,0.8);
            font-size: 60px;
        }
        
        .product-name {
            font-size: 13px;
            font-weight: bold;
            line-height: 1.4;
            height: 28px;
            overflow: hidden;
            margin-bottom: 6px;
            flex-grow: 1;
        }
        
        .product-rating {
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 6px;
            font-size: 12px;
        }
        
        .stars {
            color: #f08804;
        }
        
        .rating-count {
            color: var(--text-light);
            font-size: 11px;
        }
        
        .product-price {
            font-size: 18px;
            font-weight: bold;
            color: var(--text);
            margin-bottom: 8px;
        }
        
        .price-original {
            font-size: 12px;
            color: var(--text-light);
            text-decoration: line-through;
            margin-right: 8px;
        }
        
        .discount-badge {
            background: var(--danger);
            color: var(--white);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }
        
        .product-actions {
            display: flex;
            gap: 6px;
            margin-top: auto;
        }
        
        .btn {
            flex: 1;
            padding: 8px 10px;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        
        .btn-primary {
            background: var(--accent);
            color: var(--text);
        }
        
        .btn-primary:hover {
            background: var(--accent-dark);
        }
        
        .btn-secondary {
            background: var(--white);
            border: 1px solid var(--border);
            color: var(--text);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        
        .wishlist-btn {
            width: 36px;
            height: 36px;
            padding: 0;
            position: absolute;
            top: 8px;
            right: 8px;
            background: var(--white);
            border: 1px solid var(--border);
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            transition: 0.3s;
        }
        
        .wishlist-btn:hover, .wishlist-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: var(--text);
        }
        
        /* ── MODALS ────────────────────────────────────────────────────── */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--white);
            border-radius: 8px;
            padding: 24px;
            max-width: 600px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            position: relative;
        }
        
        .modal-close {
            position: absolute;
            top: 16px;
            right: 16px;
            font-size: 28px;
            font-weight: bold;
            color: var(--text-light);
            cursor: pointer;
            background: none;
            border: none;
        }
        
        .modal-close:hover {
            color: var(--text);
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 4px;
            font-size: 14px;
        }
        
        /* ── CART DISPLAY ──────────────────────────────────────────────────── */
        .cart-item {
            display: flex;
            gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            align-items: flex-start;
        }
        
        .cart-item:last-child {
            border-bottom: none;
        }
        
        .cart-item-image {
            width: 80px;
            height: 80px;
            background: var(--bg-light);
            border-radius: 4px;
            flex-shrink: 0;
            background-size: cover;
            background-position: center;
        }
        
        .cart-item-details {
            flex: 1;
        }
        
        .cart-item-name {
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .cart-item-price {
            font-weight: bold;
            color: var(--text);
            margin-bottom: 8px;
        }
        
        .quantity-selector {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }
        
        .qty-btn {
            width: 24px;
            height: 24px;
            border: 1px solid var(--border);
            background: var(--white);
            cursor: pointer;
            border-radius: 2px;
        }
        
        .cart-summary {
            background: var(--bg-light);
            padding: 12px;
            border-radius: 4px;
            margin-top: 16px;
        }
        
        .summary-line {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        .summary-line.total {
            border-top: 1px solid var(--border);
            padding-top: 8px;
            margin-top: 8px;
            font-weight: bold;
            font-size: 16px;
        }
        
        .message {
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 16px;
            font-size: 13px;
        }
        
        .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        /* ── RESPONSIVE ────────────────────────────────────────────────────── */
        @media (max-width: 768px) {
            .main-wrapper {
                grid-template-columns: 1fr;
            }
            
            .header-top {
                flex-direction: column;
                gap: 10px;
            }
            
            .search-container {
                max-width: 100%;
            }
            
            .header-bottom {
                flex-wrap: wrap;
            }
            
            .products-grid {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }
            
            .results-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
        }
    </style>
</head>
<body>
    <!-- HEADER -->
    <header class="header">
        <div class="header-top">
            <a href="/" class="logo">🛒 PyStore</a>
            <div class="search-container">
                <select class="search-select" id="search-category">
                    <option value="">All</option>
                </select>
                <input type="text" class="search-input" id="search-input" placeholder="Search products, brands...">
                <button class="search-button" onclick="searchProducts()"><i class="fas fa-search"></i></button>
            </div>
            <div class="header-actions">
                <a href="#" class="nav-item" onclick="openWishlist()">
                    <i class="fas fa-heart"></i>
                    <span>Wishlist</span>
                </a>
                <a href="#" class="nav-item" onclick="openCart()">
                    <div class="cart-icon">
                        <i class="fas fa-shopping-cart"></i>
                        <span class="cart-count" id="cart-count">0</span>
                    </div>
                    <span>Cart</span>
                </a>
            </div>
        </div>
        <div class="header-bottom">
            <span class="category-link" onclick="filterCategory(null)"><strong>All</strong></span>
            <span class="category-link" id="categories-header"></span>
        </div>
    </header>

    <!-- MAIN CONTENT -->
    <div class="container">
        <div class="main-wrapper">
            <!-- SIDEBAR FILTERS -->
            <aside class="sidebar">
                <div class="filter-group">
                    <div class="filter-title">Categories</div>
                    <a class="filter-option active" onclick="filterCategory(null)">All Categories</a>
                    <div id="categories-sidebar"></div>
                </div>

                <div class="filter-group">
                    <div class="filter-title">Price</div>
                    <a class="filter-option" onclick="setPriceRange('all')">All Prices</a>
                    <a class="filter-option" onclick="setPriceRange('under_1000')">Under ₹1,000</a>
                    <a class="filter-option" onclick="setPriceRange('1000_4999')">₹1,000–₹4,999</a>
                    <a class="filter-option" onclick="setPriceRange('5000_14999')">₹5,000–₹14,999</a>
                    <a class="filter-option" onclick="setPriceRange('15000_plus')">₹15,000+</a>
                </div>

                <div class="filter-group">
                    <div class="filter-title">Ratings</div>
                    <div class="rating-stars" onclick="setRating(0)">
                        <span>All Ratings</span>
                    </div>
                    <div class="rating-stars" onclick="setRating(4)">
                        <span class="stars">★★★★☆</span>
                        <span class="rating-count">4★ & up</span>
                    </div>
                    <div class="rating-stars" onclick="setRating(3)">
                        <span class="stars">★★★☆☆</span>
                        <span class="rating-count">3★ & up</span>
                    </div>
                </div>

                <div class="filter-group">
                    <a class="filter-option" id="stock-filter" onclick="toggleInStock()">✓ In Stock Only</a>
                    <button class="btn btn-secondary" style="width: 100%; margin-top: 12px;" onclick="clearFilters()">Clear Filters</button>
                </div>
            </aside>

            <!-- MAIN CONTENT -->
            <div class="content">
                <div class="results-header">
                    <div class="results-summary" id="results-summary">Showing products</div>
                    <div class="sort-section">
                        <label>Sort by:</label>
                        <select class="sort-select" id="sort-select" onchange="applySortFilter()">
                            <option value="best">Featured</option>
                            <option value="price_asc">Price: Low to High</option>
                            <option value="price_desc">Price: High to Low</option>
                            <option value="rating_desc">Avg. Customer Review</option>
                            <option value="newest">Newest Arrivals</option>
                        </select>
                    </div>
                </div>

                <div id="message-container"></div>
                <div class="products-grid" id="products-container"></div>
            </div>
        </div>
    </div>

    <!-- CART MODAL -->
    <div id="cart-modal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal('cart-modal')">×</button>
            <h2>🛒 Shopping Cart</h2>
            <div id="cart-container" style="margin-top: 20px;"></div>
        </div>
    </div>

    <!-- WISHLIST MODAL -->
    <div id="wishlist-modal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal('wishlist-modal')">×</button>
            <h2>❤️ My Wishlist</h2>
            <div id="wishlist-container" style="margin-top: 20px;"></div>
        </div>
    </div>

    <!-- CHECKOUT MODAL -->
    <div id="checkout-modal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal('checkout-modal')">×</button>
            <h2>💳 Secure Checkout</h2>
            <form id="checkout-form" onsubmit="submitCheckout(event)" style="margin-top: 20px;">
                <div class="form-group">
                    <label>Full Name</label>
                    <input type="text" name="card_holder" required />
                </div>
                <div class="form-group">
                    <label>Card Number</label>
                    <input type="text" name="card_number" placeholder="1234 5678 9012 3456" required />
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div class="form-group">
                        <label>Expiry (MM/YY)</label>
                        <input type="text" name="expiry" placeholder="MM/YY" required />
                    </div>
                    <div class="form-group">
                        <label>CVV</label>
                        <input type="text" name="cvv" placeholder="123" required />
                    </div>
                </div>
                <div class="form-group">
                    <label>Billing ZIP Code</label>
                    <input type="text" name="billing_zip" required />
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px; margin-top: 12px;">Complete Purchase</button>
            </form>
        </div>
    </div>

    <script>
        const filters = {
            search: "",
            category: null,
            price_range: "all",
            rating: 0,
            in_stock: false,
            sort: "best"
        };

        let allProducts = [];
        let wishlistItems = new Set();

        async function loadProducts() {
            const params = new URLSearchParams({
                category: filters.category || '',
                search: filters.search,
                price_range: filters.price_range,
                rating: filters.rating,
                in_stock: filters.in_stock ? '1' : '0',
                sort: filters.sort
            });

            const response = await fetch(`/api/products?${params}`);
            const data = await response.json();
            allProducts = data.products;
            renderProducts(allProducts);
            updateResultsSummary();
        }

        function renderProducts(products) {
            const container = document.getElementById('products-container');
            if (products.length === 0) {
                container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #666;">No products found. Try adjusting your filters.</div>';
                return;
            }

            container.innerHTML = products.map(p => `
                <div class="product-card">
                    <button class="wishlist-btn ${wishlistItems.has(p.id) ? 'active' : ''}" onclick="toggleWishlist(${p.id}, event)">
                        <i class="fas fa-heart"></i>
                    </button>
                    <div class="product-image" style="background-image: url('${p.image_url}');"></div>
                    <div class="product-name">${p.name}</div>
                    <div class="product-rating">
                        <span class="stars">${'★'.repeat(Math.round(p.rating))}${'☆'.repeat(5-Math.round(p.rating))}</span>
                        <span class="rating-count">(${Math.round(p.rating * 10)})</span>
                    </div>
                    <div class="product-price">₹${p.price.toLocaleString('en-IN')}</div>
                    <div style="font-size: 12px; color: #666; margin-bottom: 8px;">
                        ${p.stock > 0 ? `<span style="color: #28a745;">✓ In Stock (${p.stock})</span>` : '<span style="color: #dc3545;">Out of Stock</span>'}
                    </div>
                    <div class="product-actions">
                        <button class="btn btn-primary" onclick="quickAddToCart(${p.id})">Add to Cart</button>
                        <button class="btn btn-secondary" onclick="viewProduct(${p.id})">Details</button>
                    </div>
                </div>
            `).join('');
        }

        function updateResultsSummary() {
            const summary = document.getElementById('results-summary');
            summary.textContent = `Showing ${allProducts.length} product${allProducts.length !== 1 ? 's' : ''}`;
        }

        async function loadCategories() {
            const response = await fetch('/api/categories');
            const data = await response.json();
            const categories = data.categories.filter(c => c);

            const sidebarContainer = document.getElementById('categories-sidebar');
            const headerContainer = document.getElementById('categories-header');

            sidebarContainer.innerHTML = categories.map(cat => `
                <a class="filter-option" onclick="filterCategory('${cat}')">${cat}</a>
            `).join('');

            headerContainer.innerHTML = categories.slice(0, 5).map(cat => `
                <span class="category-link" onclick="filterCategory('${cat}')">${cat}</span>
            `).join(' | ');

            const searchSelect = document.getElementById('search-category');
            categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat;
                option.textContent = cat;
                searchSelect.appendChild(option);
            });
        }

        function filterCategory(category) {
            filters.category = category;
            document.querySelectorAll('.filter-option').forEach(opt => opt.classList.remove('active'));
            if (!category) {
                document.querySelector('.filter-option').classList.add('active');
            } else {
                document.querySelectorAll('.filter-option').forEach(opt => {
                    if (opt.textContent.includes(category)) opt.classList.add('active');
                });
            }
            loadProducts();
        }

        function setPriceRange(range) {
            filters.price_range = range;
            loadProducts();
        }

        function setRating(rating) {
            filters.rating = rating;
            loadProducts();
        }

        function toggleInStock() {
            filters.in_stock = !filters.in_stock;
            document.getElementById('stock-filter').classList.toggle('active', filters.in_stock);
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
            filters.search = "";
            filters.category = null;
            filters.price_range = "all";
            filters.rating = 0;
            filters.in_stock = false;
            filters.sort = "best";
            document.getElementById('search-input').value = '';
            document.getElementById('sort-select').value = 'best';
            loadProducts();
        }

        async function quickAddToCart(productId) {
            const response = await fetch('/api/add-to-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: productId, quantity: 1})
            });
            const data = await response.json();
            showMessage(data.message, data.success ? 'success' : 'error');
            updateCartCount();
        }

        function toggleWishlist(productId, event) {
            event.preventDefault();
            event.stopPropagation();
            if (wishlistItems.has(productId)) {
                wishlistItems.delete(productId);
            } else {
                wishlistItems.add(productId);
            }
            event.currentTarget.classList.toggle('active');
        }

        function viewProduct(productId) {
            window.location.href = `/product/${productId}`;
        }

        async function updateCartCount() {
            const response = await fetch('/api/cart-count');
            const data = await response.json();
            document.getElementById('cart-count').textContent = data.count;
        }

        async function openCart() {
            const response = await fetch('/api/cart');
            const data = await response.json();
            const container = document.getElementById('cart-container');

            if (data.items.length === 0) {
                container.innerHTML = '<p style="color: #666;">Your cart is empty</p>';
            } else {
                container.innerHTML = data.items.map(item => `
                    <div class="cart-item">
                        <div class="cart-item-image" style="background-image: url('${item.product.image_url}');"></div>
                        <div class="cart-item-details">
                            <div class="cart-item-name">${item.product.name}</div>
                            <div class="cart-item-price">₹${item.product.price.toLocaleString('en-IN')} × ${item.quantity}</div>
                            <div class="quantity-selector">
                                <button class="qty-btn" onclick="updateQuantity(${item.product.id}, ${item.quantity - 1})">−</button>
                                <span>${item.quantity}</span>
                                <button class="qty-btn" onclick="updateQuantity(${item.product.id}, ${item.quantity + 1})">+</button>
                                <button class="qty-btn" style="margin-left: auto; color: #dc3545;" onclick="removeFromCart(${item.product.id})">✕</button>
                            </div>
                        </div>
                        <div style="font-weight: bold;">₹${item.subtotal.toLocaleString('en-IN')}</div>
                    </div>
                `).join('');

                container.innerHTML += `
                    <div class="cart-summary">
                        <div class="summary-line">
                            <span>Subtotal:</span>
                            <span>₹${data.summary.subtotal.toLocaleString('en-IN')}</span>
                        </div>
                        <div class="summary-line">
                            <span>Tax (${data.summary.tax_percent}%):</span>
                            <span>₹${data.summary.tax.toLocaleString('en-IN')}</span>
                        </div>
                        <div class="summary-line">
                            <span>Shipping:</span>
                            <span>${data.summary.shipping === 0 ? 'FREE' : '₹' + data.summary.shipping.toLocaleString('en-IN')}</span>
                        </div>
                        <div class="summary-line total">
                            <span>Total:</span>
                            <span>₹${data.summary.total.toLocaleString('en-IN')}</span>
                        </div>
                        <button class="btn btn-primary" style="width: 100%; margin-top: 16px; padding: 12px;" onclick="openCheckout()">Proceed to Checkout</button>
                    </div>
                `;
            }

            document.getElementById('cart-modal').classList.add('active');
        }

        function openWishlist() {
            const container = document.getElementById('wishlist-container');
            const wishlistProducts = allProducts.filter(p => wishlistItems.has(p.id));

            if (wishlistProducts.length === 0) {
                container.innerHTML = '<p style="color: #666;">Your wishlist is empty</p>';
            } else {
                container.innerHTML = wishlistProducts.map(p => `
                    <div class="cart-item">
                        <div class="cart-item-image" style="background-image: url('${p.image_url}');"></div>
                        <div class="cart-item-details">
                            <div class="cart-item-name">${p.name}</div>
                            <div class="product-rating">
                                <span class="stars">${'★'.repeat(Math.round(p.rating))}${'☆'.repeat(5-Math.round(p.rating))}</span>
                            </div>
                            <div class="cart-item-price">₹${p.price.toLocaleString('en-IN')}</div>
                            <button class="btn btn-primary" style="margin-top: 8px;" onclick="quickAddToCart(${p.id}); openCart();">Add to Cart</button>
                        </div>
                    </div>
                `).join('');
            }

            document.getElementById('wishlist-modal').classList.add('active');
        }

        function openCheckout() {
            document.getElementById('cart-modal').classList.remove('active');
            document.getElementById('checkout-modal').classList.add('active');
        }

        async function submitCheckout(event) {
            event.preventDefault();
            const formData = new FormData(document.getElementById('checkout-form'));
            const response = await fetch('/api/checkout', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                alert(`✓ Order placed! Transaction ID: ${data.transaction_id}`);
                closeModal('checkout-modal');
                loadProducts();
                updateCartCount();
            } else {
                alert(`✕ ${data.message}`);
            }
        }

        async function removeFromCart(productId) {
            await fetch('/api/remove-from-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: productId})
            });
            updateCartCount();
            openCart();
        }

        async function updateQuantity(productId, newQty) {
            if (newQty <= 0) {
                await removeFromCart(productId);
            } else {
                await fetch('/api/update-cart', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({product_id: productId, quantity: newQty})
                });
                updateCartCount();
                openCart();
            }
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

# ── Flask API Routes ──────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    p = get_product_by_id(product_id)
    if not p:
        return render_template_string("<h1>Product not found</h1><p><a href='/'>Back to store</a></p>"), 404
    
    detail_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{p.name} - PyStore</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            .header {{ margin-bottom: 20px; }}
            .header a {{ color: #FF9900; text-decoration: none; font-weight: bold; }}
            .content {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; background: white; padding: 30px; border-radius: 8px; }}
            .product-image {{ width: 100%; height: 400px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 120px; }}
            .product-info h1 {{ margin-top: 0; }}
            .rating {{ color: #FF9900; margin: 10px 0; }}
            .price {{ font-size: 28px; font-weight: bold; color: #333; margin: 20px 0; }}
            .btn {{ padding: 12px 20px; background: #FF9900; color: #333; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; margin-right: 10px; margin-top: 20px; }}
            .btn:hover {{ background: #c67700; }}
            @media (max-width: 768px) {{ .content {{ grid-template-columns: 1fr; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <a href="/">← Back to Store</a>
            </div>
            <div class="content">
                <div class="product-image"></div>
                <div class="product-info">
                    <h1>{p.name}</h1>
                    <div style="color: #666; margin-bottom: 10px;">Category: <strong>{p.category}</strong></div>
                    <div class="rating">★★★★★ {p.rating}/5 Rating</div>
                    <div class="price">₹{p.price:,.2f}</div>
                    <div style="margin: 15px 0; color: #666; line-height: 1.6;">{p.description}</div>
                    <div style="margin: 15px 0;">
                        <strong>Stock:</strong> {p.stock} units available
                    </div>
                    <div style="margin: 15px 0;">
                        <input type="number" id="qty" min="1" max="{p.stock}" value="1" style="padding: 8px; width: 80px;">
                    </div>
                    <button class="btn" onclick="addToCart({p.id})">🛒 Add to Cart</button>
                    <button class="btn" style="background: white; border: 2px solid #FF9900; color: #FF9900;" onclick="alert('Added to Wishlist!')">❤️ Add to Wishlist</button>
                </div>
            </div>
        </div>
        <script>
            function addToCart(productId) {{
                const qty = parseInt(document.getElementById('qty').value, 10) || 1;
                fetch('/api/add-to-cart', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{product_id: productId, quantity: qty}})
                }})
                .then(r => r.json())
                .then(data => {{
                    alert(data.message);
                    if (data.success) window.location.href = '/';
                }});
            }}
        </script>
    </body>
    </html>
    """
    return detail_html

@app.route('/api/products')
def api_products():
    category = request.args.get('category', '').strip()
    search_term = request.args.get('search', '').strip()
    price_range = request.args.get('price_range', 'all')
    rating = request.args.get('rating', '0')
    in_stock = request.args.get('in_stock', '0')
    sort = request.args.get('sort', 'best')

    products = get_all_products()

    if category:
        products = [p for p in products if p.category == category]

    if search_term:
        search_results = search_products(search_term)
        products = [p for p in products if p in search_results]

    # Price filtering
    if price_range == 'under_1000':
        products = [p for p in products if p.price < 1000]
    elif price_range == '1000_4999':
        products = [p for p in products if 1000 <= p.price <= 4999]
    elif price_range == '5000_14999':
        products = [p for p in products if 5000 <= p.price <= 14999]
    elif price_range == '15000_plus':
        products = [p for p in products if p.price >= 15000]

    # Rating filtering
    try:
        min_rating = float(rating)
        if min_rating > 0:
            products = [p for p in products if p.rating >= min_rating]
    except ValueError:
        pass

    # Stock filtering
    if in_stock == '1':
        products = [p for p in products if p.stock > 0]

    # Sorting
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
         "image_url": p.image_url or "https://via.placeholder.com/200"}
        for p in products
    ]})

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

@app.route('/api/update-cart', methods=['POST'])
def api_update_cart():
    data = request.json
    cart = get_cart()
    msg = cart.update_quantity(data['product_id'], data.get('quantity', 1))
    return jsonify({"success": True, "message": msg})

@app.route('/api/cart')
def api_cart():
    cart = get_cart()
    items = [
        {"product": {"id": item.product.id, "name": item.product.name,
                      "price": item.product.price, "image_url": item.product.image_url or "https://via.placeholder.com/80"},
         "quantity": item.quantity, "subtotal": item.subtotal}
        for item in cart.items()
    ]
    summary = cart.summary()
    return jsonify({"items": items, "summary": summary})

@app.route('/api/cart-count')
def api_cart_count():
    cart = get_cart()
    return jsonify({"count": sum(item.quantity for item in cart.items())})

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    cart = get_cart()
    if not cart.items():
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


if __name__ == '__main__':
    port = 5006
    url = f'http://localhost:{port}/'
    
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open(url)
    
    thread = threading.Thread(target=open_browser, daemon=True)
    thread.start()
    
    print(f"\n🚀 PyStore running at {url}")
    print(f"💻 Press Ctrl+C to stop\n")
    
    app.run(debug=True, port=port, use_reloader=False)
