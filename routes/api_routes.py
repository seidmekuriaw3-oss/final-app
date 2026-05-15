"""
API Routes for Ethiosadat Furniture

This module contains all API endpoints for AJAX requests including:
- Product search and filtering
- Cart operations (add, remove, update)
- User authentication (login, register)
- Order placement
- Contact form submission
- Branch information
"""

from flask import Blueprint, request, jsonify, session
from database.db import get_db
from database.models import Product, Order
import json
import re

api_bp = Blueprint('api', __name__)


# ==================== PRODUCT API ====================

@api_bp.route('/products/search')
def api_search_products():
    """Search products by query"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'success': True, 'products': [], 'count': 0})
    
    db = get_db()
    cursor = db.cursor()
    
    search_term = f'%{query}%'
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE (p.name LIKE ? OR p.name_am LIKE ? OR p.name_ar LIKE ?)
        AND p.is_active = 1
        ORDER BY p.id DESC
        LIMIT 50
    """, (search_term, search_term, search_term))
    
    products = cursor.fetchall()
    
    # Convert to list of dicts
    product_list = []
    for p in products:
        product_list.append({
            'id': p['id'],
            'name': p['name'],
            'name_am': p['name_am'],
            'name_ar': p['name_ar'],
            'price': p['price'],
            'compare_price': p['compare_price'],
            'thumbnail': p['thumbnail'],
            'stock_quantity': p['stock_quantity'],
            'category_name': p['category_name']
        })
    
    return jsonify({
        'success': True,
        'products': product_list,
        'count': len(product_list),
        'query': query
    })


@api_bp.route('/products/filter')
@api_bp.route('/search-products')
def api_filter_products():
    """Filter products by category, price range, etc."""
    category_id = request.args.get('category_id', type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort_by', 'newest')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    db = get_db()
    cursor = db.cursor()
    
    # Build query
    query = """
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
    """
    params = []
    
    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)
    
    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)
    
    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)
    
    # Add sorting
    if sort_by == 'price_asc':
        query += " ORDER BY p.price ASC"
    elif sort_by == 'price_desc':
        query += " ORDER BY p.price DESC"
    elif sort_by == 'name_asc':
        query += " ORDER BY p.name ASC"
    elif sort_by == 'oldest':
        query += " ORDER BY p.id ASC"
    else:  # newest
        query += " ORDER BY p.id DESC"
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    # Get total count
    count_query = """
        SELECT COUNT(*) as total
        FROM products p
        WHERE p.is_active = 1
    """
    count_params = []
    
    if category_id:
        count_query += " AND p.category_id = ?"
        count_params.append(category_id)
    
    if min_price is not None:
        count_query += " AND p.price >= ?"
        count_params.append(min_price)
    
    if max_price is not None:
        count_query += " AND p.price <= ?"
        count_params.append(max_price)
    
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()['total']
    
    # Convert products to list
    product_list = []
    for p in products:
        # Get discount percentage if compare_price exists
        discount = None
        if p['compare_price'] and p['compare_price'] > p['price']:
            discount = int(((p['compare_price'] - p['price']) / p['compare_price']) * 100)
        
        product_list.append({
            'id': p['id'],
            'name': p['name'],
            'name_am': p['name_am'],
            'name_ar': p['name_ar'],
            'price': p['price'],
            'compare_price': p['compare_price'],
            'discount': discount,
            'thumbnail': p['thumbnail'],
            'stock_quantity': p['stock_quantity'],
            'category_id': p['category_id'],
            'category_name': p['category_name'],
            'is_featured': bool(p['is_featured']),
            'is_new': bool(p['is_new'])
        })
    
    return jsonify({
        'success': True,
        'products': product_list,
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + limit < total
    })


