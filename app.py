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
    .stButton>button {height:3em; border-radius:20px; font-size:16px; font-weight:bold; transition: all 0.3s;}
    .stButton>button:hover {transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3);}
    .primary-btn {background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important; color:black !important; border:none;}
    .secondary-btn {background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%) !important; color:white !important; border:none;}
    .success-btn {background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%) !important; color:white !important; border:none;}
    .warning-btn {background: linear-gradient(90deg, #f7971e 0%, #ffd200 100%) !important; color:black !important; border:none;}
    .info-card {background: rgba(255, 255, 255, 0.9); padding:20px; border-radius:20px; margin:10px 0; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.1); border:1px solid rgba(255,255,255,0.2);}
    .cart-card {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding:20px; border-radius:20px; 
                margin:15px 0; box-shadow: 0 10px 20px rgba(0,0,0,0.1);}
    .veg-card {background: white; padding:15px; border-radius:15px; margin:10px 0; 
               border-left:5px solid #4CAF50; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    .header-card {background: linear-gradient(90deg, #1D976C 0%, #93F9B9 100%); padding:25px; 
                  border-radius:20px; margin-bottom:25px; color:white; text-align:center;}
    .metric-card {background: white; padding:20px; border-radius:15px; margin:10px; 
                  box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align:center;}
    .stTabs [data-baseweb="tab-list"] {gap: 10px;}
    .stTabs [data-baseweb="tab"] {border-radius: 10px 10px 0px 0px; padding: 10px 20px; 
                                  background-color: #f0f2f6;}
    .stTabs [aria-selected="true"] {background-color: #4CAF50 !important; color: white !important;}
    .alert-success {background: linear-gradient(90deg, #d4edda 0%, #c3e6cb 100%); padding:15px; 
                    border-radius:10px; border-left:5px solid #155724; margin:10px 0;}
    .alert-warning {background: linear-gradient(90deg, #fff3cd 0%, #ffeaa7 100%); padding:15px; 
                    border-radius:10px; border-left:5px solid #856404; margin:10px 0;}
    .alert-danger {background: linear-gradient(90deg, #f8d7da 0%, #f5c6cb 100%); padding:15px; 
                   border-radius:10px; border-left:5px solid #721c24; margin:10px 0;}
    .stSelectbox, .stTextInput, .stNumberInput {border-radius:10px !important;}
    .cart-item {background: white; padding:12px; margin:8px 0; border-radius:10px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .quantity-control {display: flex; align-items: center; gap: 10px; background: #f8f9fa; 
                       padding: 8px 15px; border-radius: 25px; margin: 5px 0;}
    .footer {text-align:center; color:#666; margin-top:30px; font-size:0.9em;}
</style>
""", unsafe_allow_html=True)

# Header with gradient
st.markdown("""
<div class="header-card">
    <h1>🥕 Fresh Basket</h1>
    <h3 style="margin-top:10px;">Freshness You Can Feel.</h3>
</div>
""", unsafe_allow_html=True)

# ========================== DATABASE ==========================
DB_FILE = "shop.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# create tables (keeps cost_price column but UI won't show/edit it)
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
    grams = int((qty - kg) * 1000)
    if grams > 0:
        return f"{kg} kg {grams} g" if kg > 0 else f"{grams} g"
    return f"{kg} kg"

# ensure session state keys
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of [veg, qty, price, total, item_id]
if "shortage_threshold" not in st.session_state:
    st.session_state.shortage_threshold = 5.0  # default threshold in kg
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()
if "cart_counter" not in st.session_state:
    st.session_state.cart_counter = 0  # For unique cart item IDs

# ========================== SIDEBAR MENU ==========================
with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1D976C 0%, #93F9B9 100%); padding:20px; border-radius:15px; margin-bottom:20px;">
        <h2 style="color:white; text-align:center;">📋 Menu</h2>
    </div>
    """, unsafe_allow_html=True)
    
    menu = st.selectbox(
        "",
        ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Purchases", "Sales", "Expenses", "Customers", "Waste", "Download", "Financials"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 📅 Date Selector")
    selected_date = st.date_input("Select Date", value=st.session_state.selected_date, key="date_selector")
    st.session_state.selected_date = selected_date
    
    st.markdown(f"""
    <div class="info-card" style="margin-top:20px;">
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
        <h2>📊 Dashboard — Vegetable Shortage Alerts</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_items = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0", conn).iloc[0]['count']
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦</h3>
            <h4>Total Items</h4>
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
    
    # threshold control
    st.markdown("### ⚙️ Shortage Alert Settings")
    threshold = st.slider("Shortage threshold (kg)", 
                         min_value=0.0, max_value=20.0, 
                         value=float(st.session_state.shortage_threshold), step=0.5,
                         help="Items below this quantity will trigger alerts")
    st.session_state.shortage_threshold = threshold
    
    inv = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory", conn)
    if inv.empty:
        st.info("No inventory available yet.")
    else:
        inv = inv.sort_values("quantity")
        low = inv[(inv["quantity"] > 0) & (inv["quantity"] < threshold)]
        zero = inv[inv["quantity"] <= 0]
        
        if zero.empty and low.empty:
            st.markdown("""
            <div class="alert-success">
                <h4>✅ All Good!</h4>
                <p>No shortages right now. All items are sufficiently stocked.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("### 🔔 Shortage Alerts")
            # first show items with zero stock (out of stock)
            if not zero.empty:
                for _, r in zero.iterrows():
                    veg = r["vegetable"]
                    st.markdown(f"""
                    <div class="alert-danger">
                        <h4>⚠️ {veg}</h4>
                        <p>This item is <strong>out of stock</strong>. Please reorder immediately.</p>
                        <p><strong>Suggested reorder:</strong> 10 kg</p>
                    </div>
                    """, unsafe_allow_html=True)
            # then low stock items
            if not low.empty:
                for _, r in low.iterrows():
                    veg = r["vegetable"]
                    qty = r["quantity"]
                    suggested = max(5.0, threshold * 2)
                    st.markdown(f"""
                    <div class="alert-warning">
                        <h4>📉 {veg}</h4>
                        <p>Running low — only <strong>{qty:.2f} kg</strong> left.</p>
                        <p><strong>Suggested reorder:</strong> {suggested:.0f} kg</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Helpful summary table
        st.markdown("### 📋 Inventory Snapshot")
        inv_display = inv.copy()
        inv_display = safe_round_df(inv_display, ["quantity", "selling_price"])
        inv_display = inv_display.rename(columns={"vegetable": "Vegetable", "quantity": "Qty (kg)", "selling_price": "Sell/kg"})
        
        # Apply colorful styling to dataframe
        def color_low_stock(val):
            if val < threshold:
                return 'background-color: #ffcccc'
            return ''
        
        styled_df = inv_display.style.applymap(color_low_stock, subset=['Qty (kg)'])
        st.dataframe(styled_df, use_container_width=True)

# -------------------------- ADD PURCHASE --------------------------
elif menu == "Add Purchase":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #FF5F6D 0%, #FFC371 100%);">
        <h2>🛒 Add Purchase</h2>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown(f"<h3 style='color:#FF5F6D;'>📅 {selected_date.strftime('%d %B %Y')}</h3>", unsafe_allow_html=True)
        
        with st.form("purchase_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                veg = st.text_input("🥬 Vegetable Name", placeholder="Enter vegetable name")
                amount = st.number_input("💰 Total Cost ₹", min_value=0.0, step=10.0, value=0.0)
            with col2:
                qty_kg = st.number_input("⚖️ Kilograms", min_value=0.0, step=0.5, value=1.0)
                qty_g = st.number_input("⚖️ Grams", min_value=0, step=100, value=0, max_value=999)
                supplier = st.text_input("👨‍🌾 Supplier", placeholder="Supplier name (optional)")
            
            qty = qty_kg + (qty_g / 1000)
            
            submitted = st.form_submit_button("💾 Save Purchase", use_container_width=True, type="primary")
            
            if submitted:
                if not veg:
                    st.error("Please enter vegetable name.")
                elif qty <= 0:
                    st.error("Quantity must be > 0.")
                else:
                    d = selected_date.strftime("%Y-%m-%d")
                    c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (d, veg, qty, amount, supplier))
                    # update inventory
                    old_qty, old_cost, old_sell = get_stock(veg)
                    new_qty = old_qty + qty
                    unit_cost = (amount / qty) if qty > 0 else old_cost
                    
                    c.execute("SELECT selling_price, image_url FROM inventory WHERE vegetable=?", (veg,))
                    prev = c.fetchone()
                    prev_sell = prev[0] if prev else None
                    prev_img = prev[1] if prev else ""
                    
                    if prev:
                        c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", (new_qty, unit_cost, veg))
                    else:
                        c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)", 
                                 (veg, new_qty, unit_cost, prev_sell or 0.0, prev_img or ""))
                    conn.commit()
                    
                    st.markdown(f"""
                    <div class="alert-success">
                        <h4>✅ Success!</h4>
                        <p>Added {qty:.3f} kg of <strong>{veg}</strong> to purchases and inventory.</p>
                        <p><strong>Unit Cost:</strong> ₹{unit_cost:.2f}/kg</p>
                    </div>
                    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"<h3 style='color:#FF5F6D;'>📋 Purchases for {selected_date.strftime('%d %B %Y')}</h3>", unsafe_allow_html=True)
    
    pur_df = fetch_table_with_rowid("purchases")
    if not pur_df.empty:
        pur_df = pur_df[pur_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if pur_df.empty:
        st.info(f"No purchases recorded for {selected_date.strftime('%d %B %Y')}")
    else:
        pur_df = safe_round_df(pur_df, ["quantity", "amount"])
        st.dataframe(pur_df.drop(columns=["rowid"]), use_container_width=True)

# -------------------------- SET SELLING PRICES --------------------------
elif menu == "Set Selling Prices":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #00B4DB 0%, #0083B0 100%);">
        <h2>🏷 Set Selling Prices</h2>
    </div>
    """, unsafe_allow_html=True)
    
    items = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
    if items.empty:
        st.info("No items in inventory")
    else:
        tab1, tab2 = st.tabs(["💰 Update Price", "📊 All Prices"])
        
        with tab1:
            veg = st.selectbox("🥬 Choose Vegetable", items['vegetable'])
            qty, cost, sell = get_stock(veg)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="info-card">
                    <h4>📦 Current Stock</h4>
                    <h2>{qty:.2f} kg</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="info-card">
                    <h4>💰 Current Price</h4>
                    <h2>₹{sell or 0:.2f}/kg</h2>
                </div>
                """, unsafe_allow_html=True)
            
            new_price = st.number_input("🎯 New Selling Price per kg ₹", 
                                       value=float(sell or 0.0), 
                                       min_value=0.0, 
                                       step=1.0)
            
            if st.button("💾 Update Price", type="primary", use_container_width=True):
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
                conn.commit()
                st.markdown(f"""
                <div class="alert-success">
                    <h4>✅ Price Updated!</h4>
                    <p><strong>{veg}</strong> selling price updated to <strong>₹{new_price:.2f}/kg</strong></p>
                </div>
                """, unsafe_allow_html=True)
        
        with tab2:
            prices_df = pd.read_sql("SELECT vegetable, selling_price FROM inventory ORDER BY vegetable", conn)
            if not prices_df.empty:
                st.dataframe(prices_df.rename(columns={"vegetable": "Vegetable", "selling_price": "Price/kg (₹)"}), 
                           use_container_width=True)

# -------------------------- SELL (Enhanced with better selection) --------------------------
elif menu == "Sell":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%);">
        <h2>💵 Sell Vegetables</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state for edit mode
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = None
    
    # Get inventory
    inventory = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory WHERE quantity > 0 ORDER BY vegetable", conn)
    
    if inventory.empty:
        st.info("📭 No items in inventory. Please add purchases first.")
    else:
        # Customer details section
        st.markdown("### 👤 Customer Information")
        col1, col2 = st.columns(2)
        with col1:
            cust_name = st.text_input("👤 Customer Name", placeholder="Enter customer name")
        with col2:
            cust_phone = st.text_input("📱 Customer Phone", placeholder="Enter phone number")
        
        # Main selling interface with tabs
        tab1, tab2, tab3 = st.tabs(["➕ Add Items", "🛒 View Cart", "📋 Quick Select"])
        
        with tab1:
            st.markdown("### 🥬 Select Vegetables")
            
            # Create selection form for each vegetable
            for _, row in inventory.iterrows():
                veg = row['vegetable']
                stock = float(row['quantity'] or 0.0)
                price = float(row['selling_price'] or 0.0)
                
                # Calculate current quantity in cart
                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
                available_stock = stock - current_in_cart
                
                with st.expander(f"**{veg}** — Available: {stock:.3f} kg — ₹{price:.2f}/kg", expanded=False):
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"**Stock:** {stock:.3f} kg")
                        st.markdown(f"**Price:** ₹{price:.2f}/kg")
                        if current_in_cart > 0:
                            st.markdown(f"**In Cart:** {current_in_cart:.3f} kg")
                    
                    with col2:
                        kg_amount = st.number_input(
                            "Kg",
                            min_value=0.0,
                            max_value=available_stock if available_stock > 0 else 0.0,
                            step=0.5,
                            value=0.0,
                            key=f"kg_{veg}"
                        )
                    
                    with col3:
                        gram_amount = st.number_input(
                            "Grams",
                            min_value=0,
                            max_value=int((available_stock - kg_amount) * 1000) if available_stock > kg_amount else 0,
                            step=100,
                            value=0,
                            key=f"g_{veg}"
                        )
                    
                    total_qty = kg_amount + (gram_amount / 1000)
                    total_price = total_qty * price
                    
                    with col4:
                        if st.button("➕ Add to Cart", key=f"add_{veg}", 
                                    disabled=total_qty <= 0 or available_stock < total_qty,
                                    use_container_width=True):
                            # Check if already in cart
                            found = False
                            for i, item in enumerate(st.session_state.cart):
                                if item[0] == veg:
                                    st.session_state.cart[i][1] += total_qty
                                    st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * price, 2)
                                    found = True
                                    break
                            
                            if not found:
                                st.session_state.cart_counter += 1
                                st.session_state.cart.append([
                                    veg,
                                    total_qty,
                                    price,
                                    round(total_price, 2),
                                    st.session_state.cart_counter  # Unique ID
                                ])
                            
                            st.success(f"Added {total_qty:.3f} kg of {veg} to cart")
                            st.rerun()
        
        with tab2:
            st.markdown("### 🛒 Your Cart")
            
            if not st.session_state.cart:
                st.info("🛒 Cart is empty. Add items from the 'Add Items' tab.")
            else:
                # Display cart items
                cart_items = []
                total_amount = 0
                
                for idx, item in enumerate(st.session_state.cart):
                    veg_name, qty, price_per_kg, total, item_id = item
                    
                    # Display each cart item
                    with st.container():
                        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                        
                        with col1:
                            st.markdown(f"**{veg_name}**")
                        
                        with col2:
                            # Edit quantity with kg and grams
                            edit_col1, edit_col2 = st.columns(2)
                            with edit_col1:
                                new_kg = st.number_input(
                                    "Kg",
                                    min_value=0.0,
                                    max_value=float(inventory[inventory['vegetable'] == veg_name]['quantity'].iloc[0]),
                                    value=float(int(qty)),
                                    step=0.5,
                                    key=f"edit_kg_{item_id}"
                                )
                            with edit_col2:
                                grams = int((qty - int(qty)) * 1000)
                                new_g = st.number_input(
                                    "Grams",
                                    min_value=0,
                                    max_value=999,
                                    value=grams,
                                    step=100,
                                    key=f"edit_g_{item_id}"
                                )
                            new_qty = new_kg + (new_g / 1000)
                            
                            if new_qty != qty:
                                if st.button("🔄 Update", key=f"update_{item_id}"):
                                    if new_qty > 0:
                                        st.session_state.cart[idx][1] = new_qty
                                        st.session_state.cart[idx][3] = round(new_qty * price_per_kg, 2)
                                    else:
                                        st.session_state.cart.pop(idx)
                                    st.success("Quantity updated")
                                    st.rerun()
                        
                        with col3:
                            st.markdown(f"**₹{price_per_kg:.2f}**/kg")
                        
                        with col4:
                            item_total = qty * price_per_kg
                            st.markdown(f"**₹{item_total:.2f}**")
                            total_amount += item_total
                        
                        with col5:
                            if st.button("❌", key=f"remove_{item_id}"):
                                st.session_state.cart.pop(idx)
                                st.success("Item removed")
                                st.rerun()
                
                # Cart summary
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"### **Total Items:** {len(st.session_state.cart)}")
                with col2:
                    st.markdown(f"### **Total Amount:** ₹{total_amount:.2f}")
                
                # Action buttons
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✅ Complete Sale", type="primary", use_container_width=True):
                        # Validate stock and process sale
                        insufficient = []
                        for veg_name, qty, price, total, item_id in st.session_state.cart:
                            stock, _, _ = get_stock(veg_name)
                            if qty > stock:
                                insufficient.append((veg_name, stock, qty))
                        
                        if insufficient:
                            for v, stock, q in insufficient:
                                st.error(f"Not enough {v}: available {stock:.3f} kg, requested {q:.3f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            cust = f"{cust_name} ({cust_phone})" if cust_phone else cust_name or "Guest"
                            
                            # Process each item in cart
                            sale_details = []
                            for veg_name, qty, price, total, item_id in st.session_state.cart:
                                c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", 
                                         (d, veg_name, qty, price, total, cust))
                                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg_name))
                                
                                sale_details.append({
                                    "vegetable": veg_name,
                                    "quantity": qty,
                                    "price": price,
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
                            
                            # Display receipt
                            st.markdown("""
                            <div class="alert-success" style="background: linear-gradient(90deg, #56ab2f 0%, #a8e063 100%);">
                                <h2>🎉 Sale Completed Successfully!</h2>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Receipt
                            st.markdown("### 📄 Sale Receipt")
                            receipt_col1, receipt_col2 = st.columns(2)
                            
                            with receipt_col1:
                                st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
                                st.markdown(f"**Customer:** {cust}")
                            
                            with receipt_col2:
                                st.markdown(f"**Transaction ID:** {datetime.now().strftime('%Y%m%d%H%M%S')}")
                                if cust_phone:
                                    new_points = pd.read_sql("SELECT points FROM customers WHERE phone=?", 
                                                            conn, params=(cust_phone,)).iloc[0]['points']
                                    st.markdown(f"**Loyalty Points:** {new_points}")
                            
                            # Sale items table
                            st.markdown("### 🛒 Sold Items")
                            receipt_df = pd.DataFrame(sale_details)
                            receipt_df['Quantity'] = receipt_df['quantity'].apply(convert_to_display)
                            receipt_df = receipt_df.rename(columns={
                                "vegetable": "Item",
                                "price": "Price/kg",
                                "total": "Total"
                            })
                            st.dataframe(receipt_df[['Item', 'Quantity', 'Price/kg', 'Total']], use_container_width=True)
                            
                            st.markdown(f"### **Total Bill: ₹{total_amount:.2f}**")
                            
                            # Clear cart
                            st.session_state.cart = []
                            st.session_state.cart_counter = 0
                            st.balloons()
                
                with col2:
                    if st.button("🔄 Clear Cart", use_container_width=True, type="secondary"):
                        st.session_state.cart = []
                        st.session_state.cart_counter = 0
                        st.success("Cart cleared")
                        st.rerun()
                
                with col3:
                    if st.button("📥 Save as Draft", use_container_width=True):
                        st.success("Cart saved as draft")
        
        with tab3:
            st.markdown("### ⚡ Quick Add")
            st.markdown("Quickly add common quantities to cart")
            
            quick_veg = st.selectbox("Select Vegetable", inventory['vegetable'], key="quick_veg")
            quick_row = inventory[inventory['vegetable'] == quick_veg].iloc[0]
            
            col1, col2, col3, col4 = st.columns(4)
            quick_buttons = {
                "250g": 0.250,
                "500g": 0.500,
                "750g": 0.750,
                "1kg": 1.000,
                "2kg": 2.000,
                "5kg": 5.000
            }
            
            for i, (label, qty) in enumerate(quick_buttons.items()):
                with [col1, col2, col3, col4][i % 4]:
                    if st.button(f"➕ {label}", use_container_width=True):
                        # Check stock
                        stock = float(quick_row['quantity'])
                        current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == quick_veg)
                        
                        if current_in_cart + qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.3f} kg")
                        else:
                            # Add to cart
                            found = False
                            for i, item in enumerate(st.session_state.cart):
                                if item[0] == quick_veg:
                                    st.session_state.cart[i][1] += qty
                                    st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * quick_row['selling_price'], 2)
                                    found = True
                                    break
                            
                            if not found:
                                st.session_state.cart_counter += 1
                                st.session_state.cart.append([
                                    quick_veg,
                                    qty,
                                    quick_row['selling_price'],
                                    round(qty * quick_row['selling_price'], 2),
                                    st.session_state.cart_counter
                                ])
                            
                            st.success(f"Added {label} of {quick_veg} to cart")
                            st.rerun()

# -------------------------- INVENTORY --------------------------
elif menu == "Inventory":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #8E2DE2 0%, #4A00E0 100%);">
        <h2>📦 Inventory</h2>
    </div>
    """, unsafe_allow_html=True)
    
    df = pd.read_sql("SELECT rowid, vegetable, quantity, selling_price, image_url FROM inventory", conn)
    
    if df.empty:
        st.info("📭 No stock available")
    else:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_items = len(df)
            st.markdown(f"""
            <div class="metric-card">
                <h3>📊</h3>
                <h4>Total Items</h4>
                <h2>{total_items}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            total_qty = df['quantity'].sum()
            st.markdown(f"""
            <div class="metric-card">
                <h3>⚖️</h3>
                <h4>Total Quantity</h4>
                <h2>{total_qty:.1f} kg</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            avg_price = df['selling_price'].mean()
            st.markdown(f"""
            <div class="metric-card">
                <h3>💰</h3>
                <h4>Avg Price</h4>
                <h2>₹{avg_price:.2f}/kg</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Inventory table
        st.markdown("### 📋 Current Inventory")
        df_display = df.copy()
        df_display = safe_round_df(df_display, ["quantity", "selling_price"])
        df_display['Display Qty'] = df_display['quantity'].apply(convert_to_display)
        df_display = df_display.rename(columns={
            "vegetable": "Vegetable",
            "selling_price": "Sell/kg",
            "image_url": "Image URL"
        })
        
        # Color code based on quantity
        def color_quantity(val):
            if val < st.session_state.shortage_threshold:
                return 'background-color: #ffcccc; color: #d63031'
            elif val < st.session_state.shortage_threshold * 2:
                return 'background-color: #fff3cd; color: #856404'
            else:
                return 'background-color: #d4edda; color: #155724'
        
        styled_df = df_display.style.applymap(color_quantity, subset=['quantity'])
        st.dataframe(styled_df[['Vegetable', 'Display Qty', 'Sell/kg']], 
                    use_container_width=True,
                    hide_index=True)
        
        # Edit interface
        st.markdown("### ✏️ Edit Inventory")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3, 1, 1])
            with cols[0]:
                qty_display = convert_to_display(row['quantity'])
                st.markdown(f"""
                <div class="veg-card">
                    <h4>{row['vegetable']}</h4>
                    <p>📦 {qty_display} | 💰 ₹{row['selling_price'] or 0:.2f}/kg</p>
                </div>
                """, unsafe_allow_html=True)
            with cols[1]:
                if st.button("✏️ Edit", key=f"edit_inv_{int(row['rowid'])}", use_container_width=True):
                    st.session_state[f"edit_{int(row['rowid'])}"] = True
            
            with cols[2]:
                if st.button("🗑️ Delete", key=f"del_inv_{int(row['rowid'])}", use_container_width=True, type="secondary"):
                    c.execute("DELETE FROM inventory WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted item")
                    st.rerun()
            
            # Edit form
            if st.session_state.get(f"edit_{int(row['rowid'])}", False):
                with st.form(f"edit_inv_form_{int(row['rowid'])}"):
                    new_name = st.text_input("Vegetable Name", value=row['vegetable'])
                    col1, col2 = st.columns(2)
                    with col1:
                        new_qty_kg = st.number_input("Kilograms", value=int(row['quantity']), min_value=0)
                    with col2:
                        grams = int((row['quantity'] - int(row['quantity'])) * 1000)
                        new_qty_g = st.number_input("Grams", value=grams, min_value=0, max_value=999, step=100)
                    new_qty = new_qty_kg + (new_qty_g / 1000)
                    new_sell = st.number_input("Selling Price/kg ₹", value=float(row['selling_price'] or 0.0))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Save", use_container_width=True):
                            if new_name != row['vegetable']:
                                c.execute("DELETE FROM inventory WHERE vegetable=?", (row['vegetable'],))
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)",
                                         (new_name, new_qty, 0.0, new_sell, row['image_url']))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                                         (new_qty, new_sell, row['vegetable']))
                            conn.commit()
                            st.session_state[f"edit_{int(row['rowid'])}"] = False
                            st.success("Inventory updated")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Cancel", use_container_width=True, type="secondary"):
                            st.session_state[f"edit_{int(row['rowid'])}"] = False
                            st.rerun()

# -------------------------- PURCHASES --------------------------
elif menu == "Purchases":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%);">
        <h2>📋 Purchases</h2>
    </div>
    """, unsafe_allow_html=True)
    
    pur_df = fetch_table_with_rowid("purchases")
    if not pur_df.empty:
        pur_df = pur_df[pur_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if pur_df.empty:
        st.info(f"📭 No purchases for {selected_date.strftime('%d %B %Y')}")
    else:
        # Summary
        total_amount = pur_df['amount'].sum()
        total_qty = pur_df['quantity'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>💰</h3>
                <h4>Total Cost</h4>
                <h2>₹{total_amount:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>⚖️</h3>
                <h4>Total Quantity</h4>
                <h2>{total_qty:.1f} kg</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Dataframe
        pur_df2 = safe_round_df(pur_df.copy(), ["quantity", "amount"])
        st.dataframe(pur_df2.drop(columns=["rowid"]), use_container_width=True)
        
        # Edit/Delete
        st.markdown("### ✏️ Edit / Delete Purchases")
        for _, row in pur_df.sort_values("rowid", ascending=False).iterrows():
            with st.expander(f"{row['date']} — {row['vegetable']} — {row['quantity']} kg — ₹{row['amount']}"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_pur2_{int(row['rowid'])}", use_container_width=True):
                        with st.form(f"edit_pur2_form_{int(row['rowid'])}"):
                            nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                            nv = st.text_input("Vegetable", value=row['vegetable'])
                            col1, col2 = st.columns(2)
                            with col1:
                                nq_kg = st.number_input("Kilograms", value=int(row['quantity']), min_value=0)
                            with col2:
                                grams = int((row['quantity'] - int(row['quantity'])) * 1000)
                                nq_g = st.number_input("Grams", value=grams, min_value=0, max_value=999, step=100)
                            nq = nq_kg + (nq_g / 1000)
                            na = st.number_input("Amount ₹", value=float(row['amount']))
                            ns = st.text_input("Supplier", value=row['supplier'])
                            
                            if st.form_submit_button("💾 Save", use_container_width=True):
                                c.execute("UPDATE purchases SET date=?, vegetable=?, quantity=?, amount=?, supplier=? WHERE rowid=?",
                                         (nd.strftime("%Y-%m-%d"), nv, nq, na, ns, int(row['rowid'])))
                                conn.commit()
                                st.success("Updated purchase")
                                st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete", key=f"del_pur2_{int(row['rowid'])}", use_container_width=True, type="secondary"):
                        c.execute("DELETE FROM purchases WHERE rowid=?", (int(row['rowid']),))
                        conn.commit()
                        st.success("Deleted")
                        st.rerun()

# -------------------------- SALES --------------------------
elif menu == "Sales":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #F7971E 0%, #FFD200 100%);">
        <h2>🧾 Sales</h2>
    </div>
    """, unsafe_allow_html=True)
    
    sales_df = fetch_table_with_rowid("sales")
    if not sales_df.empty:
        sales_df = sales_df[sales_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if sales_df.empty:
        st.info(f"📭 No sales for {selected_date.strftime('%d %B %Y')}")
    else:
        # Summary
        total_sales = sales_df['total'].sum()
        total_qty = sales_df['quantity_sold'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>💰</h3>
                <h4>Total Sales</h4>
                <h2>₹{total_sales:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>⚖️</h3>
                <h4>Total Sold</h4>
                <h2>{total_qty:.1f} kg</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Dataframe
        sales_df2 = safe_round_df(sales_df.copy(), ["quantity_sold", "sale_price", "total"])
        st.dataframe(sales_df2.drop(columns=["rowid"]), use_container_width=True)
        
        # Edit/Delete
        st.markdown("### ✏️ Edit / Delete Sales")
        for _, row in sales_df.sort_values("rowid", ascending=False).iterrows():
            with st.expander(f"{row['date']} — {row['vegetable']} — {row['quantity_sold']} kg — ₹{row['total']}"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_sale_{int(row['rowid'])}", use_container_width=True):
                        with st.form(f"edit_sale_form_{int(row['rowid'])}"):
                            nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                            nv = st.text_input("Vegetable", value=row['vegetable'])
                            col1, col2 = st.columns(2)
                            with col1:
                                nq_kg = st.number_input("Kilograms", value=int(row['quantity_sold']), min_value=0)
                            with col2:
                                grams = int((row['quantity_sold'] - int(row['quantity_sold'])) * 1000)
                                nq_g = st.number_input("Grams", value=grams, min_value=0, max_value=999, step=100)
                            nq = nq_kg + (nq_g / 1000)
                            np = st.number_input("Price/kg ₹", value=float(row['sale_price']))
                            
                            if st.form_submit_button("💾 Save", use_container_width=True):
                                new_total = nq * np
                                c.execute("UPDATE sales SET date=?, vegetable=?, quantity_sold=?, sale_price=?, total=? WHERE rowid=?",
                                         (nd.strftime("%Y-%m-%d"), nv, nq, np, new_total, int(row['rowid'])))
                                conn.commit()
                                st.success("Sale updated")
                                st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete", key=f"del_sale_{int(row['rowid'])}", use_container_width=True, type="secondary"):
                        c.execute("DELETE FROM sales WHERE rowid=?", (int(row['rowid']),))
                        conn.commit()
                        st.success("Deleted sale")
                        st.rerun()

# -------------------------- EXPENSES --------------------------
elif menu == "Expenses":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #834d9b 0%, #d04ed6 100%);">
        <h2>💸 Expenses</h2>
    </div>
    """, unsafe_allow_html=True)
    
    exp_df = fetch_table_with_rowid("expenses")
    if not exp_df.empty:
        exp_df = exp_df[exp_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if exp_df.empty:
        st.info(f"📭 No expenses for {selected_date.strftime('%d %B %Y')}")
    else:
        total_expenses = exp_df['amount'].sum()
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>💰</h3>
            <h4>Total Expenses</h4>
            <h2>₹{total_expenses:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.dataframe(exp_df.drop(columns=["rowid"]), use_container_width=True)
        
        # Edit/Delete
        st.markdown("### ✏️ Edit / Delete Expenses")
        for _, row in exp_df.sort_values("rowid", ascending=False).iterrows():
            with st.expander(f"{row['date']} — {row['category']} — ₹{row['amount']}"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_exp_{int(row['rowid'])}", use_container_width=True):
                        with st.form(f"edit_exp_form_{int(row['rowid'])}"):
                            nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                            cat = st.text_input("Category", value=row['category'])
                            amt = st.number_input("Amount ₹", value=float(row['amount']))
                            desc = st.text_input("Description", value=row['description'])
                            
                            if st.form_submit_button("💾 Save", use_container_width=True):
                                c.execute("UPDATE expenses SET date=?, category=?, amount=?, description=? WHERE rowid=?",
                                         (nd.strftime("%Y-%m-%d"), cat, amt, desc, int(row['rowid'])))
                                conn.commit()
                                st.success("Updated expense")
                                st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete", key=f"del_exp_{int(row['rowid'])}", use_container_width=True, type="secondary"):
                        c.execute("DELETE FROM expenses WHERE rowid=?", (int(row['rowid']),))
                        conn.commit()
                        st.success("Deleted")
                        st.rerun()

# -------------------------- CUSTOMERS --------------------------
elif menu == "Customers":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);">
        <h2>👥 Customers</h2>
    </div>
    """, unsafe_allow_html=True)
    
    df = pd.read_sql("SELECT * FROM customers", conn)
    if df.empty:
        st.info("📭 No customers yet")
    else:
        # Summary
        total_customers = len(df)
        total_points = df['points'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>👥</h3>
                <h4>Total Customers</h4>
                <h2>{total_customers}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>⭐</h3>
                <h4>Total Points</h4>
                <h2>{total_points}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        st.dataframe(df, use_container_width=True)
        
        # Edit/Delete
        st.markdown("### ✏️ Edit / Delete Customers")
        for _, row in df.iterrows():
            with st.expander(f"{row['name']} — {row['phone']} — Points: {row['points']}"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_cust_{row['phone']}", use_container_width=True):
                        with st.form(f"edit_cust_form_{row['phone']}"):
                            name = st.text_input("Name", value=row['name'])
                            phone = st.text_input("Phone", value=row['phone'])
                            points = st.number_input("Points", value=int(row['points'] or 0))
                            
                            if st.form_submit_button("💾 Save", use_container_width=True):
                                if phone != row['phone']:
                                    c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                                    c.execute("INSERT OR REPLACE INTO customers (phone,name,points) VALUES (?,?,?)", 
                                             (phone, name, points))
                                else:
                                    c.execute("UPDATE customers SET name=?, points=? WHERE phone=?", (name, points, phone))
                                conn.commit()
                                st.success("Customer updated")
                                st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete", key=f"del_cust_{row['phone']}", use_container_width=True, type="secondary"):
                        c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                        conn.commit()
                        st.success("Deleted customer")
                        st.rerun()

# -------------------------- WASTE --------------------------
elif menu == "Waste":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #f46b45 0%, #eea849 100%);">
        <h2>🗑 Record Waste</h2>
    </div>
    """, unsafe_allow_html=True)
    
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("📭 No inventory")
    else:
        # Record waste form
        with st.form("waste_form", clear_on_submit=True):
            veg = st.selectbox("🥬 Vegetable", items['vegetable'])
            col1, col2 = st.columns(2)
            with col1:
                qty_kg = st.number_input("⚖️ Wasted kg", min_value=0.0, step=0.5, value=0.0)
            with col2:
                qty_g = st.number_input("⚖️ Wasted grams", min_value=0, step=100, value=0)
            qty = qty_kg + (qty_g / 1000)
            reason = st.text_input("📝 Reason", placeholder="Why was this wasted?")
            
            if st.form_submit_button("💾 Save Waste", use_container_width=True, type="primary"):
                current = get_stock(veg)[0]
                if qty <= 0:
                    st.error("Enter a positive quantity")
                elif current < qty:
                    st.error(f"Not enough stock! Available: {current:.3f} kg")
                else:
                    c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                             (selected_date.strftime("%Y-%m-%d"), veg, qty, reason))
                    c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                    conn.commit()
                    st.markdown(f"""
                    <div class="alert-warning">
                        <h4>✅ Waste Recorded</h4>
                        <p><strong>{qty:.3f} kg</strong> of <strong>{veg}</strong> marked as waste.</p>
                        <p><strong>Reason:</strong> {reason}</p>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Display waste records
    df = fetch_table_with_rowid("waste")
    if not df.empty:
        df = df[df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if df.empty:
        st.info(f"📭 No waste recorded for {selected_date.strftime('%d %B %Y')}")
    else:
        total_waste = df['quantity'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <h3>⚠️</h3>
            <h4>Total Waste Today</h4>
            <h2>{total_waste:.2f} kg</h2>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df.drop(columns=["rowid"]), use_container_width=True)

# -------------------------- DOWNLOAD --------------------------
elif menu == "Download":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);">
        <h2>⬇ Download Records</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"### 📅 Data for {selected_date.strftime('%d %B %Y')}")
    
    download_cols = st.columns(3)
    tables = [
        ("inventory", "📦 Inventory"),
        ("purchases", "🛒 Purchases"),
        ("sales", "💰 Sales"),
        ("waste", "🗑 Waste"),
        ("customers", "👥 Customers"),
        ("expenses", "💸 Expenses")
    ]
    
    for idx, (table, label) in enumerate(tables):
        with download_cols[idx % 3]:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
            if not df.empty:
                if table in ["purchases", "sales", "waste", "expenses"]:
                    df = df[df['date'] == selected_date.strftime("%Y-%m-%d")]
            
            if df.empty:
                st.info(f"No {label} data")
            else:
                csv = df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 {label}",
                    data=csv,
                    file_name=f"{table}_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

# -------------------------- FINANCIALS --------------------------
elif menu == "Financials":
    st.markdown("""
    <div class="header-card" style="background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);">
        <h2>💼 Financials — Sales, Cost & Profit</h2>
    </div>
    """, unsafe_allow_html=True)
    
    d = selected_date.strftime("%Y-%m-%d")
    
    # Get financial data
    sales_data = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", 
                           conn, params=(d,))["total"].iloc[0]
    cost_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", 
                          conn, params=(d,))["total"].iloc[0]
    expenses_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE date=?", 
                              conn, params=(d,))["total"].iloc[0]
    
    profit = sales_data - cost_data - expenses_data
    
    # Display metrics with colors
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 5px solid #4CAF50;">
            <h3>💰</h3>
            <h4>Sales</h4>
            <h2>₹{sales_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 5px solid #FF5722;">
            <h3>📦</h3>
            <h4>Cost</h4>
            <h2>₹{cost_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 5px solid #9C27B0;">
            <h3>💸</h3>
            <h4>Expenses</h4>
            <h2>₹{expenses_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        profit_color = "#4CAF50" if profit >= 0 else "#F44336"
        profit_icon = "📈" if profit >= 0 else "📉"
        st.markdown(f"""
        <div class="metric-card" style="border-top: 5px solid {profit_color};">
            <h3>{profit_icon}</h3>
            <h4>Profit</h4>
            <h2 style="color: {profit_color};">₹{profit:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Sales records
    st.markdown("### 📊 Sales Records for Today")
    df = pd.read_sql("SELECT * FROM sales WHERE date=?", conn, params=(d,))
    if df.empty:
        st.info("No sales for selected date")
    else:
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Download sales CSV", 
                         df.to_csv(index=False).encode(), 
                         f"sales_{d}.csv",
                         use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>🥕 Fresh Basket — Smart Vegetable Shop Management System | Updated with enhanced UI and easy vegetable selection ✅</p>
</div>
""", unsafe_allow_html=True)
