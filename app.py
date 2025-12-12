import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import random

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🥕", layout="wide")

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
    h1 {text-align:center; color:#2c3e50; font-size:2.8em; margin-bottom:10px;}
    .subtitle {text-align:center; color:#7f8c8d; font-size:1.2em; margin-bottom:30px;}
    
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
    
    .primary-btn {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color:white !important;}
    .secondary-btn {background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important; color:white !important;}
    .success-btn {background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%) !important; color:white !important;}
    .warning-btn {background: linear-gradient(135deg, #fa709a 0%, #fee140 100%) !important; color:black !important;}
    .info-btn {background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%) !important; color:#2c3e50 !important;}
    
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
    }
    
    .inventory-card {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(67, 233, 123, 0.3);
    }
    
    .sales-card {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(250, 112, 154, 0.3);
    }
    
    .purchase-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: #2c3e50;
        box-shadow: 0 8px 25px rgba(168, 237, 234, 0.3);
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: linear-gradient(135deg, #2c3e50 0%, #4a6491 100%) !important;
    }
    
    /* Receipt */
    .receipt {
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
        border: 2px solid #667eea;
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
        border-left: 4px solid #667eea;
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
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div style="text-align:center; margin-bottom:30px;">
    <h1>🥕 Fresh Basket</h1>
    <div class="subtitle">Your Brother's Smart Vegetable Shop Management</div>
</div>
""", unsafe_allow_html=True)

# ========================== DATABASE ==========================
DB_FILE = "shop.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    vegetable TEXT PRIMARY KEY,
    quantity REAL,
    cost_price REAL,
    selling_price REAL,
    image_url TEXT
)
""")
c.execute("CREATE TABLE IF NOT EXISTS purchases (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS sales (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS waste (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)")
c.execute("CREATE TABLE IF NOT EXISTS expenses (date TEXT, category TEXT, amount REAL, description TEXT)")
conn.commit()

# ========================== DEFAULT VEGETABLES ==========================
default_vegetables = [
    "Potato", "Onion", "Tomato", "Carrot", "Cucumber", "Spinach", 
    "Broccoli", "Cauliflower", "Cabbage", "Capsicum", "Brinjal", 
    "Green Beans", "Peas", "Radish", "Lettuce", "Celery", 
    "Sweet Potato", "Corn", "Garlic", "Ginger", "Mushroom", 
    "Pumpkin", "Lady Finger", "Beetroot", "Leek"
]

# Initialize default vegetables if not exists
for veg in default_vegetables:
    c.execute("INSERT OR IGNORE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?, 0, 0, 0, '')", (veg,))
conn.commit()

# ========================== HELPERS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price) for veg (or zeros)."""
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable=?", (veg,))
    row = c.fetchone()
    if row:
        qty = row[0] or 0.0
        cost = row[1] or 0.0
        sell = row[2] or 0.0
        return qty, cost, sell
    return 0.0, 0.0, 0.0

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

def convert_to_display(qty):
    """Convert kg to kg and grams display"""
    kg = int(qty)
    grams = round((qty - kg) * 1000)
    if grams > 0:
        return f"{kg} kg {grams} g" if kg > 0 else f"{grams} g"
    return f"{kg} kg"

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
    st.session_state.guest_counter = 1

# ========================== HELPER FUNCTIONS FOR SELL PAGE ==========================
def add_to_cart(veg, qty, price):
    """Add item to cart"""
    if qty <= 0:
        return
    
    # Check stock
    stock, _, _ = get_stock(veg)
    current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
    
    if current_in_cart + qty > stock:
        st.error(f"Not enough stock! Available: {stock:.3f} kg")
        return
    
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
        st.session_state.cart.append([veg, qty, price, total])
    
    st.success(f"✅ Added {qty:.3f} kg of {veg}")
    st.rerun()

def update_cart_item(idx, delta):
    """Update cart item quantity"""
    if 0 <= idx < len(st.session_state.cart):
        veg = st.session_state.cart[idx][0]
        price = st.session_state.cart[idx][2]
        
        # Check stock for increase
        if delta > 0:
            stock, _, _ = get_stock(veg)
            total_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
            if total_in_cart + delta > stock:
                st.error(f"Not enough stock! Available: {stock:.3f} kg")
                return
        
        new_qty = st.session_state.cart[idx][1] + delta
        if new_qty <= 0:
            st.session_state.cart.pop(idx)
        else:
            st.session_state.cart[idx][1] = new_qty
            st.session_state.cart[idx][3] = round(new_qty * price, 2)
        
        st.rerun()

def process_sale(cust_name, cust_phone, total_amount):
    """Process the sale"""
    # Validate stock
    insufficient = []
    for veg, qty, price, total in st.session_state.cart:
        if veg == "DISCOUNT":
            continue
        stock, _, _ = get_stock(veg)
        if qty > stock:
            insufficient.append((veg, stock, qty))
    
    if insufficient:
        for v, stock, q in insufficient:
            st.error(f"Not enough {v}: available {stock:.3f} kg, requested {q:.3f} kg")
        return
    
    # Process sale
    d = st.session_state.selected_date.strftime("%Y-%m-%d")
    
    # Handle customer name
    if not cust_name or cust_name.strip() == "":
        cust_name = f"Guest{st.session_state.guest_counter}"
        st.session_state.guest_counter += 1
    
    cust = f"{cust_name} ({cust_phone})" if cust_phone else cust_name
    
    sale_details = []
    for item in st.session_state.cart:
        veg, qty, price, total = item
        
        if veg == "DISCOUNT":
            # Skip discount from database insert
            continue
        
        # Save to sales table
        c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", 
                 (d, veg, qty, price, total, cust))
        
        # Update inventory
        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
        
        sale_details.append({
            "item": veg,
            "quantity": qty,
            "price_per_kg": price,
            "total": total
        })
    
    # Update customer points
    if cust_phone and cust_phone.strip() != "":
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
        "total": total_amount,
        "phone": cust_phone
    }
    
    # Clear cart
    st.session_state.cart = []
    st.rerun()

