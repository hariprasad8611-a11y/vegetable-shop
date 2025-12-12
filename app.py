import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🥕", layout="wide")
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);}
    h1 {text-align:center; color:#ffffff; font-size:2.8em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);}
    .stButton>button {height:3em; border-radius:15px; font-size:16px; font-weight:bold; transition: all 0.2s;}
    .stButton>button:hover {transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.2);}
    .primary-btn {background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important; color:black !important; border:none;}
    .secondary-btn {background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%) !important; color:white !important; border:none;}
    .success-btn {background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%) !important; color:white !important; border:none;}
    .warning-btn {background: linear-gradient(90deg, #f7971e 0%, #ffd200 100%) !important; color:black !important; border:none;}
    .info-card {background: rgba(255, 255, 255, 0.95); padding:20px; border-radius:15px; margin:10px 0; 
                box-shadow: 0 6px 20px rgba(0,0,0,0.1); border:1px solid rgba(255,255,255,0.2);}
    .cart-card {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding:15px; border-radius:15px; 
                margin:10px 0; box-shadow: 0 8px 16px rgba(0,0,0,0.1);}
    .veg-card {background: white; padding:12px; border-radius:12px; margin:8px 0; 
               border-left:4px solid #4CAF50; box-shadow: 0 3px 5px rgba(0,0,0,0.08);}
    .header-card {background: linear-gradient(90deg, #1D976C 0%, #93F9B9 100%); padding:20px; 
                  border-radius:15px; margin-bottom:20px; color:white; text-align:center;}
    .metric-card {background: white; padding:15px; border-radius:12px; margin:8px; 
                  box-shadow: 0 3px 6px rgba(0,0,0,0.1); text-align:center;}
    .receipt-card {background: white; padding:25px; border-radius:15px; margin:15px 0; 
                   box-shadow: 0 8px 25px rgba(0,0,0,0.15);}
    .quick-btn {width:100%; margin:3px 0; padding:8px; font-size:14px;}
    .number-input {width:80px; text-align:center;}
    .cart-item {background: white; padding:10px; margin:6px 0; border-radius:10px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .stSelectbox, .stTextInput, .stNumberInput {border-radius:8px !important;}
    .expense-btn {background: linear-gradient(90deg, #834d9b 0%, #d04ed6 100%) !important; color:white !important;}
    .footer {text-align:center; color:#666; margin-top:20px; font-size:0.9em;}
</style>
""", unsafe_allow_html=True)

# Header with gradient
st.markdown("""
<div class="header-card">
    <h1>🥕 Fresh Basket</h1>
    <h3 style="margin-top:10px;">Your Brother's Smart Vegetable Shop</h3>
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
    
    st.success(f"Added {qty:.3f} kg of {veg}")
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
    cust = f"{cust_name} ({cust_phone})" if cust_phone else cust_name or "Guest"
    
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
    if cust_phone:
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
    <div style="background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%); padding:20px; border-radius:15px; margin:20px 0;">
        <h2 style="color:white; text-align:center;">✅ SALE COMPLETED!</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Receipt
    with st.container():
        st.markdown("""
        <div class="receipt-card">
            <h2 style="text-align:center; color:#2c3e50;">🥕 FRESH BASKET</h2>
            <p style="text-align:center; color:#7f8c8d;">Your Brother's Vegetable Shop</p>
            <hr>
        """, unsafe_allow_html=True)
        
        # Sale info
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Date:** {sale['date']}")
            st.markdown(f"**Customer:** {sale['customer']}")
        with col2:
            st.markdown(f"**Time:** {datetime.now().strftime('%H:%M:%S')}")
            if sale['phone']:
                cust_points = pd.read_sql("SELECT points FROM customers WHERE phone=?", 
                                         conn, params=(sale['phone'],)).iloc[0]['points']
                st.markdown(f"**Loyalty Points:** {cust_points}")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # Items table
        st.markdown("### Items Purchased")
        items_df = pd.DataFrame(sale['items'])
        items_df['Qty Display'] = items_df['quantity'].apply(convert_to_display)
        items_display = items_df[['item', 'Qty Display', 'price_per_kg', 'total']]
        items_display.columns = ['Item', 'Quantity', 'Price/kg', 'Total']
        
        st.dataframe(items_display, use_container_width=True, hide_index=True)
        
        # Total
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:right;'>Total Amount: ₹{sale['total']:.2f}</h2>", unsafe_allow_html=True)
        
        st.markdown("""
        <hr>
        <p style="text-align:center; color:#7f8c8d; font-size:0.9em;">
            Thank you for your purchase!<br>
            Visit again 🥕
        </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Print button
    if st.button("🖨️ Print Receipt", use_container_width=True):
        st.info("Receipt ready for printing")
    
    st.balloons()

# ========================== SIDEBAR MENU ==========================
with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1D976C 0%, #93F9B9 100%); padding:15px; border-radius:12px; margin-bottom:15px;">
        <h2 style="color:white; text-align:center;">📋 Menu</h2>
    </div>
    """, unsafe_allow_html=True)
    
    menu = st.selectbox(
        "",
        ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Purchases", "Sales", 
         "Add Expense", "Customers", "Waste", "Download", "Financials"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 📅 Date Selector")
    selected_date = st.date_input("Select Date", value=st.session_state.selected_date, key="date_selector")
    st.session_state.selected_date = selected_date
    
    st.markdown(f"""
    <div class="info-card" style="margin-top:15px;">
        <h4>📅 Selected Date</h4>
        <h3>{selected_date.strftime('%d %B %Y')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Cart Summary in Sidebar
    if st.session_state.cart:
        cart_total = sum(item[3] for item in st.session_state.cart)
        st.markdown(f"""
        <div class="info-card" style="background: linear-gradient(90deg, #FFE985 0%, #FA742B 100%);">
            <h4>🛒 Cart Summary</h4>
            <p><strong>Items:</strong> {len(st.session_state.cart)}</p>
            <p><strong>Total:</strong> ₹{cart_total:.2f}</p>
        </div>
        """, unsafe_allow_html=True)

# -------------------------- DASHBOARD --------------------------
if menu == "Dashboard":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #4A00E0 0%, #8E2DE2 100%);">
        <h2>📊 Dashboard</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_items = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0", conn).iloc[0]['count']
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦</h3>
            <h4>Stock Items</h4>
            <h2>{total_items}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_stock = pd.read_sql("SELECT COALESCE(SUM(quantity),0) as total FROM inventory", conn).iloc[0]['total']
        st.markdown(f"""
        <div class="metric-card">
            <h3>⚖️</h3>
            <h4>Total Stock</h4>
            <h2>{total_stock:.1f} kg</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        today_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total FROM sales WHERE date=?", 
                                 conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['total']
        st.markdown(f"""
        <div class="metric-card">
            <h3>💰</h3>
            <h4>Today's Sales</h4>
            <h2>₹{today_sales:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        today_customers = pd.read_sql("SELECT COUNT(DISTINCT customer) as count FROM sales WHERE date=?", 
                                     conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['count']
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h4>Today's Customers</h4>
            <h2>{today_customers}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Shortage alerts
    st.markdown("### 🔔 Low Stock Alerts")
    threshold = st.slider("Alert threshold (kg)", 0.0, 20.0, 5.0, 0.5)
    st.session_state.shortage_threshold = threshold
    
    inv = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory WHERE quantity > 0", conn)
    if not inv.empty:
        low_stock = inv[inv['quantity'] < threshold]
        if not low_stock.empty:
            for _, row in low_stock.iterrows():
                st.warning(f"⚠️ **{row['vegetable']}**: Only {row['quantity']:.2f} kg left")
        else:
            st.success("✅ All items are sufficiently stocked")
    
    # Recent sales
    st.markdown("### 📈 Recent Sales")
    recent_sales = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC LIMIT 5", 
                              conn, params=(selected_date.strftime("%Y-%m-%d"),))
    if not recent_sales.empty:
        st.dataframe(recent_sales[['vegetable', 'quantity_sold', 'total', 'customer']], use_container_width=True)
    else:
        st.info("No sales today")

# -------------------------- ADD PURCHASE --------------------------
elif menu == "Add Purchase":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #FF5F6D 0%, #FFC371 100%);">
        <h2>🛒 Add Purchase</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick purchase form
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Quick Purchase Entry")
        with st.form("quick_purchase", clear_on_submit=True):
            veg = st.selectbox("Select Vegetable", default_vegetables)
            
            q_col1, q_col2 = st.columns(2)
            with q_col1:
                qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.5, value=1.0)
            with q_col2:
                qty_g = st.number_input("Grams", min_value=0, step=100, value=0, max_value=999)
            
            total_qty = qty_kg + (qty_g / 1000)
            amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0)
            supplier = st.text_input("Supplier Name")
            
            if st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True):
                if total_qty <= 0:
                    st.error("Enter quantity > 0")
                elif amount <= 0:
                    st.error("Enter amount > 0")
                else:
                    d = selected_date.strftime("%Y-%m-%d")
                    # Save purchase
                    c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                             (d, veg, total_qty, amount, supplier))
                    
                    # Update inventory
                    old_qty, old_cost, old_sell = get_stock(veg)
                    new_qty = old_qty + total_qty
                    unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                    
                    c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                             (new_qty, unit_cost, veg))
                    
                    conn.commit()
                    st.success(f"✅ Added {total_qty:.3f} kg of {veg}")
    
    with col2:
        st.markdown("### Quick Actions")
        if st.button("📝 Add All Default Vegetables", use_container_width=True):
            for veg in default_vegetables:
                c.execute("INSERT OR IGNORE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?, 0, 0, 0, '')", (veg,))
            conn.commit()
            st.success("✅ All default vegetables added")
        
        st.markdown("---")
        st.markdown("#### Today's Purchases")
        today_purchases = pd.read_sql("SELECT vegetable, quantity, amount FROM purchases WHERE date=?", 
                                     conn, params=(selected_date.strftime("%Y-%m-%d"),))
        if not today_purchases.empty:
            st.dataframe(today_purchases, use_container_width=True)
            total = today_purchases['amount'].sum()
            st.metric("Total Purchase Amount", f"₹{total:.2f}")
        else:
            st.info("No purchases today")

# -------------------------- SET SELLING PRICES --------------------------
elif menu == "Set Selling Prices":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #00B4DB 0%, #0083B0 100%);">
        <h2>🏷 Set Selling Prices</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables
    vegetables = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
    
    if not vegetables.empty:
        # Bulk price update
        st.markdown("### Bulk Price Update")
        price_df = pd.read_sql("SELECT vegetable, selling_price FROM inventory ORDER BY vegetable", conn)
        
        edited_df = st.data_editor(
            price_df,
            column_config={
                "vegetable": st.column_config.TextColumn("Vegetable", disabled=True),
                "selling_price": st.column_config.NumberColumn(
                    "Price/kg (₹)",
                    min_value=0.0,
                    step=1.0,
                    format="₹%.2f"
                )
            },
            use_container_width=True,
            num_rows="dynamic"
        )
        
        if st.button("💾 Save All Prices", type="primary", use_container_width=True):
            for _, row in edited_df.iterrows():
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", 
                         (row['selling_price'], row['vegetable']))
            conn.commit()
            st.success("✅ All prices updated successfully!")
        
        # Individual price update
        st.markdown("---")
        st.markdown("### Individual Price Update")
        selected_veg = st.selectbox("Select Vegetable", vegetables['vegetable'])
        current_price = pd.read_sql("SELECT selling_price FROM inventory WHERE vegetable=?", 
                                   conn, params=(selected_veg,)).iloc[0]['selling_price']
        
        col1, col2 = st.columns(2)
        with col1:
            new_price = st.number_input("New Price/kg ₹", value=float(current_price or 0.0), min_value=0.0)
        with col2:
            if st.button("Update Price", use_container_width=True):
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, selected_veg))
                conn.commit()
                st.success(f"✅ Price updated for {selected_veg}")

# -------------------------- SELL (FAST & SIMPLE) --------------------------
elif menu == "Sell":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%);">
        <h2>💵 Quick Sell</h2>
        <p>Fast vegetable selection for multiple customers</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get available vegetables with stock
    available_veg = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory WHERE quantity > 0 AND selling_price > 0 ORDER BY vegetable", conn)
    
    if available_veg.empty:
        st.warning("⚠️ No vegetables in stock or prices not set. Please add purchases and set prices first.")
    else:
        # Customer info at top
        col1, col2 = st.columns(2)
        with col1:
            cust_name = st.text_input("👤 Customer Name", placeholder="Enter name (optional)")
        with col2:
            cust_phone = st.text_input("📱 Phone Number", placeholder="Enter phone (optional)")
        
        st.markdown("---")
        
        # Main selling interface - SIMPLE and FAST
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🥬 Select Vegetables")
            
            # Create a grid of vegetables (4 columns)
            veg_list = available_veg['vegetable'].tolist()
            cols_per_row = 4
            rows = [veg_list[i:i + cols_per_row] for i in range(0, len(veg_list), cols_per_row)]
            
            for row in rows:
                col_boxes = st.columns(cols_per_row)
                for idx, veg in enumerate(row):
                    with col_boxes[idx]:
                        veg_data = available_veg[available_veg['vegetable'] == veg].iloc[0]
                        stock = veg_data['quantity']
                        price = veg_data['selling_price']
                        
                        # Calculate current in cart
                        current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
                        available = stock - current_in_cart
                        
                        # Vegetable card
                        st.markdown(f"""
                        <div style="background: white; padding:10px; border-radius:10px; margin:5px 0; border-left:4px solid #4CAF50;">
                            <strong>{veg}</strong><br>
                            <small>Stock: {stock:.2f} kg</small><br>
                            <small>Price: ₹{price:.2f}/kg</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Quantity selection
                        if available > 0:
                            # Quick add buttons
                            btn_col1, btn_col2, btn_col3 = st.columns(3)
                            with btn_col1:
                                if st.button(f"250g", key=f"q250_{veg}", use_container_width=True):
                                    add_to_cart(veg, 0.250, price)
                            with btn_col2:
                                if st.button(f"500g", key=f"q500_{veg}", use_container_width=True):
                                    add_to_cart(veg, 0.500, price)
                            with btn_col3:
                                if st.button(f"1kg", key=f"q1_{veg}", use_container_width=True):
                                    add_to_cart(veg, 1.000, price)
                            
                            # Manual input
                            man_col1, man_col2 = st.columns(2)
                            with man_col1:
                                manual_kg = st.number_input("Kg", min_value=0.0, max_value=min(available, 10.0), 
                                                          step=0.5, value=0.0, key=f"kg_{veg}")
                            with man_col2:
                                manual_g = st.number_input("Grams", min_value=0, max_value=999, step=100, 
                                                         value=0, key=f"g_{veg}")
                            
                            manual_qty = manual_kg + (manual_g / 1000)
                            if manual_qty > 0 and st.button("➕ Add", key=f"add_{veg}", use_container_width=True):
                                add_to_cart(veg, manual_qty, price)
                        
                        if current_in_cart > 0:
                            st.info(f"In cart: {current_in_cart:.3f} kg")
        
        with col2:
            st.markdown("### 🛒 Current Cart")
            
            if not st.session_state.cart:
                st.info("Cart is empty. Select vegetables from left.")
            else:
                # Display cart items
                total_amount = 0
                for idx, item in enumerate(st.session_state.cart):
                    veg, qty, price, total = item
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="cart-item">
                            <strong>{veg}</strong><br>
                            {qty:.3f} kg × ₹{price:.2f} = ₹{total:.2f}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Quick edit buttons
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("➕", key=f"inc_{veg}_{idx}", help="Add 250g"):
                                update_cart_item(idx, 0.250)
                        with col2:
                            if st.button("➖", key=f"dec_{veg}_{idx}", help="Remove 250g"):
                                update_cart_item(idx, -0.250)
                        with col3:
                            if st.button("❌", key=f"rem_{veg}_{idx}", help="Remove item"):
                                st.session_state.cart.pop(idx)
                                st.rerun()
                    
                    total_amount += total
                
                # Cart summary
                st.markdown("---")
                st.markdown(f"### **Total: ₹{total_amount:.2f}**")
                
                # Action buttons
                if st.button("✅ COMPLETE SALE", type="primary", use_container_width=True):
                    process_sale(cust_name, cust_phone, total_amount)
                
                if st.button("🔄 CLEAR CART", type="secondary", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
                
                # Quick discounts
                st.markdown("---")
                st.markdown("### Quick Discounts")
                disc_col1, disc_col2, disc_col3 = st.columns(3)
                with disc_col1:
                    if st.button("5% Off", use_container_width=True):
                        discount = total_amount * 0.05
                        st.session_state.cart.append(["DISCOUNT", 1, -discount, -discount])
                        st.rerun()
                with disc_col2:
                    if st.button("10% Off", use_container_width=True):
                        discount = total_amount * 0.10
                        st.session_state.cart.append(["DISCOUNT", 1, -discount, -discount])
                        st.rerun()
                with disc_col3:
                    if st.button("₹20 Off", use_container_width=True):
                        st.session_state.cart.append(["DISCOUNT", 1, -20, -20])
                        st.rerun()
        
        # Show receipt if last sale exists
        if st.session_state.last_sale:
            show_receipt()

# -------------------------- INVENTORY --------------------------
elif menu == "Inventory":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #8E2DE2 0%, #4A00E0 100%);">
        <h2>📦 Inventory</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Edit default vegetables
    st.markdown("### Manage Vegetables List")
    with st.expander("Edit Vegetable List"):
        edited_list = st.multiselect(
            "Select vegetables to keep",
            default_vegetables,
            default=default_vegetables
        )
        
        if st.button("Update Vegetable List"):
            # Remove unchecked vegetables with zero stock
            for veg in default_vegetables:
                if veg not in edited_list:
                    stock, _, _ = get_stock(veg)
                    if stock == 0:
                        c.execute("DELETE FROM inventory WHERE vegetable=?", (veg,))
            conn.commit()
            st.success("Vegetable list updated")
    
    # Display inventory
    df = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory ORDER BY vegetable", conn)
    
    if df.empty:
        st.info("No inventory")
    else:
        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            total_items = len(df)
            st.metric("Total Items", total_items)
        with col2:
            total_qty = df['quantity'].sum()
            st.metric("Total Quantity", f"{total_qty:.1f} kg")
        with col3:
            items_with_stock = len(df[df['quantity'] > 0])
            st.metric("In Stock", items_with_stock)
        
        # Inventory table
        st.markdown("### Current Stock")
        df_display = df.copy()
        df_display = df_display.rename(columns={
            "vegetable": "Vegetable",
            "quantity": "Quantity (kg)",
            "selling_price": "Price/kg (₹)"
        })
        st.dataframe(df_display, use_container_width=True)
        
        # Low stock warning
        low_stock = df[df['quantity'] < st.session_state.shortage_threshold]
        if not low_stock.empty:
            st.warning("⚠️ **Low Stock Alert**")
            for _, row in low_stock.iterrows():
                st.write(f"- {row['vegetable']}: {row['quantity']:.2f} kg")

# -------------------------- PURCHASES --------------------------
elif menu == "Purchases":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%);">
        <h2>📋 Purchases</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Add quick purchase
    with st.expander("➕ Add Quick Purchase", expanded=False):
        with st.form("quick_purchase_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Vegetable", default_vegetables)
                qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5, value=1.0)
            with col2:
                amount = st.number_input("Amount ₹", min_value=0.0, step=10.0, value=0.0)
                supplier = st.text_input("Supplier")
            with col3:
                if st.form_submit_button("Add Purchase", use_container_width=True):
                    if qty > 0 and amount > 0:
                        d = selected_date.strftime("%Y-%m-%d")
                        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (d, veg, qty, amount, supplier))
                        
                        # Update inventory
                        old_qty, old_cost, _ = get_stock(veg)
                        new_qty = old_qty + qty
                        unit_cost = (amount / qty) if qty > 0 else old_cost
                        c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                 (new_qty, unit_cost, veg))
                        
                        conn.commit()
                        st.success(f"Added purchase: {qty} kg of {veg}")
    
    # Display purchases
    purchases_df = pd.read_sql("SELECT * FROM purchases WHERE date=? ORDER BY rowid DESC", 
                              conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if purchases_df.empty:
        st.info(f"No purchases for {selected_date.strftime('%d %B %Y')}")
    else:
        total_amount = purchases_df['amount'].sum()
        total_qty = purchases_df['quantity'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Purchase Amount", f"₹{total_amount:.2f}")
        with col2:
            st.metric("Total Quantity", f"{total_qty:.1f} kg")
        
        st.dataframe(purchases_df, use_container_width=True)

# -------------------------- SALES --------------------------
elif menu == "Sales":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #F7971E 0%, #FFD200 100%);">
        <h2>🧾 Sales</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View Sales for Date", value=selected_date)
    with col2:
        show_all = st.checkbox("Show All Dates")
    
    # Get sales data
    if show_all:
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY date DESC, rowid DESC", conn)
    else:
        sales_df = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC", 
                              conn, params=(view_date.strftime("%Y-%m-%d"),))
    
    if sales_df.empty:
        st.info("No sales found")
    else:
        # Summary
        total_sales = sales_df['total'].sum()
        total_qty = sales_df['quantity_sold'].sum()
        unique_customers = sales_df['customer'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Sales", f"₹{total_sales:.2f}")
        with col2:
            st.metric("Quantity Sold", f"{total_qty:.1f} kg")
        with col3:
            st.metric("Customers", unique_customers)
        
        # Sales table
        st.dataframe(sales_df, use_container_width=True)
        
        # Export
        csv = sales_df.to_csv(index=False).encode()
        st.download_button("📥 Export Sales CSV", csv, f"sales_{view_date.strftime('%Y%m%d')}.csv")

# -------------------------- ADD EXPENSE --------------------------
elif menu == "Add Expense":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #834d9b 0%, #d04ed6 100%);">
        <h2>💸 Add Expense</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick expense form
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", 
                                   ["Rent", "Electricity", "Water", "Transport", "Labor", 
                                    "Packaging", "Maintenance", "Other"])
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

# -------------------------- CUSTOMERS --------------------------
elif menu == "Customers":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);">
        <h2>👥 Customers</h2>
    </div>
    """, unsafe_allow_html=True)
    
    customers_df = pd.read_sql("SELECT * FROM customers ORDER BY points DESC", conn)
    
    if customers_df.empty:
        st.info("No customers yet")
    else:
        # Summary
        total_customers = len(customers_df)
        total_points = customers_df['points'].sum()
        top_customer = customers_df.iloc[0]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Customers", total_customers)
        with col2:
            st.metric("Total Points", total_points)
        with col3:
            st.metric("Top Customer", f"{top_customer['name']} ({top_customer['points']} pts)")
        
        # Customers table
        st.dataframe(customers_df, use_container_width=True)
        
        # Top customers
        st.markdown("### 🏆 Top 5 Customers")
        top_5 = customers_df.head(5)
        for idx, row in top_5.iterrows():
            st.markdown(f"**{row['name']}** - {row['points']} points ({row['phone']})")

# -------------------------- WASTE --------------------------
elif menu == "Waste":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #f46b45 0%, #eea849 100%);">
        <h2>🗑 Record Waste</h2>
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
            if st.form_submit_button("Record Waste", use_container_width=True):
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

# -------------------------- DOWNLOAD --------------------------
elif menu == "Download":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);">
        <h2>⬇ Download Records</h2>
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

# -------------------------- FINANCIALS --------------------------
elif menu == "Financials":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);">
        <h2>💼 Financial Summary</h2>
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
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Sales", f"₹{sales_data:.2f}")
    with col2:
        st.metric("📦 Cost of Goods", f"₹{cost_data:.2f}")
    with col3:
        st.metric("💸 Expenses", f"₹{expense_data:.2f}")
    with col4:
        profit_color = "normal" if profit >= 0 else "inverse"
        st.metric("📈 Profit", f"₹{profit:.2f}", delta_color=profit_color)
    
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
            st.dataframe(sales_by_veg, use_container_width=True)
        with col2:
            # Simple chart
            chart_data = sales_by_veg.head(10).set_index('vegetable')['revenue']
            st.bar_chart(chart_data)
    
    # Recent transactions
    st.markdown("### Recent Transactions")
    recent_sales = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC LIMIT 10", 
                              conn, params=(d,))
    if not recent_sales.empty:
        st.dataframe(recent_sales[['vegetable', 'quantity_sold', 'total', 'customer']], 
                    use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>🥕 Fresh Basket — Fast & Easy Vegetable Shop Management | Designed for quick billing with multiple customers ✅</p>
</div>
""", unsafe_allow_html=True)
