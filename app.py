import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# Page config
st.set_page_config(page_title="Fresh Basket", page_icon="🥬", layout="centered", initial_sidebar_state="expanded")

# Colorful UI CSS
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #d4edda, #f8d7da);}
    h1, h2 {color: #155724;}
    .stButton>button {border-radius: 10px; font-size: 18px;}
    .stButton>button[kind="primary"] {background-color: #4CAF50; color: white;}
    .stButton>button[kind="secondary"] {background-color: #f44336; color: white;}
    .stSuccess {color: #4CAF50;}
    .stWarning {color: #f44336;}
    .stInfo {color: #2196F3;}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {font-size: 18px;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?fresh-vegetables,market", use_column_width=True)
st.markdown("<h1>🌿 Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: green;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# Database
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create tables (fixed syntax)
c.executescript('''
    CREATE TABLE IF NOT EXISTS inventory (
        vegetable TEXT PRIMARY KEY,
        quantity REAL,
        cost_price REAL,
        selling_price REAL,
        image_url TEXT
    );
    CREATE TABLE IF NOT EXISTS purchases (
        date TEXT,
        vegetable TEXT,
        quantity REAL,
        amount REAL,
        supplier TEXT
    );
    CREATE TABLE IF NOT EXISTS sales (
        date TEXT,
        vegetable TEXT,
        quantity_sold REAL,
        sale_price REAL,
        total REAL,
        customer TEXT
    );
    CREATE TABLE IF NOT EXISTS waste (
        date TEXT,
        vegetable TEXT,
        quantity REAL,
        reason TEXT
    );
    CREATE TABLE IF NOT EXISTS customers (
        phone TEXT PRIMARY KEY,
        name TEXT,
        points INTEGER DEFAULT 0
    );
''')

# Add selling_price column if missing
try:
    c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL")
except:
    pass
conn.commit()

# Helper: Get stock info (safe for None)
def get_stock_info(veg):
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable = ?", (veg,))
    result = c.fetchone()
    qty = result[0] if result and result[0] is not None else 0.0
    cost = result[1] if result and result[1] is not None else 0.0
    sell = result[2] if result and result[2] is not None else 0.0
    return qty, cost, sell

# Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Waste", "Customers", "Reports", "Download"])

if menu == "Dashboard":
    st.header("Dashboard")
    selected_date = st.date_input("Select Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total), 0) FROM sales WHERE date = ?", conn, params=(date_str,)).iloc[0,0]
    cost = pd.read_sql("SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE date = ?", conn, params=(date_str,)).iloc[0,0]
    profit = sales - cost

    col1, col2, col3 = st.columns(3)
    col1.metric("Sales", f"₹{sales:.2f}")
    col2.metric("Cost", f"₹{cost:.2f}")
    col3.metric("Profit", f"₹{profit:.2f}")

    low = pd.read_sql("SELECT vegetable, quantity FROM inventory WHERE quantity < 5 AND quantity > 0", conn)
    if not low.empty:
        st.warning("Low Stock Alert!")
        st.bar_chart(low.set_index("vegetable")["quantity"], use_container_width=True)

elif menu == "Add Purchase":
    st.header("Add Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier")
    img = st.text_input("Image URL (optional)")
    if st.button("Save Purchase", type="primary") and veg and qty > 0:
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO purchases VALUES (?, ?, ?, ?, ?)", (date, veg, qty, cost, supplier))
        old_qty, _, old_sell = get_stock_info(veg)
        new_qty = old_qty + qty
        unit_cost = cost / qty if qty > 0 else 0
        c.execute("INSERT OR REPLACE INTO inventory VALUES (?, ?, ?, ?, ?)", (veg, new_qty, unit_cost, old_sell, img))
        conn.commit()
        st.success(f"Added {qty} kg of {veg}! Total stock: {new_qty} kg 🎉")

elif menu == "Set Selling Prices":
    st.header("Set Selling Prices")
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Select Vegetable", vegs)
        current_qty, current_cost, current_sell = get_stock_info(veg)
        st.write(f"Stock: {current_qty:.2f} kg | Cost/kg: ₹{current_cost:.2f}")
        new_price = st.number_input("Selling Price per kg ₹", min_value=0.0, value=current_sell)
        if st.button("Update Price", type="primary"):
            c.execute("UPDATE inventory SET selling_price = ? WHERE vegetable = ?", (new_price, veg))
            conn.commit()
            st.success(f"Updated price for {veg} to ₹{new_price:.2f}/kg 🎉")
    else:
        st.info("Add purchases first to set prices.")

elif menu == "Sell":
    st.header("Sell Vegetables")
    customer_name = st.text_input("Customer Name")
    customer_phone = st.text_input("Phone (for loyalty)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Select Vegetable", vegs)
        current_qty, _, selling_price = get_stock_info(veg)
        price = st.number_input("Price per kg ₹", min_value=0.0, value=selling_price)
        qty = st.number_input("Kg", min_value=0.0, step=0.1)
        if st.button("Add to Cart", type="primary"):
            if current_qty >= qty > 0:
                total_item = qty * price
                st.session_state.cart.append([veg, qty, price, total_item])
                st.success(f"Added {qty} kg {veg} @ ₹{price}/kg 🎉")
            else:
                st.error("Not enough stock!")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item", "Kg", "₹/kg", "Total"])
        st.table(df)
        total = df["Total"].sum()
        st.write(f"**Total Bill: ₹{total:.2f}**")

        col1, col2 = st.columns(2)
        if col1.button("Complete Sale", type="primary"):
            date = datetime.now().strftime("%Y-%m-%d")
            customer = f"{customer_name} ({customer_phone})" if customer_phone else customer_name or "Guest"
            for item in st.session_state.cart:
                v, q, p, t = item
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (q, v))
                c.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", (date, v, q, p, t, customer))
            if customer_phone:
                c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?, ?)", (customer_phone, customer_name))
                points = int(total // 10)
                c.execute("UPDATE customers SET points = points + ? WHERE phone = ?", (points, customer_phone))
                st.info(f"Added {points} loyalty points!")
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success("Sale completed! 🎉")

        if col2.button("Print/Share Bill"):
            bill_text = f"Fresh Basket\nCustomer: {customer}\nDate: {date}\n\n" + df.to_string(index=False) + f"\nTotal: ₹{total:.2f}"
            st.text_area("Copy Bill", bill_text, height=200)

        if st.button("Clear Cart", type="secondary"):
            st.session_state.cart = []

elif menu == "Inventory":
    st.header("Inventory")
    df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
    if not df.empty:
        df.columns = ["Vegetable", "Quantity (kg)", "Cost/kg", "Sell/kg"]
        st.dataframe(df.style.format({"Quantity (kg)": "{:.2f}", "Cost/kg": "₹{:.2f}", "Sell/kg": "₹{:.2f}"}))
        veg = st.selectbox("Delete Vegetable", df["Vegetable"])
        if st.button("Delete Item", type="secondary"):
            c.execute("DELETE FROM inventory WHERE vegetable = ?", (veg,))
            conn.commit()
            st.success(f"Deleted {veg} from inventory 🎉")
            st.rerun()
    else:
        st.info("No inventory yet.")

elif menu == "Waste":
    st.header("Waste")
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Vegetable", vegs)
        qty = st.number_input("Wasted (kg)", min_value=0.0, step=0.1)
        reason = st.text_input("Reason")
        if st.button("Save Waste", type="primary"):
            current_qty, _, _ = get_stock_info(veg)
            if current_qty >= qty:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (qty, veg))
                c.execute("INSERT INTO waste VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                conn.commit()
                st.success("Waste recorded! 🎉")
    else:
        st.info("No inventory yet.")

elif menu == "Customers":
    st.header("Customers")
    df = pd.read_sql("SELECT * FROM customers", conn)
    if not df.empty:
        st.dataframe(df)
        phone = st.text_input("Phone to Redeem")
        points = st.number_input("Points to Redeem", min_value=0)
        if st.button("Redeem", type="primary"):
            c.execute("UPDATE customers SET points = points - ? WHERE phone = ? AND points >= ?", (points, phone, points))
            conn.commit()
            st.success("Points redeemed! 🎉")
    else:
        st.info("No customers yet.")

elif menu == "Reports":
    st.header("Reports")
    selected_date = st.date_input("Select Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")
    sales_df = pd.read_sql("SELECT * FROM sales WHERE date = ?", conn, params=(date_str,))
    if not sales_df.empty:
        st.dataframe(sales_df)
    else:
        st.info("No sales on this date.")

elif menu == "Download":
    st.header("Download")
    for table in ["inventory", "purchases", "sales", "waste", "customers"]:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        csv = df.to_csv(index=False).encode()
        st.download_button(f"Download {table}.csv", csv, f"{table}.csv", type="primary")

st.caption("Fresh Basket - All pages working with colorful UI! 🎉")
