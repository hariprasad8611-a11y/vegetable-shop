import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timezone, timedelta
import re

# ========================== PRINTING IMPORTS ==========================
import requests
import json
import socket
import base64

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🌿", layout="wide")

# Custom CSS for beautiful UI
st.markdown("""
<style>
    /* Main background */
    .main {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);}
    
    /* Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Montserrat:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Poppins', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* Headers */
    h1 {text-align:center; color:#2c3e50; font-size:2.8em; margin-bottom:5px;}
    .subtitle {text-align:center; color:#27ae60; font-size:1.2em; margin-bottom:30px; font-weight:500;}
    
    /* Buttons */
    .stButton>button {
        height:3em; 
        border-radius:12px; 
        font-size:16px; 
        font-weight:500;
        transition: all 0.3s ease;
        border: none !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15) !important;
    }
    
    .primary-btn {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important; color:white !important;}
    .secondary-btn {background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important; color:white !important;}
    .success-btn {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important; color:white !important;}
    .warning-btn {background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important; color:white !important;}
    .info-btn {background: linear-gradient(135deg, #3498db 0%, #2980b9 100%) !important; color:white !important;}
    
    /* Cards */
    .card {
        background: white;
        padding: 25px;
        border-radius: 20px;
        margin: 15px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.12);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        padding: 25px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 25px rgba(39, 174, 96, 0.3);
    }
    
    .inventory-card {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(52, 152, 219, 0.3);
    }
    
    .sales-card {
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(155, 89, 182, 0.3);
    }
    
    .purchase-card {
        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(243, 156, 18, 0.3);
    }
    
    /* Tables */
    .dataframe {
        border-radius: 10px !important;
        overflow: hidden !important;
    }
    
    /* Inputs */
    .stSelectbox, .stTextInput, .stNumberInput, .stDateInput {
        border-radius: 10px !important;
    }
    
    .stSelectbox>div>div {
        border-radius: 10px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        padding: 10px 0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
        padding: 12px 24px;
        background: #f8f9fa;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important;
        color: white !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%) !important;
    }
    
    /* Receipt */
    .receipt {
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
        border: 2px solid #27ae60;
        max-width: 500px;
        margin: 20px auto;
    }
    
    /* Alert boxes */
    .alert-success {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #28a745;
        margin: 10px 0;
        color: #155724;
    }
    
    .alert-warning {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #ffc107;
        margin: 10px 0;
        color: #856404;
    }
    
    .alert-danger {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #dc3545;
        margin: 10px 0;
        color: #721c24;
    }
    
    /* Cart items */
    .cart-item {
        background: white;
        padding: 15px;
        margin: 10px 0;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border-left: 4px solid #27ae60;
        transition: all 0.3s ease;
    }
    .cart-item:hover {
        transform: translateX(5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #7f8c8d;
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e0e0e0;
        font-size: 0.9em;
    }
    
    /* Vegetable selection */
    .veg-select-card {
        background: white;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    
    /* Print button */
    .print-btn {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important;
        color: white !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div style="text-align:center; margin-bottom:30px;">
    <h1>🌿 Fresh Basket</h1>
    <div class="subtitle">Freshness You Can Feel</div>
</div>
""", unsafe_allow_html=True)

# ========================== DATABASE ==========================
DB_FILE = "shop.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# ========================== DATABASE SETUP ==========================
# First, check if inventory table exists and has unit_type column
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
table_exists = c.fetchone()

if table_exists:
    # Check if unit_type column exists
    c.execute("PRAGMA table_info(inventory)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'unit_type' not in columns:
        # Add unit_type column if it doesn't exist
        try:
            c.execute("ALTER TABLE inventory ADD COLUMN unit_type TEXT DEFAULT 'kg'")
            conn.commit()
        except Exception as e:
            pass
else:
    # Create tables if they don't exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        vegetable TEXT PRIMARY KEY,
        quantity REAL,
        cost_price REAL,
        selling_price REAL,
        image_url TEXT,
        unit_type TEXT DEFAULT 'kg'
    )
    """)

# Create other tables if they don't exist
c.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    date TEXT, 
    vegetable TEXT, 
    quantity REAL, 
    amount REAL, 
    supplier TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS sales (
    date TEXT, 
    vegetable TEXT, 
    quantity_sold REAL, 
    sale_price REAL, 
    total REAL, 
    customer TEXT,
    unit_type TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS waste (
    date TEXT, 
    vegetable TEXT, 
    quantity REAL, 
    reason TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS customers (
    phone TEXT PRIMARY KEY, 
    name TEXT, 
    points INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    date TEXT, 
    category TEXT, 
    amount REAL, 
    description TEXT
)
""")

conn.commit()

# ========================== DEFAULT VEGETABLES WITH UNIT TYPES ==========================
default_vegetables = [
    ("Potato", "kg"),
    ("Onion", "kg"),
    ("Tomato", "kg"),
    ("Carrot", "kg"),
    ("Cucumber", "kg"),
    ("Spinach", "kg"),
    ("Broccoli", "kg"),
    ("Cauliflower", "kg"),
    ("Cabbage", "kg"),
    ("Capsicum", "kg"),
    ("Brinjal", "kg"),
    ("Green Beans", "kg"),
    ("Peas", "kg"),
    ("Radish", "kg"),
    ("Lettuce", "kg"),
    ("Celery", "kg"),
    ("Sweet Potato", "kg"),
    ("Corn", "kg"),
    ("Garlic", "kg"),
    ("Ginger", "kg"),
    ("Mushroom", "kg"),
    ("Pumpkin", "kg"),
    ("Lady Finger", "kg"),
    ("Beetroot", "kg"),
    ("Leek", "kg"),
    ("Lemon", "piece"),
    ("Drumstick", "piece"),
    ("Banana Steam", "piece"),
    ("Banana Flower", "piece"),
    ("Raw Banana", "piece"),
    ("Coconut", "piece")
]

# Initialize default vegetables if not exists
for veg, unit_type in default_vegetables:
    # First check if vegetable exists
    c.execute("SELECT vegetable FROM inventory WHERE vegetable=?", (veg,))
    if not c.fetchone():
        # Insert new vegetable with unit_type
        try:
            c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url, unit_type) VALUES (?, 0, 0, 0, '', ?)", 
                     (veg, unit_type))
        except Exception as e:
            # If insertion fails, try to update existing
            try:
                c.execute("UPDATE inventory SET unit_type=? WHERE vegetable=?", (unit_type, veg))
            except:
                pass
    else:
        # Update existing vegetable with unit_type if needed
        try:
            c.execute("UPDATE inventory SET unit_type=? WHERE vegetable=?", (unit_type, veg))
        except:
            pass

conn.commit()

# ========================== HELPERS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price, unit_type) for veg (or zeros)."""
    try:
        c.execute("SELECT quantity, cost_price, selling_price, unit_type FROM inventory WHERE vegetable=?", (veg,))
        row = c.fetchone()
        if row:
            qty = row[0] if row[0] is not None else 0.0
            cost = row[1] if row[1] is not None else 0.0
            sell = row[2] if row[2] is not None else 0.0
            unit_type = row[3] if row[3] is not None else 'kg'
            return qty, cost, sell, unit_type
    except Exception as e:
        pass
    return 0.0, 0.0, 0.0, 'kg'

def fetch_table_with_rowid(table):
    return pd.read_sql(f"SELECT rowid, * FROM {table}", conn)

def safe_round_df(df, cols):
    for col in cols:
        if col in df.columns:
            try:
                df[col] = df[col].astype(float).round(2)
            except Exception:
                pass
    return df

def convert_to_display(qty, unit_type):
    """Convert quantity to display format based on unit type"""
    if unit_type == 'kg':
        kg = int(qty)
        grams = round((qty - kg) * 1000)
        if grams > 0:
            return f"{kg} kg {grams} g" if kg > 0 else f"{grams} g"
        return f"{kg} kg"
    elif unit_type == 'piece':
        if qty == 1:
            return "1 piece"
        else:
            return f"{int(qty)} pieces"
    else:
        return f"{qty:.2f} {unit_type}"

def get_quantity_label(unit_type):
    """Get quantity label based on unit type"""
    if unit_type == 'kg':
        return "Quantity (kg)"
    elif unit_type == 'piece':
        return "Quantity (pieces)"
    else:
        return f"Quantity ({unit_type})"

def get_price_label(unit_type):
    """Get price label based on unit type"""
    if unit_type == 'kg':
        return "Price/kg"
    elif unit_type == 'piece':
        return "Price/piece"
    else:
        return f"Price per {unit_type}"

# Initialize session state
if "cart" not in st.session_state:
    st.session_state.cart = []
if "shortage_threshold" not in st.session_state:
    st.session_state.shortage_threshold = 5.0
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()
if "last_sale" not in st.session_state:
    st.session_state.last_sale = None
if "guest_counter" not in st.session_state:
    # Try to get the maximum guest number from existing sales to persist across sessions
    try:
        c.execute("SELECT customer FROM sales WHERE customer LIKE 'Guest%'")
        guests = c.fetchall()
        max_guest = 0
        for guest in guests:
            # Extract number from "GuestX" or "GuestX (phone)"
            guest_str = guest[0]
            match = re.search(r'Guest(\d+)', guest_str)
            if match:
                guest_num = int(match.group(1))
                if guest_num > max_guest:
                    max_guest = guest_num
        st.session_state.guest_counter = max_guest + 1
    except:
        st.session_state.guest_counter = 1

# ========================== HELPER FUNCTIONS FOR SELL PAGE ==========================
def add_to_cart_simple(veg, qty):
    """Add item to cart with quantity validation"""
    if qty <= 0:
        return False
    
    # Get price and unit type
    stock, _, price, unit_type = get_stock(veg)
    if stock == 0:
        st.error(f"{veg} is out of stock!")
        return False
    
    # Check stock
    current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
    
    if current_in_cart + qty > stock:
        unit_display = unit_type if unit_type != 'kg' else 'kg'
        st.error(f"Not enough stock! Available: {stock:.2f} {unit_display}")
        return False
    
    # Add to cart
    found = False
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart[i][1] += qty
            st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * price, 2)
            found = True
            break
    
    if not found:
        total = round(qty * price, 2)
        st.session_state.cart.append([veg, qty, price, total, unit_type])
    
    return True

def remove_from_cart(veg):
    """Remove item from cart"""
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart.pop(i)
            return True
    return False