def show_receipt():
    """Display receipt after sale"""
    sale = st.session_state.last_sale
    if not sale:
        return
    
    st.markdown("""
    <div style="text-align:center; margin:30px 0;">
        <h2 style="color:#667eea;">✅ Sale Completed Successfully!</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Receipt
    with st.container():
        st.markdown("""
        <div class="receipt">
            <div style="text-align:center; margin-bottom:20px;">
                <h2 style="color:#2c3e50;">🥕 FRESH BASKET</h2>
                <p style="color:#7f8c8d; margin:5px 0;">Your Brother's Vegetable Shop</p>
                <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">📍 Shop Address</p>
                <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">📞 Contact: 9876543210</p>
            </div>
            <hr style="border:none; height:2px; background: linear-gradient(90deg, #667eea, #764ba2); margin:15px 0;">
        """, unsafe_allow_html=True)
        
        # Sale info
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📅 Date:** {sale['date']}")
            st.markdown(f"**👤 Customer:** {sale['customer']}")
        with col2:
            st.markdown(f"**⏰ Time:** {datetime.now().strftime('%H:%M:%S')}")
            st.markdown(f"**📋 Bill No:** {datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        st.markdown("<hr style='border:none; height:1px; background:#e0e0e0; margin:15px 0;'>", unsafe_allow_html=True)
        
        # Items table
        st.markdown("### 🛒 Items Purchased")
        
        items_df = pd.DataFrame(sale['items'])
        items_df['Qty Display'] = items_df['quantity'].apply(convert_to_display)
        items_display = items_df[['item', 'Qty Display', 'price_per_kg', 'total']]
        items_display.columns = ['Item', 'Quantity', 'Price/kg', 'Total']
        
        # Apply styling to the dataframe
        st.dataframe(
            items_display.style
            .set_properties(**{'background-color': '#f8f9fa', 'color': '#2c3e50'})
            .set_table_styles([
                {'selector': 'th', 'props': [('background', '#667eea'), ('color', 'white'), 
                                            ('font-weight', 'bold'), ('text-align', 'center')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ]),
            use_container_width=True,
            hide_index=True
        )
        
        # Total
        st.markdown("<hr style='border:none; height:2px; background: linear-gradient(90deg, #667eea, #764ba2); margin:20px 0;'>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col2:
            st.markdown(f"<h3 style='text-align:right; color:#2c3e50;'>Total: ₹{sale['total']:.2f}</h3>", unsafe_allow_html=True)
        
        st.markdown("""
        <hr style='border:none; height:1px; background:#e0e0e0; margin:20px 0;'>
        <div style="text-align:center; margin-top:20px;">
            <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">
                Thank you for your purchase! 🥕
            </p>
            <p style="color:#7f8c8d; font-size:0.8em; margin:5px 0;">
                Bring this receipt for any queries
            </p>
        </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🖨️ Print Receipt", use_container_width=True, type="primary"):
            st.success("Receipt ready for printing! Press Ctrl+P to print.")
    with col2:
        if st.button("📱 Share Receipt", use_container_width=True):
            st.info("Receipt sharing feature coming soon!")
    with col3:
        if st.button("🔄 New Sale", use_container_width=True):
            st.session_state.last_sale = None
            st.rerun()
    
    st.balloons()

# ========================== SIDEBAR MENU ==========================
with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #2c3e50 0%, #4a6491 100%); padding:20px; border-radius:15px; margin-bottom:20px;">
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
        <h4 style="color:#667eea;">Selected Date</h4>
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

# ========================== DASHBOARD ==========================
if menu == "📊 Dashboard":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📊 Dashboard Overview</h2>
        <p class="subtitle">Real-time insights and stock overview</p>
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
        # Today's Customers
        today_customers = pd.read_sql("SELECT COUNT(DISTINCT customer) as count FROM sales WHERE date=?", 
                                     conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['count']
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
    
    # Current Stock Details
    st.markdown("### 📋 Current Stock Details")
    
    # Set shortage threshold
    threshold = st.slider("Low Stock Alert Threshold (kg)", 0.0, 20.0, 5.0, 0.5, 
                         help="Items below this quantity will be marked as low stock")
    st.session_state.shortage_threshold = threshold
    
    # Get inventory data
    inv_df = pd.read_sql("""
        SELECT vegetable, quantity, selling_price 
        FROM inventory 
        WHERE quantity > 0 
        ORDER BY vegetable
    """, conn)
    
    if inv_df.empty:
        st.info("No stock available. Add purchases first.")
    else:
        # Create a styled dataframe
        inv_display = inv_df.copy()
        inv_display = inv_display.rename(columns={
            "vegetable": "🥬 Vegetable",
            "quantity": "⚖️ Stock (kg)",
            "selling_price": "💰 Price/kg"
        })
        
        # Apply color coding based on stock levels
        def highlight_stock(val):
            if val < threshold:
                return 'background-color: #ffcccc; color: #d63031; font-weight: bold'
            elif val < threshold * 2:
                return 'background-color: #fff3cd; color: #856404'
            else:
                return 'background-color: #d4edda; color: #155724'
        
        styled_df = inv_display.style.applymap(highlight_stock, subset=['⚖️ Stock (kg)'])
        
        # Display the table
        st.dataframe(
            styled_df.format({
                "⚖️ Stock (kg)": "{:.2f}",
                "💰 Price/kg": "₹{:.2f}"
            }),
            use_container_width=True,
            height=400
        )
        
        # Summary
        col1, col2 = st.columns(2)
        with col1:
            out_of_stock = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity = 0", conn).iloc[0]['count']
            st.info(f"**Out of Stock:** {out_of_stock} items")
        
        with col2:
            low_stock = inv_df[inv_df['quantity'] < threshold]
            if not low_stock.empty:
                st.warning(f"**Low Stock ({threshold} kg):** {len(low_stock)} items")

# ========================== ADD PURCHASE ==========================
elif menu == "🛒 Add Purchase":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🛒 Add Purchase</h2>
        <p class="subtitle">Add new stock purchases easily</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables from inventory
    all_veg_df = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
    
    if all_veg_df.empty:
        st.info("No vegetables in inventory. Please add vegetables first.")
    else:
        # Tab interface for different purchase methods
        tab1, tab2 = st.tabs(["📝 Bulk Purchase Entry", "➕ Individual Purchase"])
        
        with tab1:
            st.markdown("### 📝 Bulk Purchase Entry")
            st.markdown("Edit all vegetables in table format")
            
            # Create editable dataframe
            purchase_df = pd.read_sql("SELECT vegetable, quantity as current_stock, selling_price FROM inventory ORDER BY vegetable", conn)
            purchase_df['New Purchase (kg)'] = 0.0
            purchase_df['Amount (₹)'] = 0.0
            purchase_df['Supplier'] = ""
            
            edited_df = st.data_editor(
                purchase_df[['vegetable', 'current_stock', 'New Purchase (kg)', 'Amount (₹)', 'Supplier']],
                column_config={
                    "vegetable": st.column_config.TextColumn("🥬 Vegetable", disabled=True),
                    "current_stock": st.column_config.NumberColumn("📦 Current Stock (kg)", disabled=True, format="%.2f"),
                    "New Purchase (kg)": st.column_config.NumberColumn("🛒 Purchase Qty (kg)", min_value=0.0, step=0.5, format="%.2f"),
                    "Amount (₹)": st.column_config.NumberColumn("💰 Amount (₹)", min_value=0.0, step=10.0, format="₹%.2f"),
                    "Supplier": st.column_config.TextColumn("👨‍🌾 Supplier", max_chars=50)
                },
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True
            )
            
            if st.button("💾 Save All Purchases", type="primary", use_container_width=True):
                purchases_made = 0
                for _, row in edited_df.iterrows():
                    if row['New Purchase (kg)'] > 0 and row['Amount (₹)'] > 0:
                        d = selected_date.strftime("%Y-%m-%d")
                        veg = row['vegetable']
                        qty = row['New Purchase (kg)']
                        amount = row['Amount (₹)']
                        supplier = row['Supplier']
                        
                        # Save purchase
                        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                 (d, veg, qty, amount, supplier))
                        
                        # Update inventory
                        old_qty, old_cost, _ = get_stock(veg)
                        new_qty = old_qty + qty
                        unit_cost = (amount / qty) if qty > 0 else old_cost
                        c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                 (new_qty, unit_cost, veg))
                        
                        purchases_made += 1
                
                conn.commit()
                if purchases_made > 0:
                    st.success(f"✅ {purchases_made} purchases saved successfully!")
                else:
                    st.warning("No purchases were saved. Make sure to enter quantity and amount.")
        
        with tab2:
            st.markdown("### ➕ Individual Purchase")
            st.markdown("Add purchase for a single vegetable")
            
            with st.form("individual_purchase", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Vegetable selection with option to add new
                    existing_veg = all_veg_df['vegetable'].tolist()
                    veg_choice = st.selectbox("Select Vegetable", existing_veg)
                    new_veg_option = st.checkbox("Add New Vegetable")
                    
                    if new_veg_option:
                        new_veg = st.text_input("New Vegetable Name")
                        veg = new_veg if new_veg else veg_choice
                    else:
                        veg = veg_choice
                    
                    # Quantity
                    q_col1, q_col2 = st.columns(2)
                    with q_col1:
                        qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.5, value=1.0)
                    with q_col2:
                        qty_g = st.number_input("Grams", min_value=0, step=100, value=0, max_value=999)
                    
                    total_qty = qty_kg + (qty_g / 1000)
                
                with col2:
                    amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0)
                    supplier = st.text_input("Supplier Name")
                    unit_price = amount / total_qty if total_qty > 0 else 0
                    st.info(f"Unit Price: ₹{unit_price:.2f}/kg")
                
                if st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True):
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
                        old_qty, old_cost, old_sell = get_stock(veg)
                        new_qty = old_qty + total_qty
                        unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                        
                        if old_qty == 0 and veg not in existing_veg:
                            # New vegetable
                            c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price) VALUES (?,?,?,?)", 
                                     (veg, new_qty, unit_cost, 0.0))
                        else:
                            c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                     (new_qty, unit_cost, veg))
                        
                        conn.commit()
                        st.success(f"✅ Added {total_qty:.3f} kg of {veg}")
    
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
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f} kg")
        with col3:
            st.metric("🥬 Vegetables Bought", veg_count)
        
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
        <p class="subtitle">Update vegetable selling prices</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables
    price_df = pd.read_sql("SELECT vegetable, selling_price FROM inventory ORDER BY vegetable", conn)
    
    if price_df.empty:
        st.info("No vegetables in inventory")
    else:
        # Add new vegetable option
        st.markdown("### ➕ Add New Vegetable")
        with st.form("add_new_veg"):
            new_veg = st.text_input("New Vegetable Name")
            new_price = st.number_input("Initial Selling Price/kg ₹", min_value=0.0, step=1.0, value=0.0)
            
            if st.form_submit_button("➕ Add Vegetable", use_container_width=True):
                if new_veg and new_veg.strip():
                    c.execute("INSERT OR IGNORE INTO inventory (vegetable, quantity, cost_price, selling_price) VALUES (?, 0, 0, ?)", 
                             (new_veg.strip(), new_price))
                    conn.commit()
                    st.success(f"✅ Added {new_veg.strip()} to inventory")
                    st.rerun()
                else:
                    st.error("Enter vegetable name")
        
        st.markdown("---")
        
        # Bulk price editor
        st.markdown("### 📝 Bulk Price Update")
        edited_df = st.data_editor(
            price_df,
            column_config={
                "vegetable": st.column_config.TextColumn("🥬 Vegetable", disabled=True),
                "selling_price": st.column_config.NumberColumn(
                    "💰 Price/kg (₹)",
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

# ========================== QUICK SELL ==========================
elif menu == "💵 Quick Sell":
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2>💵 Quick Selling</h2>
        <p class="subtitle">Fast and easy billing for multiple customers</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get available vegetables with stock
    available_veg = pd.read_sql("""
        SELECT vegetable, quantity, selling_price 
        FROM inventory 
        WHERE quantity > 0 AND selling_price > 0 
        ORDER BY vegetable
    """, conn)
    
    if available_veg.empty:
        st.warning("""
        <div class="alert-warning">
            <h4>⚠️ No vegetables available for sale!</h4>
            <p>Please add purchases and set prices first.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Customer info - Simple and clean
        st.markdown("### 👤 Customer Information")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            cust_name = st.text_input("Customer Name", placeholder="Leave empty for Guest", key="cust_name")
            if cust_name and cust_name.strip():
                cust_phone = st.text_input("Phone Number", placeholder="Optional", key="cust_phone")
            else:
                cust_phone = ""
        
        with col2:
            st.markdown("### Quick Actions")
            if st.button("🔄 Clear All", use_container_width=True, type="secondary"):
                st.session_state.cart = []
                st.rerun()
            
            if st.session_state.cart:
                total_amount = sum(item[3] for item in st.session_state.cart)
                st.markdown(f"""
                <div class="card" style="text-align:center; padding:15px; margin-top:10px;">
                    <h4 style="color:#667eea;">Cart Total</h4>
                    <h3 style="color:#2c3e50;">₹{total_amount:.2f}</h3>
                    <p style="color:#7f8c8d; font-size:0.9em;">{len(st.session_state.cart)} items</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Main selling interface - SIMPLE 2-COLUMN LAYOUT
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("### 🥬 Select Vegetables")
            
            # Simple search and filter
            search_term = st.text_input("🔍 Search vegetable", placeholder="Type to filter...")
            
            # Filter vegetables based on search
            if search_term:
                filtered_veg = available_veg[available_veg['vegetable'].str.contains(search_term, case=False, na=False)]
            else:
                filtered_veg = available_veg
            
            # Display vegetables in a simple list
            for _, row in filtered_veg.iterrows():
                veg = row['vegetable']
                stock = row['quantity']
                price = row['selling_price']
                
                # Calculate current in cart
                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
                available = stock - current_in_cart
                
                # Create a card for each vegetable
                with st.container():
                    st.markdown(f"""
                    <div class="card" style="padding:15px; margin-bottom:10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin:0; color:#2c3e50;">{veg}</h4>
                                <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:0.9em;">
                                    Stock: {stock:.2f} kg | Price: ₹{price:.2f}/kg
                                </p>
                                {f'<p style="margin:5px 0 0 0; color:#667eea; font-size:0.9em;">In cart: {current_in_cart:.2f} kg</p>' if current_in_cart > 0 else ''}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Quantity controls
                    if available > 0:
                        col_a, col_b, col_c, col_d, col_e = st.columns([2, 1, 1, 1, 1])
                        
                        with col_a:
                            # Manual input
                            manual_input = st.number_input(
                                "Quantity (kg)",
                                min_value=0.0,
                                max_value=min(available, 10.0),
                                value=0.0,
                                step=0.1,
                                key=f"manual_{veg}"
                            )
                        
                        with col_b:
                            if st.button("➕ 250g", key=f"btn_250_{veg}", use_container_width=True):
                                add_to_cart(veg, 0.250, price)
                        
                        with col_c:
                            if st.button("➕ 500g", key=f"btn_500_{veg}", use_container_width=True):
                                add_to_cart(veg, 0.500, price)
                        
                        with col_d:
                            if st.button("➕ 1kg", key=f"btn_1_{veg}", use_container_width=True):
                                add_to_cart(veg, 1.000, price)
                        
                        with col_e:
                            if manual_input > 0 and st.button("➕ Add", key=f"add_manual_{veg}", use_container_width=True):
                                add_to_cart(veg, manual_input, price)
                    else:
                        st.warning("Out of stock", icon="⚠️")
        
        with col2:
            st.markdown("### 🛒 Current Cart")
            
            if not st.session_state.cart:
                st.info("""
                <div style="text-align:center; padding:40px;">
                    <h3 style="color:#7f8c8d;">🛒 Cart is Empty</h3>
                    <p style="color:#95a5a6;">Select vegetables from the left</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Display cart items
                total_amount = 0
                
                for idx, item in enumerate(st.session_state.cart):
                    veg, qty, price, total = item
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="cart-item">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div>
                                    <strong>{veg}</strong><br>
                                    <small>{qty:.3f} kg × ₹{price:.2f}</small>
                                </div>
                                <div style="text-align:right;">
                                    <strong>₹{total:.2f}</strong>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Quick edit buttons
                        edit_col1, edit_col2, edit_col3 = st.columns(3)
                        with edit_col1:
                            if st.button("➕ 100g", key=f"inc_small_{veg}_{idx}", use_container_width=True):
                                update_cart_item(idx, 0.100)
                        with edit_col2:
                            if st.button("➖ 100g", key=f"dec_small_{veg}_{idx}", use_container_width=True):
                                update_cart_item(idx, -0.100)
                        with edit_col3:
                            if st.button("❌ Remove", key=f"rem_{veg}_{idx}", use_container_width=True, type="secondary"):
                                st.session_state.cart.pop(idx)
                                st.rerun()
                    
                    total_amount += total
                
                # Cart summary
                st.markdown("---")
                
                # Discount options
                st.markdown("#### 🎁 Apply Discount")
                disc_col1, disc_col2, disc_col3 = st.columns(3)
                with disc_col1:
                    if st.button("5% OFF", use_container_width=True):
                        discount = total_amount * 0.05
                        st.session_state.cart.append(["DISCOUNT", 1, -discount, -discount])
                        st.rerun()
                with disc_col2:
                    if st.button("10% OFF", use_container_width=True):
                        discount = total_amount * 0.10
                        st.session_state.cart.append(["DISCOUNT", 1, -discount, -discount])
                        st.rerun()
                with disc_col3:
                    if st.button("₹20 OFF", use_container_width=True):
                        st.session_state.cart.append(["DISCOUNT", 1, -20, -20])
                        st.rerun()
                
                # Final total
                final_total = sum(item[3] for item in st.session_state.cart)
                st.markdown(f"""
                <div class="card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color:white; text-align:center; padding:20px;">
                    <h3 style="margin:0;">Total Amount</h3>
                    <h1 style="margin:10px 0;">₹{final_total:.2f}</h1>
                </div>
                """, unsafe_allow_html=True)
                
                # Complete sale button - FIXED: Removed duplicate use_container_width
                if st.button("✅ COMPLETE SALE & PRINT BILL", type="primary", use_container_width=True):
                    process_sale(cust_name, cust_phone, final_total)
        
        # Show receipt if last sale exists
        if st.session_state.last_sale:
            show_receipt()

# ========================== INVENTORY ==========================
elif menu == "📦 Inventory":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📦 Inventory Management</h2>
        <p class="subtitle">Manage vegetable stock and edit inventory</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Edit vegetables list
    st.markdown("### ✏️ Manage Vegetables List")
    with st.expander("Add/Remove Vegetables", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Add new vegetable
            st.markdown("#### ➕ Add New Vegetable")
            new_veg_name = st.text_input("Vegetable Name")
            initial_qty = st.number_input("Initial Quantity (kg)", min_value=0.0, step=0.5, value=0.0)
            initial_price = st.number_input("Initial Price/kg ₹", min_value=0.0, step=1.0, value=0.0)
            
            if st.button("Add to Inventory", use_container_width=True):
                if new_veg_name and new_veg_name.strip():
                    c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price) VALUES (?,?,?,?)", 
                             (new_veg_name.strip(), initial_qty, 0.0, initial_price))
                    conn.commit()
                    st.success(f"✅ Added {new_veg_name.strip()} to inventory")
                    st.rerun()
        
        with col2:
            # Remove vegetable
            st.markdown("#### 🗑️ Remove Vegetable")
            all_veg = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
            
            if not all_veg.empty:
                veg_to_remove = st.selectbox("Select vegetable to remove", all_veg['vegetable'])
                confirm = st.checkbox("I confirm I want to remove this vegetable")
                
                if st.button("Remove from Inventory", use_container_width=True, type="secondary", disabled=not confirm):
                    # Check if vegetable has stock
                    stock, _, _ = get_stock(veg_to_remove)
                    if stock > 0:
                        st.error(f"Cannot remove {veg_to_remove} - it still has {stock:.2f} kg in stock")
                    else:
                        c.execute("DELETE FROM inventory WHERE vegetable=?", (veg_to_remove,))
                        conn.commit()
                        st.success(f"✅ Removed {veg_to_remove} from inventory")
                        st.rerun()
    
    # Current inventory
    st.markdown("### 📋 Current Inventory")
    
    inv_df = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory ORDER BY vegetable", conn)
    
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
                "vegetable": st.column_config.TextColumn("🥬 Vegetable", disabled=True),
                "quantity": st.column_config.NumberColumn(
                    "⚖️ Quantity (kg)",
                    min_value=0.0,
                    step=0.5,
                    format="%.2f"
                ),
                "selling_price": st.column_config.NumberColumn(
                    "💰 Price/kg (₹)",
                    min_value=0.0,
                    step=1.0,
                    format="₹%.2f"
                )
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True
        )
        
        if st.button("💾 Save Inventory Changes", type="primary", use_container_width=True):
            for _, row in edited_inv.iterrows():
                c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                         (row['quantity'], row['selling_price'], row['vegetable']))
            conn.commit()
            st.success("✅ Inventory updated successfully!")

# ========================== PURCHASES ==========================
elif menu == "📋 Purchases":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📋 Purchase Records</h2>
        <p class="subtitle">View and manage purchase history</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View purchases for date", value=selected_date)
    with col2:
        show_all = st.checkbox("Show all dates")
    
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
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f} kg")
        with col3:
            st.metric("🥬 Vegetables Bought", veg_count)
        
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
        <p class="subtitle">View sales history and transactions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View sales for date", value=selected_date, key="sales_date")
    with col2:
        show_all_sales = st.checkbox("Show all dates", key="show_all_sales")
    
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
            st.metric("⚖️ Quantity Sold", f"{total_qty:.1f} kg")
        with col3:
            st.metric("👥 Customers", customer_count)
        
        # Display table
        st.dataframe(
            sales_df.style.format({
                "quantity_sold": "{:.2f}",
                "sale_price": "₹{:.2f}",
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== EXPENSES ==========================
elif menu == "💸 Expenses":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💸 Expense Management</h2>
        <p class="subtitle">Record and track shop expenses</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add expense form
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", 
                                   ["Rent", "Electricity", "Water", "Transport", "Labor", 
                                    "Packaging", "Maintenance", "Miscellaneous"])
            amount = st.number_input("Amount ₹", min_value=0.0, step=10.0, value=0.0)
        with col2:
            description = st.text_input("Description", placeholder="What was this expense for?")
        
        if st.form_submit_button("💾 Save Expense", type="primary", use_container_width=True):
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
        <p class="subtitle">View customer details and loyalty points</p>
    </div>
    """, unsafe_allow_html=True)
    
    customers_df = pd.read_sql("SELECT * FROM customers ORDER BY points DESC", conn)
    
    # Calculate customer counts
    total_customers = len(customers_df)
    
    # Count named customers (excluding guests)
    named_customers = len(customers_df[~customers_df['name'].str.contains('Guest', na=False)])
    
    # Count guest customers
    guest_customers = len(customers_df[customers_df['name'].str.contains('Guest', na=False)])
    
    if customers_df.empty:
        st.info("No customers yet")
    else:
        # Summary metrics
        total_points = customers_df['points'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Customers", total_customers)
        with col2:
            st.metric("Named Customers", named_customers)
        with col3:
            st.metric("Guest Customers", guest_customers)
        with col4:
            st.metric("Total Points", total_points)
        
        # Top customers
        st.markdown("### 🏆 Top 5 Customers")
        top_5 = customers_df.head(5)
        for idx, row in top_5.iterrows():
            st.markdown(f"""
            <div class="card" style="padding:15px; margin-bottom:10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin:0; color:#2c3e50;">{row['name']}</h4>
                        <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:0.9em;">{row['phone']}</p>
                    </div>
                    <div style="text-align:right;">
                        <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    color:white; padding:5px 15px; border-radius:20px; font-weight:bold;">
                            {row['points']} pts
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # All customers table
        st.markdown("### All Customers")
        st.dataframe(customers_df, use_container_width=True)

# ========================== WASTE ==========================
elif menu == "🗑 Waste":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🗑 Waste Management</h2>
        <p class="subtitle">Record and track vegetable waste</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Record waste
    with st.form("waste_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            veg = st.selectbox("Vegetable", default_vegetables)
            qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=0.0)
        with col2:
            reason = st.selectbox("Reason", 
                                 ["Spoiled", "Damaged", "Expired", "Overstock", "Other"])
            description = st.text_input("Details")
        
        with col3:
            if st.form_submit_button("Record Waste", use_container_width=True, type="primary"):
                if qty <= 0:
                    st.error("Enter quantity > 0")
                else:
                    stock, _, _ = get_stock(veg)
                    if qty > stock:
                        st.error(f"Not enough stock! Available: {stock:.2f} kg")
                    else:
                        d = selected_date.strftime("%Y-%m-%d")
                        c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                 (d, veg, qty, f"{reason}: {description}"))
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                        conn.commit()
                        st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    # Today's waste
    waste_df = pd.read_sql("SELECT * FROM waste WHERE date=?", 
                          conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if waste_df.empty:
        st.info("No waste recorded today")
    else:
        total_waste = waste_df['quantity'].sum()
        st.metric("Total Waste Today", f"{total_waste:.2f} kg")
        st.dataframe(waste_df, use_container_width=True)

# ========================== DOWNLOAD ==========================
elif menu == "⬇ Download":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>⬇ Download Records</h2>
        <p class="subtitle">Export data for backup or analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Download options
    st.markdown(f"### 📅 Data for {selected_date.strftime('%d %B %Y')}")
    
    tables = [
        ("inventory", "📦 Inventory", "Current stock levels"),
        ("purchases", "🛒 Purchases", "Purchase records"),
        ("sales", "💰 Sales", "Sales transactions"),
        ("waste", "🗑 Waste", "Waste records"),
        ("customers", "👥 Customers", "Customer database"),
        ("expenses", "💸 Expenses", "Expense records")
    ]
    
    for table_name, display_name, description in tables:
        with st.expander(f"{display_name} - {description}"):
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
            if table_name in ["purchases", "sales", "waste", "expenses"]:
                df = df[df['date'] == selected_date.strftime("%Y-%m-%d")]
            
            if df.empty:
                st.info(f"No {display_name.lower()} data")
            else:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode()
                st.download_button(
                    f"Download {display_name}",
                    data=csv,
                    file_name=f"{table_name}_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

# ========================== FINANCIALS ==========================
elif menu == "💰 Financials":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💰 Financial Summary</h2>
        <p class="subtitle">Daily sales, costs, and profit analysis</p>
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
        profit_bg = "#43e97b" if profit >= 0 else "#fa709a"
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
        st.dataframe(
            recent_sales[['vegetable', 'quantity_sold', 'total', 'customer']].style.format({
                "quantity_sold": "{:.2f}",
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>🥕 Fresh Basket — Smart Vegetable Shop Management System | Designed for efficiency and ease of use ✅</p>
    <p style="font-size:0.8em; color:#95a5a6;">© 2024 Your Brother's Shop. All features working perfectly.</p>
</div>
""", unsafe_allow_html=True)
