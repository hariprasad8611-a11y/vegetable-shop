import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🥕", layout="centered")
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #e8f5e9, #fff8e1);}
    h1 {text-align:center; color:#1b5e20; font-size:2.4em;}
    .stButton>button {height:3em; border-radius:12px; font-size:16px;}
    .primary-btn {background:#2e7d32 !important; color:white !important;}
    .secondary-btn {background:#d32f2f !important; color:white !important;}
    .muted {color:#6b7280; font-size:0.9rem;}
    .small {font-size:0.9rem}
    .alert {background:#fff3cd; padding:12px; border-radius:8px; margin-bottom:8px;}
    .cart-item {background:#f8f9fa; padding:10px; border-radius:8px; margin:5px 0;}
    .veg-card {background:white; padding:12px; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1); margin:8px 0;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:green;font-size:16px;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

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

# ensure session state keys
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of [veg, qty, price, total]
if "shortage_threshold" not in st.session_state:
    st.session_state.shortage_threshold = 5.0  # default threshold in kg
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()

# ========================== SIDEBAR MENU ==========================
menu = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Purchases", "Sales", "Expenses", "Customers", "Waste", "Download", "Financials"]
)

# Date selector in sidebar for all pages
selected_date = st.sidebar.date_input("Select Date", value=st.session_state.selected_date)
st.session_state.selected_date = selected_date
st.sidebar.markdown(f"**Selected Date:** {selected_date.strftime('%d-%m-%Y')}")

# -------------------------- DASHBOARD --------------------------
if menu == "Dashboard":
    st.header("📊 Dashboard — Vegetable Shortage Alerts")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    # threshold control
    threshold = st.number_input("Shortage threshold (kg) — items below this are flagged", 
                               min_value=0.0, value=float(st.session_state.shortage_threshold), step=1.0)
    st.session_state.shortage_threshold = threshold
    
    inv = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory", conn)
    if inv.empty:
        st.info("No inventory available yet.")
    else:
        inv = inv.sort_values("quantity")
        low = inv[(inv["quantity"] > 0) & (inv["quantity"] < threshold)]
        zero = inv[inv["quantity"] <= 0]
        
        if zero.empty and low.empty:
            st.success("All good — no shortages right now 👍")
        else:
            st.markdown("### Shortage Alerts")
            # first show items with zero stock (out of stock)
            if not zero.empty:
                for _, r in zero.iterrows():
                    veg = r["vegetable"]
                    st.markdown(f"<div class='alert'><b>{veg}</b> is <span style='color:#d9534f;'>out of stock</span>. Please reorder immediately. Suggested reorder: <b>10 kg</b>.</div>", unsafe_allow_html=True)
            # then low stock items
            if not low.empty:
                for _, r in low.iterrows():
                    veg = r["vegetable"]
                    qty = r["quantity"]
                    suggested = max(5.0, threshold * 2)  # simple rule: suggest at least 5 or twice threshold
                    st.markdown(f"<div class='alert'><b>{veg}</b> running low — only <b>{qty:.2f} kg</b> left. Suggested reorder: <b>{suggested:.0f} kg</b>.</div>", unsafe_allow_html=True)
        
        # Helpful summary table
        st.markdown("### Inventory Snapshot")
        inv_display = inv.copy()
        inv_display = safe_round_df(inv_display, ["quantity", "selling_price"])
        inv_display = inv_display.rename(columns={"vegetable": "Vegetable", "quantity": "Qty (kg)", "selling_price": "Sell/kg"})
        st.dataframe(inv_display)

# -------------------------- ADD PURCHASE --------------------------
elif menu == "Add Purchase":
    st.header("🛒 Add Purchase")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    with st.form("purchase_form"):
        veg = st.text_input("Vegetable Name")
        col1, col2 = st.columns(2)
        with col1:
            qty_kg = st.number_input("Quantity (kg)", min_value=0.0, step=0.5, value=1.0)
        with col2:
            qty_g = st.number_input("Quantity (grams)", min_value=0, step=100, value=0)
        qty = qty_kg + (qty_g / 1000)
        amount = st.number_input("Total Cost ₹", min_value=0.0)
        supplier = st.text_input("Supplier (optional)")
        
        submitted = st.form_submit_button("Save Purchase")
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
                st.success(f"Added {qty:.3f} kg of {veg} to purchases and inventory.")
    
    st.markdown("---")
    st.subheader(f"Purchases for {selected_date.strftime('%d %B %Y')}")
    pur_df = fetch_table_with_rowid("purchases")
    if not pur_df.empty:
        pur_df = pur_df[pur_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if pur_df.empty:
        st.info("No purchases for selected date")
    else:
        pur_df = safe_round_df(pur_df, ["quantity", "amount"])
        st.dataframe(pur_df.drop(columns=["rowid"]))

# -------------------------- SET SELLING PRICES --------------------------
elif menu == "Set Selling Prices":
    st.header("🏷 Set Selling Prices")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("No items in inventory")
    else:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        st.info(f"Current Stock: {qty:.2f} kg")
        new_price = st.number_input("Selling Price per kg ₹", value=float(sell or 0.0))
        if st.button("Update Price"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
            conn.commit()
            st.success("Selling price updated")

# -------------------------- SELL (Enhanced with better selection) --------------------------
elif menu == "Sell":
    st.header("💵 Sell Vegetables")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    # Customer details
    col1, col2 = st.columns(2)
    with col1:
        cust_name = st.text_input("Customer Name")
    with col2:
        cust_phone = st.text_input("Customer Phone")
    
    # Get inventory
    inventory = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory WHERE quantity > 0 ORDER BY vegetable", conn)
    
    if inventory.empty:
        st.info("No items in inventory")
    else:
        st.markdown("### Select Vegetables to Sell")
        
        # Initialize session state for current selection
        if "current_selection" not in st.session_state:
            st.session_state.current_selection = {"vegetable": "", "kg": 0.0, "grams": 0}
        
        # Create selection form
        with st.form("add_to_cart_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Vegetable selector with stock info
                veg_options = []
                for _, row in inventory.iterrows():
                    stock_display = f"{row['vegetable']} (Stock: {row['quantity']:.2f} kg, ₹{row['selling_price']:.2f}/kg)"
                    veg_options.append((row['vegetable'], stock_display))
                
                selected_veg_display = st.selectbox(
                    "Select Vegetable",
                    options=[v[1] for v in veg_options],
                    format_func=lambda x: x
                )
                
                # Get selected vegetable name
                selected_veg = next(v[0] for v in veg_options if v[1] == selected_veg_display)
                
                # Show selected vegetable price
                selected_row = inventory[inventory['vegetable'] == selected_veg].iloc[0]
                st.caption(f"Price: ₹{selected_row['selling_price']:.2f}/kg")
            
            with col2:
                kg_amount = st.number_input("Kilograms", min_value=0.0, step=0.5, value=0.0)
            
            with col3:
                gram_amount = st.number_input("Grams", min_value=0, step=100, value=0, max_value=999)
            
            total_qty = kg_amount + (gram_amount / 1000)
            total_price = total_qty * selected_row['selling_price']
            
            st.markdown(f"**Total Quantity:** {total_qty:.3f} kg")
            st.markdown(f"**Total Price:** ₹{total_price:.2f}")
            
            col1, col2 = st.columns(2)
            with col1:
                add_to_cart = st.form_submit_button("➕ Add to Cart", type="primary")
            with col2:
                quick_add_500g = st.form_submit_button("➕ Add 500g")
        
        if add_to_cart:
            if total_qty <= 0:
                st.error("Please enter quantity greater than 0")
            else:
                # Check stock availability
                available_stock = get_stock(selected_veg)[0]
                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_veg)
                
                if current_in_cart + total_qty > available_stock:
                    st.error(f"Not enough stock! Available: {available_stock:.3f} kg, In cart: {current_in_cart:.3f} kg, Requested: {total_qty:.3f} kg")
                else:
                    # Check if already in cart
                    found = False
                    for i, item in enumerate(st.session_state.cart):
                        if item[0] == selected_veg and item[2] == selected_row['selling_price']:
                            st.session_state.cart[i][1] += total_qty
                            st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * selected_row['selling_price'], 2)
                            found = True
                            break
                    
                    if not found:
                        st.session_state.cart.append([
                            selected_veg,
                            total_qty,
                            selected_row['selling_price'],
                            round(total_price, 2)
                        ])
                    
                    st.success(f"Added {total_qty:.3f} kg of {selected_veg} to cart")
                    st.rerun()
        
        if quick_add_500g:
            quick_qty = 0.5  # 500g = 0.5kg
            available_stock = get_stock(selected_veg)[0]
            current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_veg)
            
            if current_in_cart + quick_qty > available_stock:
                st.error(f"Not enough stock! Available: {available_stock:.3f} kg")
            else:
                found = False
                for i, item in enumerate(st.session_state.cart):
                    if item[0] == selected_veg and item[2] == selected_row['selling_price']:
                        st.session_state.cart[i][1] += quick_qty
                        st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * selected_row['selling_price'], 2)
                        found = True
                        break
                
                if not found:
                    st.session_state.cart.append([
                        selected_veg,
                        quick_qty,
                        selected_row['selling_price'],
                        round(quick_qty * selected_row['selling_price'], 2)
                    ])
                
                st.success(f"Added 500g of {selected_veg} to cart")
                st.rerun()
        
        # Display current cart
        st.markdown("---")
        st.subheader("🛒 Current Cart")
        
        if not st.session_state.cart:
            st.info("Cart is empty. Add items from above.")
        else:
            # Create cart display
            cart_items = []
            total_amount = 0
            
            for item in st.session_state.cart:
                veg_name, qty, price_per_kg, total = item
                
                # Convert to kg and grams for display
                kg = int(qty)
                grams = int((qty - kg) * 1000)
                
                if grams > 0:
                    qty_display = f"{kg} kg {grams} g" if kg > 0 else f"{grams} g"
                else:
                    qty_display = f"{kg} kg"
                
                cart_items.append({
                    "Vegetable": veg_name,
                    "Quantity": qty_display,
                    "Price/kg": f"₹{price_per_kg:.2f}",
                    "Total": f"₹{total:.2f}"
                })
                total_amount += total
            
            # Display cart as dataframe
            cart_df = pd.DataFrame(cart_items)
            st.dataframe(cart_df, use_container_width=True)
            
            st.markdown(f"### **Total Amount: ₹{total_amount:.2f}**")
            
            # Cart management buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Complete Sale", type="primary", use_container_width=True):
                    # Validate stock and process sale
                    insufficient = []
                    for veg_name, qty, price, total in st.session_state.cart:
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
                        for veg_name, qty, price, total in st.session_state.cart:
                            c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", 
                                     (d, veg_name, qty, price, total, cust))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg_name))
                            
                            # Add to sale details for display
                            sale_details.append(f"{veg_name}: {qty:.3f} kg × ₹{price:.2f} = ₹{total:.2f}")
                        
                        # Update customer points
                        if cust_phone:
                            c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?,?)", 
                                     (cust_phone, cust_name))
                            points = int(total_amount // 10)
                            c.execute("UPDATE customers SET points = points + ? WHERE phone=?", 
                                     (points, cust_phone))
                        
                        conn.commit()
                        
                        # Display sale summary
                        st.success("✅ Sale Completed Successfully!")
                        st.balloons()
                        
                        st.markdown("### Sale Receipt")
                        st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
                        st.markdown(f"**Customer:** {cust}")
                        
                        for detail in sale_details:
                            st.markdown(f"- {detail}")
                        
                        st.markdown(f"**Total Bill:** ₹{total_amount:.2f}")
                        
                        if cust_phone:
                            new_points = pd.read_sql("SELECT points FROM customers WHERE phone=?", 
                                                    conn, params=(cust_phone,)).iloc[0]['points']
                            st.info(f"Customer now has {new_points} loyalty points")
                        
                        # Clear cart
                        st.session_state.cart = []
                        st.rerun()
            
            with col2:
                if st.button("🔄 Clear Cart", use_container_width=True):
                    st.session_state.cart = []
                    st.success("Cart cleared")
                    st.rerun()
            
            with col3:
                if st.button("✏️ Edit Cart", use_container_width=True):
                    # Show edit interface
                    st.markdown("### Edit Cart Items")
                    for i, item in enumerate(st.session_state.cart):
                        veg_name, qty, price, total = item
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.write(f"**{veg_name}**")
                        
                        with col2:
                            new_qty = st.number_input(f"Quantity (kg)", value=float(qty), 
                                                     min_value=0.0, step=0.1, key=f"edit_{i}")
                        
                        with col3:
                            if st.button("Update", key=f"update_{i}"):
                                if new_qty <= 0:
                                    st.session_state.cart.pop(i)
                                else:
                                    st.session_state.cart[i][1] = new_qty
                                    st.session_state.cart[i][3] = round(new_qty * price, 2)
                                st.success("Updated")
                                st.rerun()
                        
                        with col3:
                            if st.button("❌", key=f"delete_{i}"):
                                st.session_state.cart.pop(i)
                                st.success("Removed")
                                st.rerun()

# -------------------------- INVENTORY --------------------------
elif menu == "Inventory":
    st.header("📦 Inventory")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    df = pd.read_sql("SELECT rowid, vegetable, quantity, selling_price, image_url FROM inventory", conn)
    
    if df.empty:
        st.info("No stock available")
    else:
        df_display = df.copy()
        df_display = safe_round_df(df_display, ["quantity", "selling_price"])
        df_display = df_display.rename(columns={
            "vegetable": "Vegetable",
            "quantity": "Qty (kg)",
            "selling_price": "Sell/kg",
            "image_url": "Image URL"
        })
        
        # Display inventory with kg and grams
        st.subheader("Current Inventory")
        for _, row in df.iterrows():
            kg = int(row['quantity'])
            grams = int((row['quantity'] - kg) * 1000)
            
            if grams > 0:
                qty_display = f"{kg} kg {grams} g" if kg > 0 else f"{grams} g"
            else:
                qty_display = f"{kg} kg"
            
            st.markdown(f"""
            <div class='veg-card'>
                <b>{row['vegetable']}</b><br>
                Quantity: {qty_display}<br>
                Selling Price: ₹{row['selling_price']:.2f}/kg
            </div>
            """, unsafe_allow_html=True)
        
        # Edit interface
        st.markdown("### Edit Inventory")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3, 1, 1])
            with cols[0]:
                kg = int(row['quantity'])
                grams = int((row['quantity'] - kg) * 1000)
                qty_display = f"{kg} kg {grams} g" if grams > 0 else f"{kg} kg"
                st.write(f"**{row['vegetable']}** — {qty_display} — Sell ₹{row['selling_price'] or 0:.2f}")
            with cols[1]:
                if st.button("Edit", key=f"edit_inv_{int(row['rowid'])}"):
                    with st.form(f"edit_inv_form_{int(row['rowid'])}"):
                        new_name = st.text_input("Vegetable", value=row['vegetable'])
                        col1, col2 = st.columns(2)
                        with col1:
                            new_qty_kg = st.number_input("Kilograms", value=int(row['quantity']), min_value=0)
                        with col2:
                            new_qty_g = st.number_input("Grams", 
                                                       value=int((row['quantity'] - int(row['quantity'])) * 1000), 
                                                       min_value=0, max_value=999, step=100)
                        new_qty = new_qty_kg + (new_qty_g / 1000)
                        new_sell = st.number_input("Selling Price/kg", value=float(row['selling_price'] or 0.0))
                        
                        if st.form_submit_button("Save"):
                            if new_name != row['vegetable']:
                                c.execute("DELETE FROM inventory WHERE vegetable=?", (row['vegetable'],))
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)",
                                         (new_name, new_qty, 0.0, new_sell, row['image_url']))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                                         (new_qty, new_sell, row['vegetable']))
                            conn.commit()
                            st.success("Inventory updated")
                            st.rerun()
            with cols[2]:
                if st.button("Delete", key=f"del_inv_{int(row['rowid'])}"):
                    c.execute("DELETE FROM inventory WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted item")
                    st.rerun()