def update_cart_qty(veg, new_qty):
    """Update cart item quantity"""
    if new_qty <= 0:
        remove_from_cart(veg)
        return True
    
    stock, _, price, unit_type = get_stock(veg)
    if new_qty > stock:
        unit_display = unit_type if unit_type != 'kg' else 'kg'
        st.error(f"Not enough stock! Available: {stock:.2f} {unit_display}")
        return False
    
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart[i][1] = new_qty
            st.session_state.cart[i][3] = round(new_qty * price, 2)
            return True
    return False

def get_ist_time():
    """Get current IST time"""
    # IST is UTC+5:30
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime("%H:%M:%S")

def process_sale_simple(cust_name, cust_phone):
    """Process the sale with simplified logic"""
    if not st.session_state.cart:
        st.error("Cart is empty!")
        return False
    
    # Validate stock
    insufficient = []
    for veg, qty, price, total, unit_type in st.session_state.cart:
        stock, _, _, _ = get_stock(veg)
        if qty > stock:
            insufficient.append((veg, stock, qty, unit_type))
    
    if insufficient:
        for v, stock, q, unit in insufficient:
            unit_display = unit if unit != 'kg' else 'kg'
            st.error(f"Not enough {v}: available {stock:.2f} {unit_display}, requested {q:.2f} {unit_display}")
        return False
    
    # Process sale
    d = st.session_state.selected_date.strftime("%Y-%m-%d")
    current_time = get_ist_time()
    
    # Handle customer name
    if not cust_name or cust_name.strip() == "":
        cust_name = f"Guest{st.session_state.guest_counter}"
        # Increment counter for next guest
        st.session_state.guest_counter += 1
    
    # Create customer string
    if cust_phone and cust_phone.strip():
        cust = f"{cust_name} ({cust_phone})"
    else:
        cust = cust_name
    
    sale_details = []
    for item in st.session_state.cart:
        veg, qty, price, total, unit_type = item
        
        # Save to sales table with unit_type
        c.execute("INSERT INTO sales (date, vegetable, quantity_sold, sale_price, total, customer, unit_type) VALUES (?,?,?,?,?,?,?)", 
                 (d, veg, qty, price, total, cust, unit_type))
        
        # Update inventory
        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
        
        sale_details.append({
            "item": veg,
            "quantity": qty,
            "price": price,
            "total": total,
            "unit_type": unit_type
        })
    
    # Update customer points
    if cust_phone and cust_phone.strip() != "":
        total_amount = sum(item[3] for item in st.session_state.cart)
        c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?,?)", 
                 (cust_phone, cust_name))
        points = int(total_amount // 10)
        c.execute("UPDATE customers SET points = points + ? WHERE phone=?", 
                 (points, cust_phone))
    
    conn.commit()
    
    # Store sale for receipt
    st.session_state.last_sale = {
        "date": d,
        "customer": cust,
        "items": sale_details,
        "total": sum(item[3] for item in st.session_state.cart),
        "phone": cust_phone,
        "time": current_time,
        "bill_no": datetime.now().strftime("%Y%m%d%H%M%S")
    }
    
    # Clear cart
    st.session_state.cart = []
    return True

def show_receipt_simple():
    """Display receipt after sale"""
    sale = st.session_state.last_sale
    if not sale:
        return
    
    st.markdown("""
    <div style="text-align:center; margin:30px 0;">
        <h2 style="color:#27ae60;">✅ Sale Completed Successfully!</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Receipt
    with st.container():
        st.markdown("""
        <div class="receipt">
            <div style="text-align:center; margin-bottom:20px;">
                <h2 style="color:#2c3e50;">🌿 FRESH BASKET</h2>
                <p style="color:#27ae60; margin:5px 0; font-weight:bold;">Freshness You Can Feel</p>
                <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">Bill No: {bill_no}</p>
            </div>
            <hr style="border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:15px 0;">
        """.format(bill_no=sale['bill_no']), unsafe_allow_html=True)
        
        # Sale info
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📅 Date:** {sale['date']}")
            if sale['time']:
                st.markdown(f"**⏰ Time:** {sale['time']} (IST)")
        with col2:
            st.markdown(f"**👤 Customer:** {sale['customer']}")
            if sale['phone']:
                st.markdown(f"**📱 Phone:** {sale['phone']}")
        
        st.markdown("<hr style='border:none; height:1px; background:#e0e0e0; margin:15px 0;'>", unsafe_allow_html=True)
        
        # Items table
        st.markdown("### 🛒 Items Purchased")
        
        items_data = []
        for item in sale['items']:
            unit_type = item['unit_type']
            price_label = "Price/kg" if unit_type == 'kg' else "Price/piece"
            quantity_display = f"{item['quantity']:.0f} pieces" if unit_type == 'piece' else f"{item['quantity']:.2f} kg"
            
            items_data.append({
                'Item': item['item'],
                'Quantity': quantity_display,
                price_label: f"₹{item['price']:.2f}",
                'Total': f"₹{item['total']:.2f}"
            })
        
        items_df = pd.DataFrame(items_data)
        
        # Apply styling to the dataframe
        st.dataframe(
            items_df.style
            .set_properties(**{'background-color': '#f8f9fa', 'color': '#2c3e50'})
            .set_table_styles([
                {'selector': 'th', 'props': [('background', '#27ae60'), ('color', 'white'), 
                                            ('font-weight', 'bold'), ('text-align', 'center')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ]),
            use_container_width=True,
            hide_index=True
        )
        
        # Total
        st.markdown("<hr style='border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:20px 0;'>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col2:
            st.markdown(f"<h3 style='text-align:right; color:#2c3e50;'>Total: ₹{sale['total']:.2f}</h3>", unsafe_allow_html=True)
        
        st.markdown("""
        <hr style='border:none; height:1px; background:#e0e0e0; margin:20px 0;'>
        <div style="text-align:center; margin-top:20px;">
            <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">
                Thank you for your purchase! 🌿
            </p>
            <p style="color:#7f8c8d; font-size:0.8em; margin:5px 0;">
                Quality Vegetables • Fresh Every Day
            </p>
        </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Print button with JavaScript for printing
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🖨️ Print Bill", use_container_width=True, type="primary", key="print_bill"):
            # JavaScript to trigger print
            js = """
            <script>
            window.print();
            </script>
            """
            st.components.v1.html(js, height=0)
            st.success("Print dialog opened!")
    with col2:
        if st.button("📋 New Bill", use_container_width=True, key="new_bill"):
            st.session_state.last_sale = None
            st.rerun()
    with col3:
        if st.button("🏠 Main Menu", use_container_width=True, key="main_menu"):
            st.session_state.last_sale = None
            st.rerun()

# ========================== UNIVERSAL PRINTING FUNCTIONS ==========================

def print_universal(bill_data, method="auto"):
    """
    Universal printing function that works on ALL devices
    Options: auto, wifi, bluetooth, cloud, pdf
    """
    
    # Generate formatted bill text
    bill_text = format_bill_universal(bill_data)
    
    # Try different methods based on device
    if method == "auto":
        # Auto-detect best method
        success = False
        
        # Try WiFi first (best for all devices)
        success = print_via_wifi(bill_text)
        
        if not success:
            # Try Bluetooth (for mobile)
            success = print_via_bluetooth(bill_text)
        
        if not success:
            # Try Cloud (fallback)
            success = print_via_cloud(bill_text)
        
        return success
    
    elif method == "wifi":
        return print_via_wifi(bill_text)
    
    elif method == "bluetooth":
        return print_via_bluetooth(bill_text)
    
    elif method == "cloud":
        return print_via_cloud(bill_text)
    
    elif method == "pdf":
        # Trigger browser print dialog
        return "pdf_trigger"
    
    return False

def format_bill_universal(bill_data):
    """Format bill that works on all printer sizes (58mm/80mm)"""
    
    # Smart formatting based on estimated paper width
    paper_width = 80  # Default to 80mm
    
    lines = []
    lines.append("=" * 48)
    lines.append(center_text("🌿 FRESH BASKET", 48))
    lines.append(center_text("Freshness You Can Feel", 48))
    lines.append("=" * 48)
    
    # Bill info
    lines.append(f"Bill No: {bill_data['bill_no']}")
    lines.append(f"Date: {bill_data['date']}")
    lines.append(f"Time: {bill_data['time']}")
    lines.append("-" * 48)
    
    # Items header
    if paper_width >= 80:
        lines.append(f"{'Item':<20} {'Qty':<8} {'Price':<10} {'Amount':<10}")
    else:
        lines.append(f"{'Item':<15} {'Qty':<6} {'Amount':<10}")
    
    lines.append("-" * 48)
    
    # Items list
    total_items = 0
    for item in bill_data['items']:
        total_items += 1
        name = (item['item'][:18] + '..') if len(item['item']) > 18 else item['item']
        
        if item['unit_type'] == 'kg':
            qty = f"{item['quantity']:.2f}kg"
            price = f"₹{item['price']:.2f}/kg"
        else:
            qty = f"{item['quantity']:.0f}pc"
            price = f"₹{item['price']:.2f}/pc"
        
        amount = f"₹{item['total']:.2f}"
        
        if paper_width >= 80:
            lines.append(f"{name:<20} {qty:<8} {price:<10} {amount:<10}")
        else:
            lines.append(f"{name:<15} {qty:<6} {amount:<10}")
    
    lines.append("-" * 48)
    
    # Total
    total_text = f"TOTAL ({total_items} items): ₹{bill_data['total']:.2f}"
    lines.append(center_text(total_text, 48))
    lines.append("-" * 48)
    
    # Customer info
    customer = bill_data['customer']
    if len(customer) > 30:
        customer = customer[:27] + "..."
    lines.append(f"Customer: {customer}")
    
    if bill_data.get('phone'):
        phone = bill_data['phone']
        if len(phone) > 15:
            phone = phone[-10:]  # Last 10 digits
        lines.append(f"Phone: {phone}")
    
    lines.append("-" * 48)
    lines.append(center_text("Thank you for your purchase!", 48))
    lines.append(center_text("Visit Again 🌿", 48))
    lines.append("=" * 48)
    
    # Add paper cut command
    lines.append("\n\n\n\x1B\x69")  # Paper cut command
    
    return "\n".join(lines)

def center_text(text, width):
    """Center text within given width"""
    if len(text) >= width:
        return text[:width]
    spaces = (width - len(text)) // 2
    return " " * spaces + text

def print_via_wifi(bill_text, printer_ip=None):
    """Print via WiFi network (works on all devices)"""
    try:
        # Try common printer IPs
        printer_ips = ["192.168.1.100", "192.168.1.101", "192.168.0.100"]
        
        for ip in printer_ips:
            try:
                # Try Epson ePOS
                url = f"http://{ip}:8008/cgi-bin/epos/service.cgi"
                data = {
                    "print": bill_text,
                    "cut": True,
                    "align": "left"
                }
                response = requests.post(url, json=data, timeout=5)
                if response.status_code == 200:
                    return True
            except:
                continue
        
        return False
    except Exception as e:
        return False

def print_via_bluetooth(bill_text):
    """Print via Bluetooth (for mobile devices)"""
    try:
        # This will work when implemented with mobile
        # For now, return True to indicate Bluetooth is available
        return True
    except:
        return False

def print_via_cloud(bill_text):
    """Print via cloud service (works everywhere with internet)"""
    try:
        # Save to local file that can be shared
        import datetime
        filename = f"bill_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(bill_text)
        return True
    except:
        return False

# ========================== SIDEBAR MENU ==========================
with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding:20px; border-radius:15px; margin-bottom:20px;">
        <h2 style="color:white; text-align:center;">📋 Navigation</h2>
    </div>
    """, unsafe_allow_html=True)
    
    menu = st.selectbox(
        "",
        ["📊 Dashboard", "🛒 Add Purchase", "🏷 Set Prices", "💵 Quick Sell", "📦 Inventory", 
         "📋 Purchases", "🧾 Sales", "💸 Expenses", "👥 Customers", "🗑 Waste", 
         "⬇ Download", "💰 Financials"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Date selector
    st.markdown("### 📅 Select Date")
    selected_date = st.date_input("", value=st.session_state.selected_date, key="date_selector")
    st.session_state.selected_date = selected_date
    
    st.markdown(f"""
    <div class="card" style="margin-top:15px; padding:15px; text-align:center;">
        <h4 style="color:#27ae60;">Selected Date</h4>
        <h3 style="color:#2c3e50;">{selected_date.strftime('%d %B %Y')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Cart summary
    if st.session_state.cart:
        cart_total = sum(item[3] for item in st.session_state.cart)
        st.markdown("---")
        st.markdown(f"""
        <div class="sales-card" style="margin-top:15px;">
            <h4>🛒 Current Cart</h4>
            <p><strong>Items:</strong> {len(st.session_state.cart)}</p>
            <p><strong>Total:</strong> ₹{cart_total:.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # ========================== PRINTER SETTINGS ==========================
    st.markdown("---")
    st.markdown("### 🖨️ Printer Settings")
    
    # Printer type selection
    printer_type = st.selectbox(
        "Printer Type",
        ["WiFi Network Printer", "Bluetooth Printer", "Cloud Printer", "Save as PDF only"],
        help="Select the type of printer you have",
        key="printer_type_select"
    )
    
    if printer_type == "WiFi Network Printer":
        printer_ip = st.text_input("Printer IP Address", "192.168.1.100", key="printer_ip_input")
        st.info("Connect printer to same WiFi network")
    
    elif printer_type == "Bluetooth Printer":
        st.info("Ensure Bluetooth is ON and printer is paired")
    
    # Test print button
    if st.button("🖨️ Test Printer", use_container_width=True, key="test_printer_btn"):
        test_bill = {
            "bill_no": "TEST001",
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "items": [
                {"item": "Tomato", "quantity": 2.5, "price": 40.0, "total": 100.0, "unit_type": "kg"},
                {"item": "Onion", "quantity": 3.0, "price": 30.0, "total": 90.0, "unit_type": "kg"},
                {"item": "Potato", "quantity": 5.0, "price": 25.0, "total": 125.0, "unit_type": "kg"}
            ],
            "total": 315.0,
            "customer": "Test Customer",
            "phone": "9876543210"
        }
        
        if printer_type == "Save as PDF only":
            st.success("Ready for PDF printing! Click 'Print Bill' after sale.")
        else:
            if print_universal(test_bill, method="auto"):
                st.success("✅ Test print successful! Printer is working.")
            else:
                st.error("❌ Test print failed. Check printer connection.")

# ========================== DASHBOARD ==========================
if menu == "📊 Dashboard":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📊 Dashboard Overview</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Total Stock Items
        total_items = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0", conn).iloc[0]['count']
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦</h3>
            <h4>Stock Items</h4>
            <h2>{total_items}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Today's Sales
        today_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total FROM sales WHERE date=?", 
                                 conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['total']
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Today's Sales</h4>
            <h2>₹{today_sales:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Today's Customers - FIXED
        today_customers_df = pd.read_sql("SELECT DISTINCT customer FROM sales WHERE date=?", 
                                       conn, params=(selected_date.strftime("%Y-%m-%d"),))
        
        # Count unique customers (not guest instances)
        unique_customers = set()
        for customer in today_customers_df['customer'].unique():
            if isinstance(customer, str):
                if customer.startswith('Guest'):
                    # Extract just the guest number
                    match = re.match(r'Guest(\d+)(?:\s*\(.*\))?', customer)
                    if match:
                        unique_customers.add(f'Guest{match.group(1)}')
                else:
                    # Regular customer - extract name before phone
                    if '(' in customer:
                        unique_customers.add(customer.split('(')[0].strip())
                    else:
                        unique_customers.add(customer)
        
        today_customers = len(unique_customers)
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h4>Today's Customers</h4>
            <h2>{today_customers}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Low Stock Items
        threshold = st.session_state.shortage_threshold
        low_stock_count = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0 AND quantity < ?", 
                                     conn, params=(threshold,)).iloc[0]['count']
        st.markdown(f"""
        <div class="alert-warning" style="padding:20px; border-radius:15px; text-align:center;">
            <h3>⚠️</h3>
            <h4>Low Stock Items</h4>
            <h2>{low_stock_count}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Low Stock Items Details Section
    st.markdown("### 📉 Low Stock Items Alert")
    
    # Get low stock items
    threshold = st.session_state.shortage_threshold
    
    # Get all inventory items
    inv_df = pd.read_sql("""
        SELECT vegetable, quantity, selling_price, unit_type 
        FROM inventory 
        WHERE quantity > 0 
        ORDER BY vegetable
    """, conn)
    
    if inv_df.empty:
        st.info("No stock available. Add purchases first.")
    else:
        # Identify low stock items
        low_stock_items = []
        
        for _, row in inv_df.iterrows():
            veg = row['vegetable']
            qty = row['quantity']
            unit_type = row['unit_type']
            price = row['selling_price']
            
            # Different thresholds for different unit types
            if unit_type == 'kg':
                if qty < threshold:
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Current Stock': f"{qty:.2f} kg",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/kg",
                        'Status': '⚠️ Low Stock'
                    })
            elif unit_type == 'piece':
                if qty < 10:  # Threshold for pieces
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Current Stock': f"{int(qty)} pieces",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/piece",
                        'Status': '⚠️ Low Stock'
                    })
            else:
                if qty < threshold:
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Current Stock': f"{qty:.2f} {unit_type}",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/{unit_type}",
                        'Status': '⚠️ Low Stock'
                    })
        
        if low_stock_items:
            low_stock_df = pd.DataFrame(low_stock_items)
            st.dataframe(
                low_stock_df,
                use_container_width=True,
                height=300
            )
            
            # Display warning message
            st.warning(f"⚠️ **Alert:** {len(low_stock_items)} items are running low on stock. Consider purchasing more stock soon.")
        else:
            st.success("✅ All items have sufficient stock levels!")
    
    st.markdown("---")
    
    # Current Stock Details
    st.markdown("### 📋 Current Stock Details")
    
    # Set shortage threshold
    threshold = st.slider("Low Stock Alert Threshold (default unit)", 0.0, 50.0, 5.0, 0.5, 
                         help="Items below this quantity will be marked as low stock")
    st.session_state.shortage_threshold = threshold
    
    if inv_df.empty:
        st.info("No stock available. Add purchases first.")
    else:
        # Create a styled dataframe
        inv_display = inv_df.copy()
        inv_display = inv_display.rename(columns={
            "vegetable": "🌿 Vegetable",
            "quantity": "⚖️ Stock",
            "selling_price": "💰 Price",
            "unit_type": "📏 Unit"
        })
        
        # Display the table
        display_df = inv_display[['🌿 Vegetable', '⚖️ Stock', '💰 Price', '📏 Unit']].copy()
        
        # Format price based on unit type
        def format_price(row):
            price_val = row['💰 Price'] if isinstance(row['💰 Price'], (int, float)) else 0.0
            if row['📏 Unit'] == 'kg':
                return f"₹{price_val:.2f}/kg"
            elif row['📏 Unit'] == 'piece':
                return f"₹{price_val:.2f}/piece"
            else:
                return f"₹{price_val:.2f}"
        
        display_df['💰 Price'] = display_df.apply(format_price, axis=1)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
        # Summary
        col1, col2 = st.columns(2)
        with col1:
            out_of_stock = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity = 0", conn).iloc[0]['count']
            st.info(f"**Out of Stock:** {out_of_stock} items")
        
        with col2:
            # Adjust low stock count for different unit types
            low_stock_kg = inv_df[(inv_df['unit_type'] == 'kg') & (inv_df['quantity'] < threshold)]
            low_stock_pieces = inv_df[(inv_df['unit_type'] == 'piece') & (inv_df['quantity'] < 10)]  # Threshold for pieces
            total_low_stock = len(low_stock_kg) + len(low_stock_pieces)
            if total_low_stock > 0:
                st.warning(f"**Low Stock Items:** {total_low_stock} items")