@api_bp.route('/products/<int:pid>')
def api_get_product(pid):
    """Get single product details"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT p.*, c.name as category_name, c.name_am as category_name_am
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ? AND p.is_active = 1
    """, (pid,))
    
    product = cursor.fetchone()
    
    if not product:
        return jsonify({'success': False, 'error': 'Product not found'}), 404
    
    # Get discount percentage
    discount = None
    if product['compare_price'] and product['compare_price'] > product['price']:
        discount = int(((product['compare_price'] - product['price']) / product['compare_price']) * 100)
    
    # Parse images if stored as JSON
    images = []
    if product['images']:
        try:
            images = json.loads(product['images'])
        except:
            images = [product['thumbnail']] if product['thumbnail'] else []
    
    return jsonify({
        'success': True,
        'product': {
            'id': product['id'],
            'name': product['name'],
            'name_am': product['name_am'],
            'name_ar': product['name_ar'],
            'description': product['description'],
            'description_am': product['description_am'],
            'description_ar': product['description_ar'],
            'price': product['price'],
            'compare_price': product['compare_price'],
            'discount': discount,
            'thumbnail': product['thumbnail'],
            'images': images,
            'stock_quantity': product['stock_quantity'],
            'category_id': product['category_id'],
            'category_name': product['category_name'],
            'material': product['material'],
            'color': product['color'],
            'sku': product['sku'],
            'is_featured': bool(product['is_featured']),
            'is_new': bool(product['is_new'])
        }
    })


# ==================== CART API ====================

@api_bp.route('/cart/add', methods=['GET', 'POST'])
def api_cart_add():
    """Add product to cart"""
    if request.method == 'GET':
        product_id = request.args.get('product_id')
        quantity = int(request.args.get('quantity', 1))
    else:
        data = request.get_json(silent=True) or {}
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
    
    if not product_id:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400
    
    product_id = int(product_id)
    quantity = int(quantity)
    
    if not product_id:
        return jsonify({'success': False, 'error': 'Product ID required'}), 400
    
    # Check if user is logged in
    if session.get('user_id'):
        # Save to database
        db = get_db()
        cursor = db.cursor()
        
        # Check if product already in cart
        cursor.execute("""
            SELECT id, quantity FROM cart_items 
            WHERE user_id = ? AND product_id = ?
        """, (session['user_id'], product_id))
        
        existing = cursor.fetchone()
        
        if existing:
            new_quantity = existing['quantity'] + quantity
            cursor.execute("""
                UPDATE cart_items SET quantity = ? WHERE id = ?
            """, (new_quantity, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO cart_items (user_id, product_id, quantity)
                VALUES (?, ?, ?)
            """, (session['user_id'], product_id, quantity))
        
        db.commit()
    else:
        # Save to session cart
        cart = session.get('cart', {})
        cart_key = str(product_id)
        
        if cart_key in cart:
            cart[cart_key] += quantity
        else:
            cart[cart_key] = quantity
        
        session['cart'] = cart
        session.modified = True
    
    return jsonify({'success': True, 'message': 'Product added to cart'})


@api_bp.route('/cart/remove', methods=['GET', 'POST'])
def api_cart_remove():
    """Remove product from cart"""
    if request.method == 'GET':
        product_id = request.args.get('product_id')
    else:
        data = request.get_json(silent=True) or {}
        product_id = data.get('product_id')
    if product_id:
        product_id = int(product_id)
    
    if not product_id:
        return jsonify({'success': False, 'error': 'Product ID required'}), 400
    
    if session.get('user_id'):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            DELETE FROM cart_items WHERE user_id = ? AND product_id = ?
        """, (session['user_id'], product_id))
        db.commit()
    else:
        cart = session.get('cart', {})
        cart_key = str(product_id)
        if cart_key in cart:
            del cart[cart_key]
        session['cart'] = cart
        session.modified = True
    
    return jsonify({'success': True, 'message': 'Product removed from cart'})


@api_bp.route('/cart/update', methods=['GET', 'POST'])
def api_cart_update():
    """Update product quantity in cart"""
    if request.method == 'GET':
        product_id = request.args.get('product_id')
        quantity = int(request.args.get('quantity', 1))
    else:
        data = request.get_json(silent=True) or {}
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
    if product_id:
        product_id = int(product_id)
    quantity = int(quantity)
    
    if not product_id:
        return jsonify({'success': False, 'error': 'Product ID required'}), 400
    
    if quantity <= 0:
        return api_cart_remove()
    
    if session.get('user_id'):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE cart_items SET quantity = ? 
            WHERE user_id = ? AND product_id = ?
        """, (quantity, session['user_id'], product_id))
        db.commit()
    else:
        cart = session.get('cart', {})
        cart_key = str(product_id)
        cart[cart_key] = quantity
        session['cart'] = cart
        session.modified = True
    
    return jsonify({'success': True, 'message': 'Cart updated'})


@api_bp.route('/cart')
def api_get_cart():
    """Get current cart contents"""
    cart_items = []
    subtotal = 0
    
    if session.get('user_id'):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT ci.*, p.name, p.name_am, p.name_ar, p.price, p.compare_price, p.thumbnail
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = ?
        """, (session['user_id'],))
        
        rows = cursor.fetchall()
        for row in rows:
            item_subtotal = row['price'] * row['quantity']
            subtotal += item_subtotal
            cart_items.append({
                'id': row['id'],
                'product_id': row['product_id'],
                'name': row['name'],
                'name_am': row['name_am'],
                'name_ar': row['name_ar'],
                'price': row['price'],
                'quantity': row['quantity'],
                'thumbnail': row['thumbnail'],
                'subtotal': item_subtotal
            })
    else:
        cart = session.get('cart', {})
        if cart:
            db = get_db()
            cursor = db.cursor()
            placeholders = ','.join(['?'] * len(cart))
            cursor.execute(f"""
                SELECT id, name, name_am, name_ar, price, compare_price, thumbnail
                FROM products WHERE id IN ({placeholders})
            """, list(cart.keys()))
            
            products = cursor.fetchall()
            for p in products:
                quantity = cart.get(str(p['id']), 0)
                if quantity > 0:
                    item_subtotal = p['price'] * quantity
                    subtotal += item_subtotal
                    cart_items.append({
                        'product_id': p['id'],
                        'name': p['name'],
                        'name_am': p['name_am'],
                        'name_ar': p['name_ar'],
                        'price': p['price'],
                        'quantity': quantity,
                        'thumbnail': p['thumbnail'],
                        'subtotal': item_subtotal
                    })
    
    # Calculate shipping
    free_shipping_threshold = 5000
    shipping_cost = 0 if subtotal >= free_shipping_threshold else 200
    total = subtotal + shipping_cost
    
    # Apply 10% discount for logged in users
    discount = 0
    if session.get('user_id'):
        discount = subtotal * 0.1
        total = subtotal - discount + shipping_cost
    
    return jsonify({
        'success': True,
        'items': cart_items,
        'item_count': len(cart_items),
        'subtotal': round(subtotal, 2),
        'discount': round(discount, 2),
        'shipping_cost': shipping_cost,
        'total': round(total, 2),
        'free_shipping_threshold': free_shipping_threshold
    })