# -------------------------- PURCHASES --------------------------
elif menu == "Purchases":
    st.header("📋 Purchases")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    pur_df = fetch_table_with_rowid("purchases")
    if not pur_df.empty:
        pur_df = pur_df[pur_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if pur_df.empty:
        st.info(f"No purchases for {selected_date.strftime('%d %B %Y')}")
    else:
        pur_df2 = safe_round_df(pur_df.copy(), ["quantity", "amount"])
        st.dataframe(pur_df2.drop(columns=["rowid"]))
        
        st.markdown("### Edit / Delete purchases")
        for _, row in pur_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{row['date']} — {row['vegetable']} — {row['quantity']} kg — ₹{row['amount']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_pur2_{int(row['rowid'])}"):
                    with st.form(f"edit_pur2_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        nv = st.text_input("Vegetable", value=row['vegetable'])
                        col1, col2 = st.columns(2)
                        with col1:
                            nq_kg = st.number_input("Kilograms", value=int(row['quantity']), min_value=0)
                        with col2:
                            nq_g = st.number_input("Grams", 
                                                  value=int((row['quantity'] - int(row['quantity'])) * 1000), 
                                                  min_value=0, max_value=999, step=100)
                        nq = nq_kg + (nq_g / 1000)
                        na = st.number_input("Amount", value=float(row['amount']))
                        ns = st.text_input("Supplier", value=row['supplier'])
                        if st.form_submit_button("Save"):
                            c.execute("UPDATE purchases SET date=?, vegetable=?, quantity=?, amount=?, supplier=? WHERE rowid=?",
                                     (nd.strftime("%Y-%m-%d"), nv, nq, na, ns, int(row['rowid'])))
                            conn.commit()
                            st.success("Updated purchase")
                            st.rerun()
                if st.button("Delete", key=f"del_pur2_{int(row['rowid'])}"):
                    c.execute("DELETE FROM purchases WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.rerun()

# -------------------------- SALES --------------------------
elif menu == "Sales":
    st.header("🧾 Sales")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    sales_df = fetch_table_with_rowid("sales")
    if not sales_df.empty:
        sales_df = sales_df[sales_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if sales_df.empty:
        st.info(f"No sales for {selected_date.strftime('%d %B %Y')}")
    else:
        sales_df2 = safe_round_df(sales_df.copy(), ["quantity_sold", "sale_price", "total"])
        st.dataframe(sales_df2.drop(columns=["rowid"]))
        
        st.markdown("### Edit / Delete sales")
        for _, row in sales_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{row['date']} — {row['vegetable']} — {row['quantity_sold']} kg — ₹{row['total']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_sale_{int(row['rowid'])}"):
                    with st.form(f"edit_sale_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        nv = st.text_input("Vegetable", value=row['vegetable'])
                        col1, col2 = st.columns(2)
                        with col1:
                            nq_kg = st.number_input("Kilograms", value=int(row['quantity_sold']), min_value=0)
                        with col2:
                            nq_g = st.number_input("Grams", 
                                                  value=int((row['quantity_sold'] - int(row['quantity_sold'])) * 1000), 
                                                  min_value=0, max_value=999, step=100)
                        nq = nq_kg + (nq_g / 1000)
                        np = st.number_input("Price/kg", value=float(row['sale_price']))
                        if st.form_submit_button("Save"):
                            new_total = nq * np
                            c.execute("UPDATE sales SET date=?, vegetable=?, quantity_sold=?, sale_price=?, total=? WHERE rowid=?",
                                     (nd.strftime("%Y-%m-%d"), nv, nq, np, new_total, int(row['rowid'])))
                            conn.commit()
                            st.success("Sale updated")
                            st.rerun()
                if st.button("Delete", key=f"del_sale_{int(row['rowid'])}"):
                    c.execute("DELETE FROM sales WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted sale")
                    st.rerun()

# -------------------------- EXPENSES --------------------------
elif menu == "Expenses":
    st.header("💸 Expenses")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    exp_df = fetch_table_with_rowid("expenses")
    if not exp_df.empty:
        exp_df = exp_df[exp_df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if exp_df.empty:
        st.info(f"No expenses for {selected_date.strftime('%d %B %Y')}")
    else:
        st.dataframe(exp_df.drop(columns=["rowid"]))
        st.markdown("Edit / Delete expenses")
        for _, row in exp_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{row['date']} — {row['category']} — ₹{row['amount']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_exp_{int(row['rowid'])}"):
                    with st.form(f"edit_exp_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        cat = st.text_input("Category", value=row['category'])
                        amt = st.number_input("Amount", value=float(row['amount']))
                        desc = st.text_input("Description", value=row['description'])
                        if st.form_submit_button("Save"):
                            c.execute("UPDATE expenses SET date=?, category=?, amount=?, description=? WHERE rowid=?",
                                     (nd.strftime("%Y-%m-%d"), cat, amt, desc, int(row['rowid'])))
                            conn.commit()
                            st.success("Updated expense")
                            st.rerun()
                if st.button("Delete", key=f"del_exp_{int(row['rowid'])}"):
                    c.execute("DELETE FROM expenses WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.rerun()

# -------------------------- CUSTOMERS --------------------------
elif menu == "Customers":
    st.header("👥 Customers")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    df = pd.read_sql("SELECT * FROM customers", conn)
    if df.empty:
        st.info("No customers yet")
    else:
        st.dataframe(df)
        st.markdown("Edit / Delete customers")
        for _, row in df.iterrows():
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{row['name']} — {row['phone']} — Points: {row['points']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_cust_{row['phone']}"):
                    with st.form(f"edit_cust_form_{row['phone']}"):
                        name = st.text_input("Name", value=row['name'])
                        phone = st.text_input("Phone", value=row['phone'])
                        points = st.number_input("Points", value=int(row['points'] or 0))
                        if st.form_submit_button("Save"):
                            if phone != row['phone']:
                                c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                                c.execute("INSERT OR REPLACE INTO customers (phone,name,points) VALUES (?,?,?)", 
                                         (phone, name, points))
                            else:
                                c.execute("UPDATE customers SET name=?, points=? WHERE phone=?", (name, points, phone))
                            conn.commit()
                            st.success("Customer updated")
                            st.rerun()
                if st.button("Delete", key=f"del_cust_{row['phone']}"):
                    c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                    conn.commit()
                    st.success("Deleted customer")
                    st.rerun()

# -------------------------- WASTE --------------------------
elif menu == "Waste":
    st.header("🗑 Record Waste")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("No inventory")
    else:
        veg = st.selectbox("Vegetable", items['vegetable'])
        col1, col2 = st.columns(2)
        with col1:
            qty_kg = st.number_input("Wasted kg", min_value=0.0, step=0.5, value=0.0)
        with col2:
            qty_g = st.number_input("Wasted grams", min_value=0, step=100, value=0)
        qty = qty_kg + (qty_g / 1000)
        reason = st.text_input("Reason")
        if st.button("Save Waste"):
            current = get_stock(veg)[0]
            if qty <= 0:
                st.error("Enter a positive quantity")
            elif current < qty:
                st.error("Not enough stock")
            else:
                c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                         (selected_date.strftime("%Y-%m-%d"), veg, qty, reason))
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                conn.commit()
                st.success("Waste recorded")
    
    df = fetch_table_with_rowid("waste")
    if not df.empty:
        df = df[df['date'] == selected_date.strftime("%Y-%m-%d")]
    
    if df.empty:
        st.info(f"No waste recorded for {selected_date.strftime('%d %B %Y')}")
    else:
        st.dataframe(df.drop(columns=["rowid"]))

# -------------------------- DOWNLOAD --------------------------
elif menu == "Download":
    st.header("⬇ Download Records")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    for t in ["inventory", "purchases", "sales", "waste", "customers", "expenses"]:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        if not df.empty:
            # Filter by selected date for relevant tables
            if t in ["purchases", "sales", "waste", "expenses"]:
                df = df[df['date'] == selected_date.strftime("%Y-%m-%d")]
        
        if df.empty:
            st.info(f"No records in {t} for selected date")
        else:
            st.download_button(f"Download {t}.csv", df.to_csv(index=False).encode(), f"{t}_{selected_date.strftime('%Y%m%d')}.csv")

# -------------------------- FINANCIALS --------------------------
elif menu == "Financials":
    st.header("💼 Financials — Sales, Cost & Profit")
    st.markdown(f"**Date:** {selected_date.strftime('%d %B %Y')}")
    
    d = selected_date.strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", 
                       conn, params=(d,))["total"].iloc[0]
    cost = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", 
                      conn, params=(d,))["total"].iloc[0]
    profit = sales - cost
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sales", f"₹{sales:.2f}")
    with col2:
        st.metric("Cost", f"₹{cost:.2f}")
    with col3:
        st.metric("Profit", f"₹{profit:.2f}", 
                 delta_color="inverse" if profit < 0 else "normal")
    
    st.markdown("### Sales Records for selected date")
    df = pd.read_sql("SELECT * FROM sales WHERE date=?", conn, params=(d,))
    if df.empty:
        st.info("No sales")
    else:
        st.dataframe(df)
        st.download_button("Download sales CSV", df.to_csv(index=False).encode(), f"sales_{d}.csv")

st.caption("Fresh Basket — Updated: Easy vegetable selection with kg/gram options, date-based filtering ✅")