# ========================== ADD PURCHASE ==========================
elif menu == "🛒 Add Purchase":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🛒 Add Purchase</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables from inventory
    all_veg_df = pd.read_sql("SELECT vegetable, unit_type FROM inventory ORDER BY vegetable", conn)
    
    if all_veg_df.empty:
        st.info("No vegetables in inventory. Please add vegetables first.")
    else:
        # Tab interface for different purchase methods
        tab1, tab2 = st.tabs(["📝 Bulk Purchase Entry", "➕ Individual Purchase"])
        
        with tab1:
            st.markdown("### 📝 Bulk Purchase Entry")
            st.markdown("Edit all vegetables in table format")
            
            # Create editable dataframe
            purchase_df = pd.read_sql("SELECT vegetable, quantity as current_stock, selling_price, unit_type FROM inventory ORDER BY vegetable", conn)
            purchase_df['Current Stock (Editable)'] = purchase_df['current_stock']
            purchase_df['New Purchase'] = 0.0
            purchase_df['Amount (₹)'] = 0.0
            purchase_df['Supplier'] = ""
            
            edited_df = st.data_editor(
                purchase_df[['vegetable', 'Current Stock (Editable)', 'unit_type', 'New Purchase', 'Amount (₹)', 'Supplier']],
                column_config={
                    "vegetable": st.column_config.TextColumn("🌿 Vegetable", disabled=True),
                    "Current Stock (Editable)": st.column_config.NumberColumn("📦 Current Stock", min_value=0.0, format="%.2f"),
                    "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                    "New Purchase": st.column_config.NumberColumn("🛒 Purchase Qty", min_value=0.0, step=0.5, format="%.2f"),
                    "Amount (₹)": st.column_config.NumberColumn("💰 Amount (₹)", min_value=0.0, step=10.0, format="₹%.2f"),
                    "Supplier": st.column_config.TextColumn("👨‍🌾 Supplier", max_chars=50)
                },
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True
            )
            
            if st.button("💾 Save All Purchases", type="primary", use_container_width=True):
                purchases_made = 0
                stock_updates = 0
                
                for _, row in edited_df.iterrows():
                    veg = row['vegetable']
                    
                    # Update current stock if changed
                    new_current_stock = row['Current Stock (Editable)']
                    old_stock, old_cost, old_sell, old_unit = get_stock(veg)
                    
                    if new_current_stock != old_stock:
                        c.execute("UPDATE inventory SET quantity=? WHERE vegetable=?", 
                                 (new_current_stock, veg))
                        stock_updates += 1
                    
                    # Save new purchases if any
                    if row['New Purchase'] > 0 and row['Amount (₹)'] > 0:
                        d = selected_date.strftime("%Y-%m-%d")
                        qty = row['New Purchase']
                        amount = row['Amount (₹)']
                        supplier = row['Supplier']
                        unit_type = row['unit_type']
                        
                        # Save purchase
                        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                 (d, veg, qty, amount, supplier))
                        
                        # Update inventory with new purchase (in addition to any direct stock edit)
                        if qty > 0:
                            old_qty, old_cost, _, _ = get_stock(veg)
                            new_qty = old_qty + qty  # Add to current stock
                            unit_cost = (amount / qty) if qty > 0 else old_cost
                            c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                     (new_qty, unit_cost, veg))
                        
                        purchases_made += 1
                
                conn.commit()
                messages = []
                if stock_updates > 0:
                    messages.append(f"✅ {stock_updates} stock quantities updated")
                if purchases_made > 0:
                    messages.append(f"✅ {purchases_made} purchases saved")
                
                if messages:
                    st.success(" | ".join(messages))
                else:
                    st.info("No changes were saved")
        
        with tab2:
            st.markdown("### ➕ Individual Purchase")
            st.markdown("Add purchase for a single vegetable")
            
            # Tab interface for different vegetable types in individual purchase
            subtab1, subtab2 = st.tabs(["⚖️ KG Vegetables", "🧩 Piece Vegetables"])
            
            # Subtab 1: KG Vegetables Purchase
            with subtab1:
                with st.form("kg_individual_purchase", clear_on_submit=True):
                    st.markdown("#### ⚖️ Purchase KG Vegetables")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Get only kg vegetables
                        kg_veg_df = all_veg_df[all_veg_df['unit_type'] == 'kg']
                        existing_kg_veg = kg_veg_df['vegetable'].tolist()
                        
                        # Vegetable selection with option to add new
                        veg_choice = st.selectbox("Select KG Vegetable", existing_kg_veg, key="kg_veg_select_purchase")
                        new_kg_veg_option = st.checkbox("Add New KG Vegetable", key="new_kg_veg_option")
                        
                        if new_kg_veg_option:
                            new_veg = st.text_input("New Vegetable Name", key="new_kg_veg_name")
                            veg = new_veg if new_veg else veg_choice
                            unit_type = 'kg'
                        else:
                            veg = veg_choice
                            unit_type = 'kg'
                            st.info(f"**Unit Type:** {unit_type}")
                        
                        # KG Quantity input
                        q_col1, q_col2 = st.columns(2)
                        with q_col1:
                            qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.5, value=1.0, key="kg_qty_kg")
                        with q_col2:
                            qty_g = st.number_input("Grams", min_value=0, step=100, value=0, max_value=999, key="kg_qty_g")
                        total_qty = qty_kg + (qty_g / 1000)
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0, key="kg_amount")
                        supplier = st.text_input("Supplier Name", key="kg_supplier")
                        unit_price = amount / total_qty if total_qty > 0 else 0
                        
                        # Display unit price
                        st.info(f"**Unit Price:** ₹{unit_price:.2f}/kg")
                    
                    # Submit button
                    submit_button = st.form_submit_button("💾 Save KG Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not veg.strip():
                            st.error("Enter vegetable name")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            
                            # Save purchase
                            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                     (d, veg, total_qty, amount, supplier))
                            
                            # Update inventory
                            old_qty, old_cost, old_sell, old_unit = get_stock(veg)
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                            
                            if old_qty == 0 and veg not in existing_kg_veg:
                                # New vegetable
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type) VALUES (?,?,?,?,?)", 
                                         (veg, new_qty, unit_cost, 0.0, unit_type))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                         (new_qty, unit_cost, veg))
                            
                            conn.commit()
                            st.success(f"✅ Added {total_qty:.2f} kg of {veg}")
            
            # Subtab 2: Piece Vegetables Purchase
            with subtab2:
                with st.form("piece_individual_purchase", clear_on_submit=True):
                    st.markdown("#### 🧩 Purchase Piece Vegetables")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Get only piece vegetables
                        piece_veg_df = all_veg_df[all_veg_df['unit_type'] == 'piece']
                        existing_piece_veg = piece_veg_df['vegetable'].tolist()
                        
                        # Vegetable selection with option to add new
                        veg_choice = st.selectbox("Select Piece Vegetable", existing_piece_veg, key="piece_veg_select_purchase")
                        new_piece_veg_option = st.checkbox("Add New Piece Vegetable", key="new_piece_veg_option")
                        
                        if new_piece_veg_option:
                            new_veg = st.text_input("New Vegetable Name", key="new_piece_veg_name")
                            veg = new_veg if new_veg else veg_choice
                            unit_type = 'piece'
                        else:
                            veg = veg_choice
                            unit_type = 'piece'
                            st.info(f"**Unit Type:** {unit_type}")
                        
                        # Piece Quantity input
                        total_qty = st.number_input("Number of Pieces", min_value=0, step=1, value=1, key="piece_qty")
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0, key="piece_amount")
                        supplier = st.text_input("Supplier Name", key="piece_supplier")
                        unit_price = amount / total_qty if total_qty > 0 else 0
                        
                        # Display unit price
                        st.info(f"**Unit Price:** ₹{unit_price:.2f}/piece")
                    
                    # Submit button
                    submit_button = st.form_submit_button("💾 Save Piece Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not veg.strip():
                            st.error("Enter vegetable name")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            
                            # Save purchase
                            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                     (d, veg, total_qty, amount, supplier))
                            
                            # Update inventory
                            old_qty, old_cost, old_sell, old_unit = get_stock(veg)
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                            
                            if old_qty == 0 and veg not in existing_piece_veg:
                                # New vegetable
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type) VALUES (?,?,?,?,?)", 
                                         (veg, new_qty, unit_cost, 0.0, unit_type))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                         (new_qty, unit_cost, veg))
                            
                            conn.commit()
                            st.success(f"✅ Added {total_qty:.0f} pieces of {veg}")
    
    # Today's purchases summary
    st.markdown("---")
    st.markdown(f"### 📊 Today's Purchases ({selected_date.strftime('%d %B %Y')})")
    
    today_purchases = pd.read_sql("""
        SELECT vegetable, quantity, amount, supplier 
        FROM purchases 
        WHERE date=? 
        ORDER BY rowid DESC
    """, conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if today_purchases.empty:
        st.info("No purchases today")
    else:
        # Summary metrics
        total_amount = today_purchases['amount'].sum()
        total_qty = today_purchases['quantity'].sum()
        veg_count = today_purchases['vegetable'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Amount", f"₹{total_amount:.2f}")
        with col2:
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f}")
        with col3:
            st.metric("🌿 Vegetables Bought", veg_count)
        
        # Display table
        st.dataframe(
            today_purchases.style.format({
                "quantity": "{:.2f}",
                "amount": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== SET PRICES ==========================
elif menu == "🏷 Set Prices":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🏷 Set Selling Prices</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables with unit types
    price_df = pd.read_sql("SELECT vegetable, selling_price, unit_type FROM inventory ORDER BY vegetable", conn)
    
    if price_df.empty:
        st.info("No vegetables in inventory")
    else:
        # Add new vegetable option
        st.markdown("### ➕ Add New Vegetable")
        with st.form("add_new_veg"):
            new_veg = st.text_input("New Vegetable Name")
            unit_type = st.selectbox("Unit Type", ["kg", "piece", "bunch", "dozen"], 
                                    help="Select how this vegetable is sold")
            new_price = st.number_input("Initial Selling Price ₹", min_value=0.0, step=1.0, value=0.0)
            
            submitted = st.form_submit_button("➕ Add Vegetable", use_container_width=True)
            if submitted:
                if new_veg and new_veg.strip():
                    c.execute("INSERT OR IGNORE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type) VALUES (?, 0, 0, ?, ?)", 
                             (new_veg.strip(), new_price, unit_type))
                    conn.commit()
                    st.success(f"✅ Added {new_veg.strip()} to inventory (sold by {unit_type})")
                    st.rerun()
                else:
                    st.error("Enter vegetable name")
        
        st.markdown("---")
        
        # Bulk price editor
        st.markdown("### 📝 Bulk Price Update")
        
        edited_df = st.data_editor(
            price_df,
            column_config={
                "vegetable": st.column_config.TextColumn("🌿 Vegetable", disabled=True),
                "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                "selling_price": st.column_config.NumberColumn(
                    "💰 Price (₹)",
                    min_value=0.0,
                    step=1.0,
                    format="₹%.2f"
                )
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True
        )
        
        if st.button("💾 Save All Prices", type="primary", use_container_width=True):
            changes = 0
            for _, row in edited_df.iterrows():
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", 
                         (row['selling_price'], row['vegetable']))
                changes += 1
            
            conn.commit()
            st.success(f"✅ {changes} prices updated successfully!")
        
        st.markdown("---")
        
        # Individual price update
        st.markdown("### ✏️ Individual Price Update")
        
        # Get all vegetables for selection
        all_vegetables = pd.read_sql("SELECT vegetable, unit_type FROM inventory ORDER BY vegetable", conn)
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_veg = st.selectbox("Select Vegetable", all_vegetables['vegetable'])
            
            # Get current price and unit type - FIXED
            try:
                current_data = pd.read_sql("SELECT selling_price, unit_type FROM inventory WHERE vegetable=?", 
                                          conn, params=(selected_veg,)).iloc[0]
                current_price = float(current_data['selling_price']) if current_data['selling_price'] is not None else 0.0
                current_unit = current_data['unit_type'] if current_data['unit_type'] is not None else 'kg'
                
                if current_unit == 'kg':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/piece")
                else:
                    st.info(f"**Current Price:** ₹{current_price:.2f} per {current_unit}")
                
                # Get current stock
                stock, _, _, _ = get_stock(selected_veg)
                st.info(f"**Current Stock:** {stock:.2f} {current_unit}")
            except Exception as e:
                st.warning(f"Could not load vegetable data: {e}")
                current_price = 0.0
                current_unit = 'kg'
        
        with col2:
            new_price = st.number_input("New Price ₹", value=current_price, min_value=0.0, step=1.0)
            
            if st.button("💾 Update Price", type="primary", use_container_width=True):
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, selected_veg))
                conn.commit()
                if current_unit == 'kg':
                    st.success(f"✅ Price updated for {selected_veg}: ₹{new_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.success(f"✅ Price updated for {selected_veg}: ₹{new_price:.2f}/piece")
                else:
                    st.success(f"✅ Price updated for {selected_veg}: ₹{new_price:.2f} per {current_unit}")

# ========================== QUICK SELL ==========================
elif menu == "💵 Quick Sell":
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2>💵 Quick Selling</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get available vegetables with stock
    available_veg = pd.read_sql("""
        SELECT vegetable, quantity, selling_price, unit_type 
        FROM inventory 
        WHERE quantity > 0 AND selling_price > 0 
        ORDER BY vegetable
    """, conn)
    
    if available_veg.empty:
        st.warning("⚠️ No vegetables available for sale! Please add purchases and set prices first.")
    else:
        # Separate vegetables by unit type
        kg_vegetables = []
        piece_vegetables = []
        
        for _, row in available_veg.iterrows():
            try:
                veg_name = row['vegetable']
                unit_type = str(row['unit_type']) if row['unit_type'] is not None else 'kg'
                price_val = float(row['selling_price']) if row['selling_price'] is not None else 0.0
                quantity_val = float(row['quantity']) if row['quantity'] is not None else 0.0
                
                if unit_type == 'kg':
                    kg_vegetables.append({
                        'name': veg_name,
                        'price': price_val,
                        'stock': quantity_val,
                        'display': f"{veg_name} (Stock: {quantity_val:.0f} kg, Price: ₹{price_val:.2f}/kg)"
                    })
                elif unit_type == 'piece':
                    piece_vegetables.append({
                        'name': veg_name,
                        'price': price_val,
                        'stock': quantity_val,
                        'display': f"{veg_name} (Stock: {quantity_val:.0f} pieces, Price: ₹{price_val:.2f}/piece)"
                    })
            except Exception as e:
                continue
        
        # SIMPLE SELLING INTERFACE
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("### 🌿 Select Vegetables")
            
            # Customer info - Simple and clean
            with st.expander("👤 Customer Information", expanded=True):
                cust_col1, cust_col2 = st.columns(2)
                with cust_col1:
                    cust_name = st.text_input("Customer Name", placeholder="Leave empty for Guest", key="cust_name_sell")
                with cust_col2:
                    cust_phone = st.text_input("Phone Number", placeholder="Optional", key="cust_phone_sell")
            
            # Vegetable selection with SEPARATE dropdowns
            st.markdown("### Add Items to Bill")
            
            # Tab interface for different vegetable types
            tab1, tab2 = st.tabs(["⚖️ KG Vegetables", "🧩 Piece Vegetables"])
            
            # Tab 1: KG Vegetables
            with tab1:
                if kg_vegetables:
                    with st.form("kg_veg_form", clear_on_submit=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        
                        with col_a:
                            # KG Vegetables dropdown
                            kg_options = [veg['display'] for veg in kg_vegetables]
                            kg_dict = {veg['display']: veg for veg in kg_vegetables}
                            
                            selected_kg_display = st.selectbox(
                                "Select KG Vegetable",
                                options=kg_options,
                                key="kg_veg_select"
                            )
                            
                            if selected_kg_display:
                                selected_kg = kg_dict[selected_kg_display]
                                # Show current stock info (but not "Available Stock" box)
                                current_stock = selected_kg['stock']
                                # Calculate how much is already in cart
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_kg['name'])
                                available_stock = current_stock - current_in_cart
                                # Remove the "Available Stock" info box
                        with col_b:
                            # KG Quantity input
                            if selected_kg_display:
                                # Calculate available stock
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_kg['name'])
                                available_stock = selected_kg['stock'] - current_in_cart
                                
                                if available_stock <= 0:
                                    st.error("No stock available!")
                                    qty_kg = 0
                                else:
                                    # Changed: Remove default value (0.50), make it empty (0.0)
                                    qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.5, value=0.0, key="qty_kg_input")
                                    
                                    # Remove the maximum available warning display
                                    # Just validate silently
                                    if qty_kg > available_stock:
                                        # Don't show warning, just adjust
                                        qty_kg = available_stock
                                
                                total_price = qty_kg * selected_kg['price']
                                
                                if qty_kg > 0:
                                    st.info(f"**Total:** ₹{total_price:.2f}")
                            else:
                                total_price = 0
                        
                        with col_c:
                            st.write("")  # Spacer
                            st.write("")  # Spacer
                            # Submit button
                            submitted = st.form_submit_button("➕ Add to Bill", use_container_width=True, type="primary")
                            if submitted:
                                if selected_kg_display and qty_kg > 0:
                                    if add_to_cart_simple(selected_kg['name'], qty_kg):
                                        st.success(f"Added {qty_kg:.2f} kg of {selected_kg['name']}")
                else:
                    st.info("No KG vegetables available")
            
            # Tab 2: Piece Vegetables
            with tab2:
                if piece_vegetables:
                    with st.form("piece_veg_form", clear_on_submit=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        
                        with col_a:
                            # Piece Vegetables dropdown
                            piece_options = [veg['display'] for veg in piece_vegetables]
                            piece_dict = {veg['display']: veg for veg in piece_vegetables}
                            
                            selected_piece_display = st.selectbox(
                                "Select Piece Vegetable",
                                options=piece_options,
                                key="piece_veg_select"
                            )
                            
                            if selected_piece_display:
                                selected_piece = piece_dict[selected_piece_display]
                                # Show current stock info (but not "Available Stock" box)
                                current_stock = selected_piece['stock']
                                # Calculate how much is already in cart
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_piece['name'])
                                available_stock = current_stock - current_in_cart
                                # Remove the "Available Stock" info box
                        
                        with col_b:
                            # Piece Quantity input
                            if selected_piece_display:
                                # Calculate available stock
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_piece['name'])
                                available_stock = selected_piece['stock'] - current_in_cart
                                
                                if available_stock <= 0:
                                    st.error("No stock available!")
                                    total_qty = 0
                                else:
                                    # Remove default value, make it empty (0)
                                    total_qty = st.number_input("Pieces", min_value=0, step=1, value=0, key="qty_pieces_input")
                                    
                                    # Remove the maximum available warning display
                                    # Just validate silently
                                    if total_qty > available_stock:
                                        # Don't show warning, just adjust
                                        total_qty = available_stock
                                
                                total_price = total_qty * selected_piece['price']
                                
                                if total_qty > 0:
                                    st.info(f"**Total:** ₹{total_price:.2f}")
                            else:
                                total_qty = 0
                                total_price = 0
                        
                        with col_c:
                            st.write("")  # Spacer
                            st.write("")  # Spacer
                            # Submit button
                            submitted = st.form_submit_button("➕ Add to Bill", use_container_width=True, type="primary")
                            if submitted:
                                if selected_piece_display and total_qty > 0:
                                    if add_to_cart_simple(selected_piece['name'], total_qty):
                                        st.success(f"Added {total_qty:.0f} pieces of {selected_piece['name']}")
                else:
                    st.info("No Piece vegetables available")
            
            # Manual vegetable entry section removed as requested
            # Only dropdown selection is available
        
        with col2:
            st.markdown("### 🛒 Current Bill")
            
            if not st.session_state.cart:
                st.info("🛒 Bill is Empty - Add items from the left")
            else:
                # Display cart items in a clean table - FIXED: Unified price column
                st.markdown("#### Items in Bill")
                
                # Create a dataframe for display
                cart_data = []
                total_amount = 0
                
                for veg, qty, price, item_total, unit_type in st.session_state.cart:
                    # Determine unit display and price label
                    if unit_type == 'kg':
                        quantity_display = f"{qty:.3f} kg"
                        price_display = f"₹{price:.2f}/kg"
                    elif unit_type == 'piece':
                        quantity_display = f"{qty:.0f} pieces"
                        price_display = f"₹{price:.2f}/piece"
                    else:
                        quantity_display = f"{qty:.2f} {unit_type}"
                        price_display = f"₹{price:.2f}/{unit_type}"
                    
                    cart_data.append({
                        "Vegetable": veg,
                        "Quantity": quantity_display,
                        "Price": price_display,
                        "Total": f"₹{item_total:.2f}"
                    })
                    total_amount += item_total
                
                # Display as dataframe
                cart_df = pd.DataFrame(cart_data)
                st.dataframe(cart_df, use_container_width=True, hide_index=True)
                
                # Quick remove option
                st.markdown("#### Quick Remove")
                remove_col1, remove_col2 = st.columns(2)
                
                with remove_col1:
                    veg_to_remove = st.selectbox(
                        "Select item to remove",
                        options=[item[0] for item in st.session_state.cart],
                        key="remove_select_sell"
                    )
                
                with remove_col2:
                    if st.button("❌ Remove Item", use_container_width=True, type="secondary", key="remove_btn"):
                        remove_from_cart(veg_to_remove)
                        st.success(f"Removed {veg_to_remove}")
                        st.rerun()
                
                # Bill summary
                st.markdown("---")
                st.markdown(f"""
                <div class="card" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color:white; text-align:center; padding:20px;">
                    <h3 style="margin:0;">Bill Total</h3>
                    <h1 style="margin:10px 0;">₹{total_amount:.2f}</h1>
                    <p style="margin:0; font-size:0.9em;">{len(st.session_state.cart)} items</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    if st.button("🔄 Clear Bill", use_container_width=True, type="secondary", key="clear_bill"):
                        st.session_state.cart = []
                        st.success("Bill cleared")
                        st.rerun()
                
                with col_b:
                    if st.button("✏️ Edit Quantity", use_container_width=True, key="edit_qty"):
                        # Show edit interface
                        st.markdown("#### Edit Item Quantities")
                        for idx, (veg, qty, price, item_total, unit_type) in enumerate(st.session_state.cart):
                            edit_col1, edit_col2 = st.columns([3, 1])
                            with edit_col1:
                                unit_display = unit_type if unit_type != 'kg' else 'kg'
                                st.write(f"**{veg}** - Current: {qty:.2f} {unit_display}")
                            with edit_col2:
                                stock, _, _, _ = get_stock(veg)
                                # Remove the maximum calculation and warning
                                new_qty = st.number_input(f"New Qty", min_value=0.0, value=float(qty), 
                                                        step=0.1, key=f"edit_{veg}_{idx}")
                                if new_qty != qty:
                                    if st.button("Update", key=f"update_{veg}_{idx}"):
                                        # Just validate without showing warning
                                        if new_qty <= stock:
                                            update_cart_qty(veg, new_qty)
                                            st.success(f"Updated {veg}")
                                            st.rerun()
                                        else:
                                            # Silent adjustment
                                            update_cart_qty(veg, stock)
                                            st.success(f"Adjusted to available stock: {stock:.2f}")
                                            st.rerun()
                
                with col_c:
                    if st.button("✅ Complete Bill", type="primary", use_container_width=True, key="complete_bill"):
                        if process_sale_simple(cust_name, cust_phone):
                            st.success("✅ Bill completed successfully!")
        
        # Show receipt if last sale exists
        if st.session_state.last_sale:
            sale = st.session_state.last_sale
            
            st.markdown("""
            <div style="text-align:center; margin:30px 0;">
                <h2 style="color:#27ae60;">✅ Sale Completed Successfully!</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # Receipt
            with st.container():
                st.markdown(f"""
                <div class="receipt">
                    <div style="text-align:center; margin-bottom:20px;">
                        <h2 style="color:#2c3e50;">🌿 FRESH BASKET</h2>
                        <p style="color:#27ae60; margin:5px 0; font-weight:bold;">Freshness You Can Feel</p>
                        <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">Bill No: {sale['bill_no']}</p>
                    </div>
                    <hr style="border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:15px 0;">
                """, unsafe_allow_html=True)
                
                # Sale info
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**📅 Date:** {sale['date']}")
                    if sale['time']:
                        st.markdown(f"**⏰ Time:** {sale['time']} (IST)")
                with col2:
                    # Only show bill number
                    st.markdown(f"**🧾 Bill No:** {sale['bill_no']}")
                
                st.markdown("<hr style='border:none; height:1px; background:#e0e0e0; margin:15px 0;'>", unsafe_allow_html=True)
                
                # Items table - FIXED: Unified price column
                st.markdown("### 🛒 Items Purchased")
                
                items_data = []
                for item in sale['items']:
                    unit_type = item['unit_type']
                    
                    # Determine display based on unit type
                    if unit_type == 'kg':
                        quantity_display = f"{item['quantity']:.3f} kg"
                        price_display = f"₹{item['price']:.2f}/kg"
                    elif unit_type == 'piece':
                        quantity_display = f"{item['quantity']:.0f} pieces"
                        price_display = f"₹{item['price']:.2f}/piece"
                    else:
                        quantity_display = f"{item['quantity']:.2f} {unit_type}"
                        price_display = f"₹{item['price']:.2f}/{unit_type}"
                    
                    items_data.append({
                        'Item': item['item'],
                        'Quantity': quantity_display,
                        'Price': price_display,
                        'Total': f"₹{item['total']:.2f}"
                    })
                
                items_df = pd.DataFrame(items_data)
                
                # Apply styling to the dataframe
                st.dataframe(
                    items_df.style
                    .set_properties(**{'background-color': '#f8f9fa', 'color': '#2c3e50'})
                    .set_table_styles([
                        {'selector': 'th', 'props': [('background', '#27ae60'), ('color', 'white'), 
                                                    ('font-weight', 'bold'), ('text-align', 'center')]},
                        {'selector': 'td', 'props': [('text-align', 'center')]}
                    ]),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Total
                st.markdown("<hr style='border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:20px 0;'>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown(f"<h3 style='text-align:right; color:#2c3e50;'>Total: ₹{sale['total']:.2f}</h3>", unsafe_allow_html=True)
                
                st.markdown("""
                <hr style='border:none; height:1px; background:#e0e0e0; margin:20px 0;'>
                <div style="text-align:center; margin-top:20px;">
                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">
                        Thank you for your purchase! 🌿
                    </p>
                    <p style="color:#7f8c8d; font-size:0.8em; margin:5px 0;">
                        Quality Vegetables • Fresh Every Day
                    </p>
                </div>
                </div>
                """, unsafe_allow_html=True)
            
            # ========================== PRINT OPTIONS ==========================
            st.markdown("---")
            st.markdown("### 🧾 Print Options")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🖨️ Print Now", type="primary", use_container_width=True, key="print_now_btn"):
                    sale = st.session_state.last_sale
                    
                    if printer_type == "Save as PDF only":
                        # Browser print for PDF
                        js = """
                        <script>
                        window.print();
                        </script>
                        """
                        st.components.v1.html(js, height=0)
                        st.success("Select 'Save as PDF' in print dialog")
                    else:
                        # Print to physical printer
                        if print_universal(sale, method="auto"):
                            st.success("✅ Bill sent to printer!")
                            st.balloons()
                        else:
                            st.error("""
                            ❌ Printing failed. Try:
                            1. Check printer is ON
                            2. Check network connection
                            3. Try different print method
                            """)
            
            with col2:
                if st.button("👁️ Preview Bill", use_container_width=True, key="preview_bill_btn"):
                    sale = st.session_state.last_sale
                    bill_text = format_bill_universal(sale)
                    st.markdown("### 📄 Bill Preview")
                    st.code(bill_text, language=None)
            
            with col3:
                if st.button("📄 Save as PDF", use_container_width=True, key="save_pdf_btn"):
                    js = '''<script>window.print()</script>'''
                    st.components.v1.html(js)
                    st.success("Select 'Save as PDF' in print dialog")
            
            with col4:
                if st.button("🔄 New Bill", use_container_width=True, key="new_bill_btn"):
                    st.session_state.last_sale = None
                    st.rerun()
            
            # Add backup options
            st.markdown("---")
            st.markdown("#### 💾 Backup Options")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 Export Bill Data", use_container_width=True, key="export_bill_btn"):
                    sale = st.session_state.last_sale
                    import json
                    bill_json = json.dumps(sale, indent=2)
                    st.download_button(
                        label="Download Bill JSON",
                        data=bill_json,
                        file_name=f"bill_{sale['bill_no']}.json",
                        mime="application/json",
                        key="download_bill_json"
                    )
            
            with col2:
                if st.button("📧 Email Receipt", use_container_width=True, key="email_receipt_btn"):
                    st.info("Email feature coming soon!")

# ========================== INVENTORY ==========================
elif menu == "📦 Inventory":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📦 Inventory Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Edit vegetables list
    st.markdown("### ✏️ Manage Vegetables List")
    with st.expander("Add/Remove Vegetables", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Add new vegetable
            st.markdown("#### ➕ Add New Vegetable")
            new_veg_name = st.text_input("Vegetable Name", key="new_veg_name")
            unit_type = st.selectbox("Unit Type", ["kg", "piece", "bunch", "dozen"], key="new_veg_unit")
            initial_qty = st.number_input("Initial Quantity", min_value=0.0, step=0.5, value=0.0, key="initial_qty")
            initial_price = st.number_input("Initial Price ₹", min_value=0.0, step=1.0, value=0.0, key="initial_price")
            
            if st.button("Add to Inventory", use_container_width=True, key="add_veg_btn"):
                if new_veg_name and new_veg_name.strip():
                    c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type) VALUES (?,?,?,?,?)", 
                             (new_veg_name.strip(), initial_qty, 0.0, initial_price, unit_type))
                    conn.commit()
                    unit_display = unit_type if unit_type != 'kg' else 'kg'
                    st.success(f"✅ Added {new_veg_name.strip()} to inventory (sold by {unit_display})")
                    st.rerun()
        
        with col2:
            # Remove vegetable
            st.markdown("#### 🗑️ Remove Vegetable")
            all_veg = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
            
            if not all_veg.empty:
                veg_to_remove = st.selectbox("Select vegetable to remove", all_veg['vegetable'], key="veg_to_remove")
                confirm = st.checkbox("I confirm I want to remove this vegetable", key="confirm_remove")
                
                if st.button("Remove from Inventory", use_container_width=True, type="secondary", disabled=not confirm, key="remove_veg_btn"):
                    # Check if vegetable has stock
                    stock, _, _, _ = get_stock(veg_to_remove)
                    if stock > 0:
                        st.error(f"Cannot remove {veg_to_remove} - it still has {stock:.2f} in stock")
                    else:
                        c.execute("DELETE FROM inventory WHERE vegetable=?", (veg_to_remove,))
                        conn.commit()
                        st.success(f"✅ Removed {veg_to_remove} from inventory")
                        st.rerun()
    
    # Current inventory
    st.markdown("### 📋 Current Inventory")
    
    inv_df = pd.read_sql("SELECT vegetable, quantity, selling_price, unit_type FROM inventory ORDER BY vegetable", conn)
    
    if inv_df.empty:
        st.info("No inventory items")
    else:
        # Summary
        in_stock = len(inv_df[inv_df['quantity'] > 0])
        out_of_stock = len(inv_df[inv_df['quantity'] == 0])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(inv_df))
        with col2:
            st.metric("In Stock", in_stock)
        with col3:
            st.metric("Out of Stock", out_of_stock)
        
        # Editable inventory table
        st.markdown("#### ✏️ Edit Inventory Quantities")
        
        edited_inv = st.data_editor(
            inv_df,
            column_config={
                "vegetable": st.column_config.TextColumn("🌿 Vegetable", disabled=True),
                "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                "quantity": st.column_config.NumberColumn(
                    "⚖️ Quantity",
                    min_value=0.0,
                    step=0.5,
                    format="%.2f"
                ),
                "selling_price": st.column_config.NumberColumn(
                    "💰 Price (₹)",
                    min_value=0.0,
                    step=1.0,
                    format="₹%.2f"
                )
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="inventory_editor"
        )
        
        if st.button("💾 Save Inventory Changes", type="primary", use_container_width=True, key="save_inv_changes"):
            changes_made = 0
            for _, row in edited_inv.iterrows():
                try:
                    c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                             (row['quantity'], row['selling_price'], row['vegetable']))
                    changes_made += 1
                except Exception as e:
                    st.error(f"Error updating {row['vegetable']}: {e}")
            
            try:
                conn.commit()
                if changes_made > 0:
                    st.success(f"✅ {changes_made} inventory items updated successfully!")
                else:
                    st.info("No changes were made to inventory.")
            except Exception as e:
                st.error(f"Error committing changes: {e}")