@api_bp.route('/cart/count')
def api_cart_count():
    """Get cart item count"""
    count = 0
    
    if session.get('user_id'):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT SUM(quantity) as total FROM cart_items WHERE user_id = ?", (session['user_id'],))
        result = cursor.fetchone()
        count = result['total'] or 0
    else:
        cart = session.get('cart', {})
        count = sum(cart.values())
    
    return jsonify({'success': True, 'count': count})


# ==================== USER AUTH API ====================

@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    """Register new user"""
    data = request.get_json()
    
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    
    # Validation
    if not full_name or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'success': False, 'error': 'Invalid email address'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if email exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        return jsonify({'success': False, 'error': 'Email already registered'}), 400
    
    # Create user
    from werkzeug.security import generate_password_hash
    import random as _random
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    base_username = email.split('@')[0].lower()
    username = base_username
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        username = base_username + str(_random.randint(100, 9999))

    cursor.execute("""
        INSERT INTO users (username, full_name, email, phone, password_hash, is_admin, is_active)
        VALUES (?, ?, ?, ?, ?, 0, 1) RETURNING id
    """, (username, full_name, email, phone, password_hash))
    row = cursor.fetchone()
    db.commit()
    user_id = row[0] if row else None
    
    # Auto login after registration
    session['user_id'] = user_id
    session['user_name'] = full_name
    session['user_email'] = email
    session['user_phone'] = phone
    
    return jsonify({
        'success': True,
        'message': 'Registration successful!',
        'user': {
            'id': user_id,
            'name': full_name,
            'email': email
        }
    })


