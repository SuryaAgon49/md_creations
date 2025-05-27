from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = '99a0768fb15406f8b9cecea7c80138dd'  # Change this to a random secret key
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create admin table
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 email TEXT UNIQUE NOT NULL,
                 password TEXT NOT NULL,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL,
                 category TEXT NOT NULL,
                 price REAL NOT NULL,
                 description TEXT,
                 image_path TEXT,
                 video_path TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 product_id INTEGER,
                 customer_name TEXT NOT NULL,
                 customer_email TEXT NOT NULL,
                 customer_phone TEXT NOT NULL,
                 customer_address TEXT NOT NULL,
                 message TEXT,
                 order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 status TEXT DEFAULT 'pending',
                 FOREIGN KEY (product_id) REFERENCES products (id))''')
    
    # Create default admin if not exists
    c.execute("SELECT * FROM admin WHERE email = ?", ('admin@jewelryshop.com',))
    if not c.fetchone():
        hashed_password = generate_password_hash('admin123')
        c.execute("INSERT INTO admin (email, password) VALUES (?, ?)", 
                 ('admin@jewelryshop.com', hashed_password))
    
    conn.commit()
    conn.close()

# Helper function to get database connection
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Main store page
@app.route('/')
def index():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('index.html', products=products)

@app.route('/contact')
def contact():
    """Contact page route"""
    return render_template('contact.html')

# Product detail and order form
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    if not product:
        flash('Product not found!')
        return redirect(url_for('index'))
    return render_template('index.html', products=[product], show_order_form=True)

# Handle order submission
@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        product_id = request.form['product_id']
        customer_name = request.form['customer_name']
        customer_email = request.form['customer_email']
        customer_phone = request.form['customer_phone']
        customer_address = request.form['customer_address']
        message = request.form.get('message', '')
        
        conn = get_db()
        conn.execute('''INSERT INTO orders 
                       (product_id, customer_name, customer_email, customer_phone, 
                        customer_address, message) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (product_id, customer_name, customer_email, customer_phone, 
                     customer_address, message))
        conn.commit()
        conn.close()
        
        flash('Order placed successfully! We will contact you soon.')
        return redirect(url_for('index'))
    except Exception as e:
        flash('Error placing order. Please try again.')
        return redirect(url_for('index'))

# Admin login page
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        admin = conn.execute('SELECT * FROM admin WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['id']
            session['admin_email'] = admin['email']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials!')
    
    return render_template('login.html')

# Admin dashboard
@app.route('/admin')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    orders = conn.execute('''SELECT o.*, p.name as product_name, p.price 
                            FROM orders o 
                            JOIN products p ON o.product_id = p.id 
                            ORDER BY o.order_date DESC''').fetchall()
    conn.close()
    
    return render_template('admin.html', products=products, orders=orders)

# Add/Edit product
@app.route('/admin/product', methods=['POST'])
def manage_product():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    try:
        product_id = request.form.get('product_id')
        name = request.form['name']
        category = request.form['category']
        price = float(request.form['price'])
        description = request.form['description']
        
        # Handle file uploads
        image_path = None
        video_path = None
        
        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(f"{uuid.uuid4()}_{image.filename}")
                image_path = f"uploads/{filename}"
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        if 'video' in request.files and request.files['video'].filename:
            video = request.files['video']
            if video and allowed_file(video.filename):
                filename = secure_filename(f"{uuid.uuid4()}_{video.filename}")
                video_path = f"uploads/{filename}"
                video.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = get_db()
        
        if product_id:  # Edit existing product
            update_query = "UPDATE products SET name=?, category=?, price=?, description=?"
            params = [name, category, price, description]
            
            if image_path:
                update_query += ", image_path=?"
                params.append(image_path)
            if video_path:
                update_query += ", video_path=?"
                params.append(video_path)
            
            update_query += " WHERE id=?"
            params.append(product_id)
            
            conn.execute(update_query, params)
        else:  # Add new product
            conn.execute('''INSERT INTO products (name, category, price, description, image_path, video_path)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (name, category, price, description, image_path, video_path))
        
        conn.commit()
        conn.close()
        flash('Product saved successfully!')
        
    except Exception as e:
        flash(f'Error saving product: {str(e)}')
    
    return redirect(url_for('admin_dashboard'))

# Delete product
@app.route('/admin/product/delete/<int:product_id>')
def delete_product(product_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db()
        # Get file paths before deleting
        product = conn.execute('SELECT image_path, video_path FROM products WHERE id = ?', 
                             (product_id,)).fetchone()
        
        # Delete files
        if product:
            if product['image_path']:
                try:
                    os.remove(os.path.join('static', product['image_path']))
                except:
                    pass
            if product['video_path']:
                try:
                    os.remove(os.path.join('static', product['video_path']))
                except:
                    pass
        
        # Delete from database
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
        flash('Product deleted successfully!')
        
    except Exception as e:
        flash(f'Error deleting product: {str(e)}')
    
    return redirect(url_for('admin_dashboard'))

# Update order status
@app.route('/admin/order/update', methods=['POST'])
def update_order_status():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    try:
        order_id = request.form['order_id']
        status = request.form['status']
        
        conn = get_db()
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        conn.close()
        flash('Order status updated successfully!')
        
    except Exception as e:
        flash(f'Error updating order: {str(e)}')
    
    return redirect(url_for('admin_dashboard'))

# Admin logout
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# Helper function to check allowed file extensions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    init_db()
    app.run(debug=True)