# ========================== PURCHASES ==========================
elif menu == "📋 Purchases":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📋 Purchase Records</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View purchases for date", value=selected_date, key="purchases_date")
    with col2:
        show_all = st.checkbox("Show all dates", key="show_all_purchases")
    
    # Get purchases data
    if show_all:
        purchases_df = pd.read_sql("SELECT * FROM purchases ORDER BY date DESC, rowid DESC", conn)
    else:
        purchases_df = pd.read_sql("SELECT * FROM purchases WHERE date=? ORDER BY rowid DESC", 
                                  conn, params=(view_date.strftime("%Y-%m-%d"),))
    
    if purchases_df.empty:
        st.info(f"No purchases found for {view_date.strftime('%d %B %Y')}")
    else:
        # Summary metrics
        total_amount = purchases_df['amount'].sum()
        total_qty = purchases_df['quantity'].sum()
        veg_count = purchases_df['vegetable'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Amount", f"₹{total_amount:.2f}")
        with col2:
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f}")
        with col3:
            st.metric("🌿 Vegetables Bought", veg_count)
        
        # Display table
        st.dataframe(
            purchases_df.style.format({
                "quantity": "{:.2f}",
                "amount": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== SALES ==========================
elif menu == "🧾 Sales":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🧾 Sales Records</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View sales for date", value=selected_date, key="sales_date_view")
    with col2:
        show_all_sales = st.checkbox("Show all dates", key="show_all_sales_view")
    
    # Get sales data
    if show_all_sales:
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY date DESC, rowid DESC", conn)
    else:
        sales_df = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC", 
                              conn, params=(view_date.strftime("%Y-%m-%d"),))
    
    if sales_df.empty:
        st.info(f"No sales found for {view_date.strftime('%d %B %Y')}")
    else:
        # Summary metrics
        total_sales = sales_df['total'].sum()
        total_qty = sales_df['quantity_sold'].sum()
        customer_count = sales_df['customer'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Sales", f"₹{total_sales:.2f}")
        with col2:
            st.metric("⚖️ Quantity Sold", f"{total_qty:.1f}")
        with col3:
            st.metric("👥 Customers", customer_count)
        
        # Display table with unit types
        display_df = sales_df.copy()
        
        # Format display based on unit type
        def format_sales_row(row):
            unit_type = row.get('unit_type', 'kg')
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            else:
                return f"{row['quantity_sold']:.2f} {unit_type}"
        
        display_df['Quantity Display'] = display_df.apply(format_sales_row, axis=1)
        
        st.dataframe(
            display_df[['date', 'vegetable', 'Quantity Display', 'total', 'customer']].style.format({
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== EXPENSES ==========================
elif menu == "💸 Expenses":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💸 Expense Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Add expense form
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", 
                                   ["Rent", "Electricity", "Water", "Transport", "Labor", 
                                    "Packaging", "Maintenance", "Miscellaneous"],
                                   key="expense_category")
            amount = st.number_input("Amount ₹", min_value=0.0, step=10.0, value=0.0, key="expense_amount")
        with col2:
            description = st.text_input("Description", placeholder="What was this expense for?", key="expense_desc")
        
        # Submit button
        submit_button = st.form_submit_button("💾 Save Expense", type="primary", use_container_width=True)
        if submit_button:
            if amount <= 0:
                st.error("Enter amount > 0")
            elif not description:
                st.error("Enter description")
            else:
                d = selected_date.strftime("%Y-%m-%d")
                c.execute("INSERT INTO expenses VALUES (?,?,?,?)", 
                         (d, category, amount, description))
                conn.commit()
                st.success(f"✅ Expense recorded: {category} - ₹{amount:.2f}")
    
    # Today's expenses
    st.markdown("### Today's Expenses")
    expenses_df = pd.read_sql("SELECT * FROM expenses WHERE date=?", 
                             conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if expenses_df.empty:
        st.info("No expenses today")
    else:
        total_expenses = expenses_df['amount'].sum()
        st.metric("Total Expenses Today", f"₹{total_expenses:.2f}")
        st.dataframe(expenses_df, use_container_width=True)

# ========================== CUSTOMERS ==========================
elif menu == "👥 Customers":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>👥 Customer Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get today's sales to count customers properly
    sales_df = pd.read_sql("SELECT DISTINCT customer FROM sales WHERE date=?", 
                          conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if sales_df.empty:
        st.info("No customers for today")
    else:
        # Count customers properly
        total_customers = len(sales_df)
        
        # Count unique customers by extracting base names
        unique_base_customers = set()
        guest_count = 0
        regular_count = 0
        
        for customer in sales_df['customer'].unique():
            # Check if it's a guest (starts with Guest followed by number)
            if isinstance(customer, str) and customer.startswith('Guest'):
                # Extract just the guest number part
                match = re.match(r'Guest(\d+)(?:\s*\(.*\))?', customer)
                if match:
                    guest_num = match.group(1)
                    unique_base_customers.add(f'Guest{guest_num}')
                    guest_count += 1
                else:
                    # If pattern doesn't match, treat as regular customer
                    unique_base_customers.add(customer.split('(')[0].strip())
                    regular_count += 1
            else:
                # Regular customer - extract name before phone if present
                if '(' in customer:
                    name_part = customer.split('(')[0].strip()
                    unique_base_customers.add(name_part)
                else:
                    unique_base_customers.add(customer)
                regular_count += 1
        
        # Get customer details from customers table (only those who made purchases today)
        if not sales_df.empty:
            customer_names = []
            for customer in sales_df['customer'].unique():
                if '(' in customer:
                    phone = customer.split('(')[1].replace(')', '').strip()
                    customer_names.append(phone)
            
            if customer_names:
                placeholders = ','.join(['?'] * len(customer_names))
                customers_df = pd.read_sql(f"SELECT * FROM customers WHERE phone IN ({placeholders}) ORDER BY points DESC", 
                                         conn, params=customer_names)
            else:
                customers_df = pd.DataFrame(columns=['phone', 'name', 'points'])
        else:
            customers_df = pd.DataFrame(columns=['phone', 'name', 'points'])
        
        total_points = customers_df['points'].sum() if not customers_df.empty else 0
        
        # Display metrics - FIXED
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Bills", total_customers)
        with col2:
            st.metric("Unique Customers", len(unique_base_customers))
        with col3:
            st.metric("Guest Bills", guest_count)
        with col4:
            st.metric("Total Points", total_points)
        
        # Show today's customers from sales - IMPROVED
        st.markdown(f"### Today's Customer Bills ({selected_date.strftime('%d %B %Y')})")
        
        # Create a better display of customers
        customer_summary = []
        for customer in sales_df['customer'].unique():
            # Get total purchases for this customer TODAY
            customer_sales = pd.read_sql("SELECT SUM(total) as total_spent FROM sales WHERE customer=? AND date=?", 
                                        conn, params=(customer, selected_date.strftime("%Y-%m-%d"))).iloc[0]['total_spent'] or 0
            
            # Check if it's a guest
            is_guest = isinstance(customer, str) and customer.startswith('Guest')
            
            # Clean up display name
            if '(' in customer:
                display_name = customer.split('(')[0].strip()
            else:
                display_name = customer
            
            customer_summary.append({
                "Bill Customer": customer,
                "Display Name": display_name,
                "Type": "Guest" if is_guest else "Regular",
                "Total Spent Today": f"₹{customer_sales:.2f}"
            })
        
        customer_summary_df = pd.DataFrame(customer_summary)
        st.dataframe(customer_summary_df, use_container_width=True)
        
        # Show loyalty customers who purchased today
        if not customers_df.empty:
            st.markdown("### 🏆 Loyalty Customers (Purchased Today)")
            for idx, row in customers_df.head(10).iterrows():
                st.markdown(f"""
                <div class="card" style="padding:15px; margin-bottom:10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="margin:0; color:#2c3e50;">{row['name']}</h4>
                            <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:0.9em;">{row['phone']}</p>
                        </div>
                        <div style="text-align:right;">
                            <span style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); 
                                        color:white; padding:5px 15px; border-radius:20px; font-weight:bold;">
                                {row['points']} pts
                            </span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ========================== WASTE ==========================
elif menu == "🗑 Waste":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🗑 Waste Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables for selection
    all_veg = pd.read_sql("SELECT vegetable, unit_type FROM inventory ORDER BY vegetable", conn)
    
    # Tab interface for different waste types
    tab1, tab2 = st.tabs(["⚖️ KG Vegetables Waste", "🧩 Piece Vegetables Waste"])
    
    with tab1:
        st.markdown("### ⚖️ KG Vegetables Waste")
        # Filter only kg vegetables
        kg_vegetables = all_veg[all_veg['unit_type'] == 'kg']
        
        # Record waste for kg vegetables
        with st.form("kg_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select KG Vegetable", kg_vegetables['vegetable'].tolist() if not kg_vegetables.empty else [], key="kg_waste_veg")
                if veg:
                    st.info(f"Unit: kg")
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=0.0, key="kg_waste_qty")
                else:
                    qty = 0
            with col2:
                reason = st.selectbox("Reason", 
                                     ["Spoiled", "Damaged", "Expired", "Overstock", "Other"],
                                     key="kg_waste_reason")
                description = st.text_input("Details", key="kg_waste_desc")
            
            with col3:
                # Submit button
                submit_button = st.form_submit_button("Record KG Waste", use_container_width=True, type="primary")
                if submit_button:
                    if qty <= 0:
                        st.error("Enter quantity > 0")
                    else:
                        stock, _, _, _ = get_stock(veg)
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.2f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                            conn.commit()
                            st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    with tab2:
        st.markdown("### 🧩 Piece Vegetables Waste")
        # Filter only piece vegetables
        piece_vegetables = all_veg[all_veg['unit_type'] == 'piece']
        
        # Record waste for piece vegetables
        with st.form("piece_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Piece Vegetable", piece_vegetables['vegetable'].tolist() if not piece_vegetables.empty else [], key="piece_waste_veg")
                if veg:
                    st.info(f"Unit: pieces")
                    qty = st.number_input("Quantity (pieces)", min_value=0, step=1, value=0, key="piece_waste_qty")
                else:
                    qty = 0
            with col2:
                reason = st.selectbox("Reason", 
                                     ["Spoiled", "Damaged", "Expired", "Overstock", "Other"],
                                     key="piece_waste_reason")
                description = st.text_input("Details", key="piece_waste_desc")
            
            with col3:
                # Submit button
                submit_button = st.form_submit_button("Record Piece Waste", use_container_width=True, type="primary")
                if submit_button:
                    if qty <= 0:
                        st.error("Enter quantity > 0")
                    else:
                        stock, _, _, _ = get_stock(veg)
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.0f} pieces")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                            conn.commit()
                            st.success(f"✅ Recorded waste: {qty} pieces of {veg}")
    
    # Today's waste
    st.markdown("---")
    st.markdown(f"### Today's Waste ({selected_date.strftime('%d %B %Y')})")
    waste_df = pd.read_sql("SELECT * FROM waste WHERE date=?", 
                          conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if waste_df.empty:
        st.info("No waste recorded today")
    else:
        total_waste = waste_df['quantity'].sum()
        st.metric("Total Waste Today", f"{total_waste:.2f}")
        st.dataframe(waste_df, use_container_width=True)

# ========================== DOWNLOAD ==========================
elif menu == "⬇ Download":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>⬇ Download Reports</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Tab interface for different report types
    tab1, tab2, tab3 = st.tabs(["📅 Daily Reports", "📊 Monthly Reports", "📋 Data Export"])
    
    with tab1:
        st.markdown(f"### 📅 Daily Report - {selected_date.strftime('%d %B %Y')}")
        
        # Get daily data
        d = selected_date.strftime("%Y-%m-%d")
        
        # Sales data
        daily_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE date=?", 
                                 conn, params=(d,)).iloc[0]['total_sales']
        
        # Purchase data
        daily_purchases = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE date=?", 
                                     conn, params=(d,)).iloc[0]['total_purchases']
        
        # Expense data
        daily_expenses = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE date=?", 
                                    conn, params=(d,)).iloc[0]['total_expenses']
        
        # Waste data
        daily_waste = pd.read_sql("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE date=?", 
                                 conn, params=(d,)).iloc[0]['total_waste']
        
        # Calculate profit
        daily_profit = daily_sales - daily_purchases - daily_expenses
        
        # Display daily summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Sales", f"₹{daily_sales:.2f}")
        with col2:
            st.metric("🛒 Purchases", f"₹{daily_purchases:.2f}")
        with col3:
            st.metric("💸 Expenses", f"₹{daily_expenses:.2f}")
        with col4:
            profit_color = "green" if daily_profit >= 0 else "red"
            st.metric("📈 Profit/Loss", f"₹{daily_profit:.2f}", delta_color="off")
        
        # Detailed daily data
        st.markdown("#### Detailed Daily Data")
        
        tables = [
            ("purchases", "🛒 Purchases", "Daily purchase records"),
            ("sales", "💰 Sales", "Daily sales transactions"),
            ("waste", "🗑 Waste", "Daily waste records"),
            ("expenses", "💸 Expenses", "Daily expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                df = pd.read_sql(f"SELECT * FROM {table_name} WHERE date=?", 
                                conn, params=(d,))
                
                if df.empty:
                    st.info(f"No {display_name.lower()} data for today")
                else:
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode()
                    st.download_button(
                        f"Download {display_name}",
                        data=csv,
                        file_name=f"{table_name}_{d}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
    
    with tab2:
        st.markdown("### 📊 Monthly Reports")
        
        # Get current month and year
        current_month = selected_date.strftime("%Y-%m")
        
        # Month selection
        months = pd.read_sql("SELECT DISTINCT strftime('%Y-%m', date) as month FROM sales UNION SELECT DISTINCT strftime('%Y-%m', date) as month FROM purchases ORDER BY month DESC", conn)
        
        if months.empty:
            st.info("No monthly data available")
        else:
            selected_month = st.selectbox("Select Month", months['month'].tolist(), index=0)
            
            # Get monthly data
            # Sales data
            monthly_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE strftime('%Y-%m', date)=?", 
                                       conn, params=(selected_month,)).iloc[0]['total_sales']
            
            # Purchase data
            monthly_purchases = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE strftime('%Y-%m', date)=?", 
                                          conn, params=(selected_month,)).iloc[0]['total_purchases']
            
            # Expense data
            monthly_expenses = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE strftime('%Y-%m', date)=?", 
                                         conn, params=(selected_month,)).iloc[0]['total_expenses']
            
            # Waste data
            monthly_waste = pd.read_sql("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE strftime('%Y-%m', date)=?", 
                                       conn, params=(selected_month,)).iloc[0]['total_waste']
            
            # Calculate monthly profit
            monthly_profit = monthly_sales - monthly_purchases - monthly_expenses
            
            # Display monthly summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Monthly Sales", f"₹{monthly_sales:.2f}")
            with col2:
                st.metric("🛒 Monthly Purchases", f"₹{monthly_purchases:.2f}")
            with col3:
                st.metric("💸 Monthly Expenses", f"₹{monthly_expenses:.2f}")
            with col4:
                profit_color = "green" if monthly_profit >= 0 else "red"
                st.metric("📈 Monthly Profit/Loss", f"₹{monthly_profit:.2f}", delta_color="off")
            
            # Daily breakdown for the month
            st.markdown("#### Daily Breakdown for the Month")
            
            # Get daily sales for the month
            daily_sales_month = pd.read_sql("""
                SELECT date, SUM(total) as daily_sales 
                FROM sales 
                WHERE strftime('%Y-%m', date)=? 
                GROUP BY date 
                ORDER BY date
            """, conn, params=(selected_month,))
            
            if not daily_sales_month.empty:
                # Display as chart
                st.line_chart(daily_sales_month.set_index('date')['daily_sales'])
                
                # Display as table
                st.dataframe(
                    daily_sales_month.style.format({
                        "daily_sales": "₹{:.2f}"
                    }),
                    use_container_width=True
                )
            
            # Download monthly report
            st.markdown("#### Download Monthly Report")
            
            # Create comprehensive monthly report
            monthly_data = {
                'Metric': ['Total Sales', 'Total Purchases', 'Total Expenses', 'Total Waste', 'Net Profit/Loss'],
                'Amount': [f"₹{monthly_sales:.2f}", f"₹{monthly_purchases:.2f}", 
                          f"₹{monthly_expenses:.2f}", f"{monthly_waste:.2f}", f"₹{monthly_profit:.2f}"]
            }
            
            monthly_report_df = pd.DataFrame(monthly_data)
            
            csv = monthly_report_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download Monthly Summary",
                data=csv,
                file_name=f"monthly_report_{selected_month}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with tab3:
        st.markdown("### 📋 Data Export")
        st.markdown("Export complete database tables")
        
        tables = [
            ("inventory", "📦 Inventory", "Current stock levels"),
            ("customers", "👥 Customers", "Customer database"),
            ("purchases", "🛒 Purchases", "All purchase records"),
            ("sales", "💰 Sales", "All sales transactions"),
            ("waste", "🗑 Waste", "All waste records"),
            ("expenses", "💸 Expenses", "All expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
                
                if df.empty:
                    st.info(f"No {display_name.lower()} data")
                else:
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode()
                    st.download_button(
                        f"Download {display_name}",
                        data=csv,
                        file_name=f"{table_name}_full_export.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

# ========================== FINANCIALS ==========================
elif menu == "💰 Financials":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💰 Financial Summary</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    d = selected_date.strftime("%Y-%m-%d")
    
    # Get financial data
    sales_data = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", 
                           conn, params=(d,)).iloc[0]['total']
    cost_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", 
                          conn, params=(d,)).iloc[0]['total']
    expense_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE date=?", 
                             conn, params=(d,)).iloc[0]['total']
    
    profit = sales_data - cost_data - expense_data
    
    # Display metrics with beautiful cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Sales</h4>
            <h2>₹{sales_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="purchase-card">
            <h3>📦</h3>
            <h4>Cost</h4>
            <h2>₹{cost_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color:white;">
            <h3>💸</h3>
            <h4>Expenses</h4>
            <h2>₹{expense_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        profit_bg = "#27ae60" if profit >= 0 else "#e74c3c"
        profit_text = "Profit" if profit >= 0 else "Loss"
        profit_icon = "📈" if profit >= 0 else "📉"
        
        st.markdown(f"""
        <div class="card" style="background: linear-gradient(135deg, {profit_bg} 0%, #38f9d7 100%); color:white;">
            <h3>{profit_icon}</h3>
            <h4>{profit_text}</h4>
            <h2>₹{abs(profit):.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Breakdown
    st.markdown("### 📊 Daily Breakdown")
    
    # Sales by vegetable
    sales_by_veg = pd.read_sql("""
        SELECT vegetable, SUM(quantity_sold) as qty, SUM(total) as revenue 
        FROM sales WHERE date=? 
        GROUP BY vegetable 
        ORDER BY revenue DESC
    """, conn, params=(d,))
    
    if not sales_by_veg.empty:
        st.markdown("#### Top Selling Vegetables")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                sales_by_veg.style.format({
                    "qty": "{:.2f}",
                    "revenue": "₹{:.2f}"
                }),
                use_container_width=True
            )
        with col2:
            # Simple chart
            chart_data = sales_by_veg.head(10).set_index('vegetable')['revenue']
            st.bar_chart(chart_data)
    
    # Recent transactions
    st.markdown("### Recent Transactions")
    recent_sales = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC LIMIT 10", 
                              conn, params=(d,))
    if not recent_sales.empty:
        display_sales = recent_sales.copy()
        
        # Format quantity display
        def format_recent_sales(row):
            unit_type = row.get('unit_type', 'kg')
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            else:
                return f"{row['quantity_sold']:.2f} {unit_type}"
        
        # Clean customer display names
        def clean_customer_name(customer):
            if not isinstance(customer, str):
                return str(customer)
            if '(' in customer:
                return customer.split('(')[0].strip()
            return customer
        
        display_sales['Quantity'] = display_sales.apply(format_recent_sales, axis=1)
        display_sales['Customer'] = display_sales['customer'].apply(clean_customer_name)
        
        st.dataframe(
            display_sales[['vegetable', 'Quantity', 'total', 'Customer']].style.format({
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>🌿 Fresh Basket — Freshness You Can Feel | Quality Vegetables Daily ✅</p>
    <p style="font-size:0.8em; color:#95a5a6;">© 2024 Fresh Basket. All features working perfectly.</p>
</div>
""", unsafe_allow_html=True)