@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """Login user"""
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
    user = cursor.fetchone()
    
    if not user:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    
    from werkzeug.security import check_password_hash
    if not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    
    # Set session
    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    session['user_email'] = user['email']
    session['user_phone'] = user['phone']
    
    # Merge guest cart with user cart
    guest_cart = session.get('cart', {})
    if guest_cart:
        for product_id, quantity in guest_cart.items():
            cursor.execute("SELECT id, quantity FROM cart_items WHERE user_id = ? AND product_id = ?", 
                          (user['id'], product_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE cart_items SET quantity = quantity + ? WHERE id = ?",
                             (quantity, existing['id']))
            else:
                cursor.execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                             (user['id'], product_id, quantity))
        db.commit()
        session.pop('cart', None)
    
    return jsonify({
        'success': True,
        'message': 'Login successful!',
        'user': {
            'id': user['id'],
            'name': user['full_name'],
            'email': user['email']
        }
    })


@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """Logout user"""
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    session.pop('user_phone', None)
    
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@api_bp.route('/auth/check')
def api_check_auth():
    """Check if user is authenticated"""
    if session.get('user_id'):
        return jsonify({
            'success': True,
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'name': session.get('user_name'),
                'email': session.get('user_email')
            }
        })
    else:
        return jsonify({
            'success': True,
            'authenticated': False,
            'user': None
        })


# ==================== ORDER API ====================

@api_bp.route('/order/place', methods=['POST'])
def api_place_order():
    """Place a new order"""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Please login to place order'}), 401
    
    data = request.get_json()
    
    # Get cart items
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT ci.*, p.price, p.name
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.user_id = ?
    """, (session['user_id'],))
    
    cart_items = cursor.fetchall()
    
    if not cart_items:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400
    
    # Calculate totals
    subtotal = 0
    items_list = []
    for item in cart_items:
        item_subtotal = item['price'] * item['quantity']
        subtotal += item_subtotal
        items_list.append({
            'product_id': item['product_id'],
            'quantity': item['quantity'],
            'price': item['price']
        })
    
    # Apply 10% discount
    discount = subtotal * 0.1
    shipping_cost = 200 if subtotal < 5000 else 0
    total = subtotal - discount + shipping_cost
    
    # Generate order number
    from datetime import datetime
    import random
    import string
    order_number = f"{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    
    # Create order
    cursor.execute("""
        INSERT INTO orders (
            order_number, user_id, status, payment_status,
            subtotal, discount, shipping_fee, total,
            shipping_address, shipping_city, shipping_phone, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
    """, (
        order_number, session['user_id'], 'pending', 'pending',
        subtotal, discount, shipping_cost, total,
        data.get('shipping_address', ''),
        data.get('shipping_city', ''),
        data.get('shipping_phone', session.get('user_phone', '')),
        data.get('notes', '')
    ))
    row = cursor.fetchone()
    order_id = row[0] if row else None
    
    # Create order items
    for item in items_list:
        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, quantity, price_at_time)
            VALUES (?, ?, ?, ?)
        """, (order_id, item['product_id'], item['quantity'], item['price']))
        
        # Update product stock
        cursor.execute("""
            UPDATE products SET stock_quantity = stock_quantity - ?, sales_count = sales_count + ?
            WHERE id = ?
        """, (item['quantity'], item['quantity'], item['product_id']))
    
    # Clear cart
    cursor.execute("DELETE FROM cart_items WHERE user_id = ?", (session['user_id'],))
    
    db.commit()
    
    return jsonify({
        'success': True,
        'message': 'Order placed successfully!',
        'order_id': order_id,
        'order_number': order_number,
        'total': total
    })


# ==================== CONTACT API ====================

@api_bp.route('/contact', methods=['POST'])
def api_contact():
    """Submit contact form"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    message = data.get('message', '').strip()
    
    if not name or not email or not message:
        return jsonify({'success': False, 'error': 'Name, email, and message are required'}), 400
    
    # Save to database or send email
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        INSERT INTO contacts (name, email, phone, message)
        VALUES (?, ?, ?, ?)
    """, (name, email, phone, message))
    
    db.commit()
    
    return jsonify({
        'success': True,
        'message': 'Message sent successfully! We will contact you soon.'
    })


