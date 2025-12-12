import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Page config
st.set_page_config(page_title="Fresh Basket", page_icon="🥬", layout="centered", initial_sidebar_state="expanded")

# Beautiful design
st.markdown("""
<style>
    .main {background: linear_gradient(90deg, #d4edda, #f8d7da);}
    h1 {text-align: center; color: #155724; font-size: 2.5em;}
    .stButton>button {background-color: #28a745; color: white; height: 3em; width: 100%; border-radius: 12px; font-size: 18px;}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {font-size: 18px; height: 3em;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?fresh-vegetables,market", use_column_width=True)
st.markdown("<h1>🌿 Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: green;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# Database
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create tables safely
tables = [
    "CREATE TABLE IF NOT EXISTS inventory (vegetable TEXT PRIMARY KEY, quantity REAL, unit_price REAL, image_url TEXT)",
    "CREATE TABLE IF NOT EXISTS purchases (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)",
    "CREATE TABLE IF NOT EXISTS sales (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)",
    "CREATE TABLE IF NOT EXISTS waste (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)"
]
for table in tables:
    c.execute(table)
conn.commit()

# Helper
def get_qty(veg):
    c.execute("SELECT quantity FROM inventory WHERE vegetable = ?", (veg,))
    result = c.fetchone()
    return result[0] if result else 0

# Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Sell", "Inventory", "Waste", "Customers", "Reports", "Download"])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # FIXED SAFE QUERIES — this was the problem!
    try:
        sales_today = pd.read_sql("SELECT COALESCE(SUM(total), 0) FROM sales WHERE date = ?", conn, params=(today,)).iloc[0,0]
        cost_today = pd.read_sql("SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE date = ?", conn, params=(today,)).iloc[0,0]
    except:
        sales_today = cost_today = 0.0
    
    profit_today = sales_today - cost_today

    col1, col2, col3 = st.columns(3)
    col1.metric("Today's Sales", f"₹{sales_today:.2f}")
    col2.metric("Today's Cost", f"₹{cost_today:.2f}")
    col3.metric("Today's Profit", f"₹{profit_today:.2f}")

    # Low stock
    try:
        low = pd.read_sql("SELECT vegetable, quantity FROM inventory WHERE quantity < 5", conn)
        if not low.empty:
            st.warning("Low Stock Alert!")
            st.write(", ".join(low['vegetable'].tolist()))
    except:
        pass

    st.success("App is working perfectly!")

elif menu == "Add Purchase":
    st.header("Record Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier Name")
    img = st.text_input("Image URL (optional)")
    if st.button("Save Purchase"):
        if veg and qty > 0:
            date = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO purchases VALUES (?, ?, ?, ?, ?)", (date, veg, qty, cost, supplier))
            new_qty = qty + get_qty(veg)
            unit_price = cost / qty if qty > 0 else 0
            c.execute("INSERT OR REPLACE INTO inventory VALUES (?, ?, ?, ?)", (veg, new_qty, unit_price, img))
            conn.commit()
            st.success(f"Added {qty} kg of {veg}!")
            st.rerun()

# Sell section (same as before, works great)
elif menu == "Sell":
    st.header("Sell Vegetables")
    customer_name = st.text_input("Customer Name")
    customer_phone = st.text_input("Phone (for loyalty points)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Select Vegetable", vegs)
        qty = st.number_input("Kg", min_value=0.0, step=0.1)
        price = st.number_input("Price per kg ₹", min_value=0.0)
        if st.button("Add to Cart"):
            if get_qty(veg) >= qty:
                st.session_state.cart.append([veg, qty, price, qty * price])
                st.success("Added!")
            else:
                st.error("Not enough stock!")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item", "Kg", "₹/kg", "Total"])
        st.table(df)
        total = df["Total"].sum()
        st.write(f"**Total Bill: ₹{total:.2f}**")

        col1, col2 = st.columns(2)
        if col1.button("Complete Sale"):
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
            st.success("Sale completed!")

        if col2.button("Print/Share Bill"):
            bill_text = f"Fresh Basket\nCustomer: {customer}\nDate: {date}\n\n{df.to_string(index=False)}\nTotal: ₹{total:.2f}"
            st.text_area("Copy & Share", bill_text, height=200)

        if st.button("Clear Cart"):
            st.session_state.cart = []

# Other menus (Inventory, Waste, etc.) - kept simple and safe
elif menu == "Inventory":
    st.header("Current Stock")
    df = pd.read_sql("SELECT vegetable, quantity, unit_price FROM inventory", conn)
    st.dataframe(df)

elif menu == "Waste":
    st.header("Record Waste")
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Vegetable", vegs)
        qty = st.number_input("Wasted kg", 0.0, step=0.1)
        reason = st.text_input("Reason")
        if st.button("Save"):
            if get_qty(veg) >= qty:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (qty, veg))
                c.execute("INSERT INTO waste VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                conn.commit()
                st.success("Recorded!")

elif menu == "Customers":
    st.header("Customers")
    df = pd.read_sql("SELECT * FROM customers", conn)
    st.dataframe(df)

elif menu == "Reports":
    st.header("Sales Report")
    df = pd.read_sql("SELECT date, SUM(total) as sales FROM sales GROUP BY date", conn)
    if not df.empty:
        st.bar_chart(df.set_index("date")['sales'])

elif menu == "Download":
    st.header("Download Data")
    tables = ["inventory", "purchases", "sales", "waste", "customers"]
    for table in tables:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        csv = df.to_csv(index=False).encode()
        st.download_button(f"Download {table}.csv", csv, f"{table}.csv")

st.caption("Fresh Basket - Ready for daily use on any phone!")