# ==================== BRANCHES API ====================

@api_bp.route('/branches')
def api_get_branches():
    """Get all branches"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM branches 
        WHERE is_active = 1 
        ORDER BY sort_order ASC
    """)
    
    branches = cursor.fetchall()
    
    branch_list = []
    for b in branches:
        branch_list.append({
            'id': b['id'],
            'name': b['name'],
            'name_am': b['name_am'],
            'name_ar': b['name_ar'],
            'address': b['address'],
            'address_am': b['address_am'],
            'address_ar': b['address_ar'],
            'phone': b['phone'],
            'email': b['email'],
            'latitude': b['latitude'],
            'longitude': b['longitude'],
            'working_hours': b['working_hours'],
            'image': b['image'],
            'maps_url': f"https://www.google.com/maps/dir/?api=1&destination={b['latitude']},{b['longitude']}"
        })
    
    return jsonify({
        'success': True,
        'branches': branch_list,
        'count': len(branch_list)
    })


# ==================== SETTINGS API ====================

@api_bp.route('/settings')
def api_get_settings():
    """Get public settings"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM settings")
    
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    return jsonify({
        'success': True,
        'settings': {
            'site_name': settings.get('site_name', 'Ethiosadat Furniture'),
            'site_phone': settings.get('site_phone', '+251906020606'),
            'whatsapp_number': settings.get('whatsapp_number', '251906020606'),
            'free_shipping_threshold': float(settings.get('free_shipping_threshold', 5000)),
            'shipping_cost': float(settings.get('shipping_cost', 200)),
            'currency': settings.get('currency', 'ETB')
        }
    })


# ==================== CATEGORIES API ====================

@api_bp.route('/categories')
def api_categories():
    """Get all active categories with product counts."""
    try:
        db = get_db()
        db.row_factory = __import__('sqlite3').Row
        cursor = db.cursor()
        cursor.execute("""
            SELECT c.*, COUNT(p.id) as product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id AND p.is_active = 1
            WHERE c.is_active = 1
            GROUP BY c.id
            ORDER BY c.sort_order ASC
        """)
        categories = cursor.fetchall()
        return jsonify({
            'success': True,
            'categories': [dict(c) for c in categories] if categories else []
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WISHLIST API ====================

@api_bp.route('/wishlist/add', methods=['POST'])
def api_wishlist_add():
    """Add product to wishlist."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'error': 'Product ID required'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO wishlist (user_id, product_id)
            VALUES (?, ?)
            ON CONFLICT (user_id, product_id) DO NOTHING
        """, (session['user_id'], product_id))
        db.commit()
        return jsonify({'success': True, 'message': 'Added to wishlist'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/wishlist/remove', methods=['POST'])
def api_wishlist_remove():
    """Remove product from wishlist."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'error': 'Product ID required'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM wishlist WHERE user_id = ? AND product_id = ?",
                       (session['user_id'], product_id))
        db.commit()
        return jsonify({'success': True, 'message': 'Removed from wishlist'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COUPON API ====================

@api_bp.route('/apply-coupon', methods=['POST'])
def api_apply_coupon():
    """Apply discount coupon to cart."""
    try:
        data = request.get_json()
        code = data.get('code', '').strip().upper()
        if not code:
            return jsonify({'success': False, 'error': 'Coupon code required'}), 400

        db = get_db()
        db.row_factory = __import__('sqlite3').Row
        cursor = db.cursor()

        cursor.execute("""
            SELECT * FROM coupons
            WHERE code = ? AND is_active = 1
            AND (valid_from IS NULL OR valid_from <= CURRENT_TIMESTAMP)
            AND (valid_to IS NULL OR valid_to >= CURRENT_TIMESTAMP)
            AND (usage_limit IS NULL OR used_count < usage_limit)
        """, (code,))
        coupon = cursor.fetchone()

        if not coupon:
            return jsonify({'success': False, 'error': 'Invalid or expired coupon code'}), 400

        # Get cart subtotal
        subtotal = 0
        if session.get('user_id'):
            cursor.execute("""
                SELECT SUM(p.price * ci.quantity) as total
                FROM cart_items ci JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = ?
            """, (session['user_id'],))
            result = cursor.fetchone()
            subtotal = result['total'] or 0 if result else 0

        if subtotal < (coupon['min_order'] or 0):
            return jsonify({'success': False,
                            'error': f"Minimum order of {coupon['min_order']} ETB required"}), 400

        if coupon['discount_type'] == 'percentage':
            discount = subtotal * (coupon['discount_value'] / 100)
            if coupon['max_discount']:
                discount = min(discount, coupon['max_discount'])
        else:
            discount = coupon['discount_value']

        session['applied_coupon'] = {
            'code': code,
            'discount': discount,
            'coupon_id': coupon['id']
        }
        session.modified = True

        return jsonify({
            'success': True,
            'message': f'Coupon applied! You saved {discount:.2f} ETB',
            'discount': discount
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== REVIEWS API ====================

@api_bp.route('/product/<int:product_id>/reviews', methods=['GET', 'POST'])
def product_reviews(product_id):
    """Get or add product reviews."""
    if request.method == 'GET':
        try:
            db = get_db()
            db.row_factory = __import__('sqlite3').Row
            cursor = db.cursor()
            cursor.execute("""
                SELECT r.*, u.full_name as user_name
                FROM reviews r JOIN users u ON r.user_id = u.id
                WHERE r.product_id = ? AND r.is_approved = 1
                ORDER BY r.created_at DESC LIMIT 20
            """, (product_id,))
            reviews = cursor.fetchall()
            reviews_list = [dict(r) for r in reviews] if reviews else []
            avg_rating = (sum(r['rating'] for r in reviews_list) / len(reviews_list)
                          if reviews_list else 0)
            return jsonify({
                'success': True,
                'reviews': reviews_list,
                'average_rating': round(avg_rating, 1),
                'total_reviews': len(reviews_list)
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # POST - add review
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Please login to leave a review'}), 401
    try:
        data = request.get_json()
        rating = data.get('rating', 0)
        comment = data.get('comment', '').strip()

        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': 'Rating must be between 1 and 5'}), 400
        if not comment:
            return jsonify({'success': False, 'error': 'Please write a review'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM reviews WHERE product_id = ? AND user_id = ?",
                       (product_id, session['user_id']))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'You have already reviewed this product'}), 400

        cursor.execute("""
            INSERT INTO reviews (product_id, user_id, rating, comment, is_approved)
            VALUES (?, ?, ?, ?, 0)
        """, (product_id, session['user_id'], rating, comment))
        db.commit()
        return jsonify({'success': True, 'message': 'Review submitted! Awaiting approval.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== NEWSLETTER API ====================

@api_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    """Subscribe to newsletter."""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        if not re.match(r'^[^\s@]+@([^\s@.,]+\.)+[^\s@.,]{2,}$', email):
            return jsonify({'success': False, 'error': 'Invalid email address'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO newsletter (email) VALUES (?)
            ON CONFLICT (email) DO NOTHING
        """, (email,))
        db.commit()
        return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== TRANSLATION API ====================

@api_bp.route('/translate', methods=['POST'])
def api_translate():
    """Translate text to target language."""
    try:
        from utils.translation_cache import translate_text
        data = request.get_json()
        text = data.get('text', '').strip()
        target_lang = data.get('target_lang', 'en')
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        translated = translate_text(text, target_lang)
        return jsonify({'status': 'success', 'original': text,
                        'translated': translated, 'language': target_lang})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@api_bp.route('/translate-batch', methods=['POST'])
def api_translate_batch():
    """Translate multiple texts at once."""
    try:
        from utils.translation_cache import batch_translate
        data = request.get_json()
        texts = data.get('texts', [])
        target_lang = data.get('target_lang', 'en')
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'Texts array is required'}), 400
        translations = batch_translate(texts, target_lang)
        return jsonify({'status': 'success', 'translations': translations,
                        'language': target_lang, 'count': len(translations)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== PLATFORM API ====================

@api_bp.route('/platform')
def api_platform():
    """Get current platform information."""
    from middleware.platform import get_platform, is_android_app
    from flask import request as _req
    return jsonify({
        'success': True,
        'platform': get_platform(),
        'is_android_app': is_android_app(),
        'user_agent': _req.headers.get('User-Agent', '')
    })


# ==================== SUBMIT ORDER API ====================

@api_bp.route('/submit-order', methods=['POST'])
def api_submit_order():
    """Submit order via AJAX (quick-checkout modal)."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Please login to place order'}), 401
    try:
        data = request.get_json()
        customer_name = (data.get('customer_name') or '').strip()
        customer_phone = (data.get('customer_phone') or '').strip()
        shipping_address = (data.get('customer_address') or '').strip() or 'Not provided'
        customer_email = (data.get('customer_email') or '').strip() or None
        notes = (data.get('order_notes') or '').strip()

        if not customer_name or not customer_phone:
            return jsonify({'success': False, 'error': 'Name and phone number are required'}), 400

        db = get_db()
        db.row_factory = __import__('sqlite3').Row
        cursor = db.cursor()

        cursor.execute("""
            SELECT ci.product_id, ci.quantity, p.price, p.name, p.name_am
            FROM cart_items ci JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = %s
        """, (session['user_id'],))
        cart_items = cursor.fetchall()

        if not cart_items:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400

        from middleware.platform import is_android_app
        android_user = is_android_app()

        subtotal = 0
        items_list = []
        for item in cart_items:
            price = item['price'] or 0
            qty = item['quantity'] or 1
            unit_price = price * 0.9 if android_user else price
            subtotal += unit_price * qty
            items_list.append({
                'product_id': item['product_id'], 'quantity': qty,
                'price': unit_price, 'name': item['name'],
                'name_am': item['name_am'] or item['name'],
            })

        discount = subtotal * 0.1 if android_user else 0
        subtotal_after_discount = subtotal - discount
        threshold = int(os.environ.get('FREE_SHIPPING_THRESHOLD', '5000'))
        shipping_cost = 0 if subtotal_after_discount >= threshold else int(os.environ.get('SHIPPING_COST', '200'))
        total = subtotal_after_discount + shipping_cost

        import random, string
        from datetime import datetime as _dt
        order_number = f"{_dt.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

        cursor.execute("""
            INSERT INTO orders (
                order_number, user_id, status, payment_status,
                subtotal, discount, shipping_fee, total,
                shipping_address, shipping_phone, notes, customer_name, customer_email
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (order_number, session['user_id'], 'pending', 'pending',
              subtotal, discount, shipping_cost, total,
              shipping_address, customer_phone, notes, customer_name, customer_email))

        row = cursor.fetchone()
        order_id = row[0] if row else None

        for item in items_list:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price_at_time)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['product_id'], item['quantity'], item['price']))
            cursor.execute("""
                UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s
            """, (item['quantity'], item['product_id']))

        cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (session['user_id'],))
        db.commit()

        return jsonify({
            'success': True,
            'message': 'Order placed successfully!',
            'order_id': order_id,
            'order_number': order_number,
            'total': total,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/user/profile', methods=['GET'])
def api_get_user_profile():
    """Return current logged-in user profile data as JSON."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, full_name, email, phone, city, address FROM users WHERE id = ?",
            (session['user_id'],)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        uid = session['user_id']
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id = ?", (uid,))
        total_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? AND status = 'delivered'", (uid,))
        delivered_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? AND status NOT IN ('delivered','cancelled')", (uid,))
        pending_row = cursor.fetchone()

        return jsonify({
            'success': True,
            'user': {
                'full_name': row['full_name'] or '',
                'email':     row['email'] or '',
                'phone':     row['phone'] or '',
                'city':      row['city'] or '',
                'address':   row['address'] or '',
            },
            'order_stats': {
                'total':     total_row['cnt'] if total_row else 0,
                'delivered': delivered_row['cnt'] if delivered_row else 0,
                'pending':   pending_row['cnt'] if pending_row else 0,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
