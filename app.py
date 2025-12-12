import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Page config
st.set_page_config(page_title="Fresh Basket", page_icon="🥬", layout="centered", initial_sidebar_state="expanded")

# Beautiful design
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #d4edda, #f8d7da);}
    h1 {text-align: center; color: #155724; font-size: 2.5em;}
    .stButton>button {background-color: #28a745; color: white; height: 3em; width: 100%; border-radius: 12px; font-size: 18px;}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {font-size: 18px; height: 3em;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?fresh-vegetables,market", use_column_width=True)
st.markdown("<h1>🌿 Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: green;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# Database
@st.cache_resource
def init_db():
    conn = sqlite3.connect("shop.db", check_same_thread=False)
    c = conn.cursor()
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
    return conn

conn = init_db()

# Helpers
def get_qty(veg, conn):
    c = conn.cursor()
    c.execute("SELECT quantity FROM inventory WHERE vegetable=?", (veg,))
    r = c.fetchone()
    return r[0] if r else 0

def add_purchase(veg, qty, cost, supplier, img="", conn=conn):
    date = datetime.now().strftime("%Y-%m-%d")
    c = conn.cursor()
    c.execute("INSERT INTO purchases VALUES (?, ?, ?, ?, ?)", (date, veg, qty, cost, supplier))
    new_qty = qty + get_qty(veg, conn)
    unit_price = cost / qty if qty > 0 else 0
    c.execute("INSERT OR REPLACE INTO inventory VALUES (?, ?, ?, ?)", (veg, new_qty, unit_price, img))
    conn.commit()

def get_low_stock(conn):
    return pd.read_sql("SELECT vegetable, quantity FROM inventory WHERE quantity < 5", conn)

# Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Sell", "Inventory", "Waste", "Customers", "Reports", "Download"])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    sales = pd.read_sql(f"SELECT COALESCE(SUM(total), 0) FROM sales WHERE date='{today}'", conn).iloc[0,0]
    cost = pd.read_sql(f"SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE date='{today}'", conn).iloc[0,0]
    profit = sales - cost
    col1, col2, col3 = st.columns(3)
    col1.metric("Sales", f"₹{sales:.2f}")
    col2.metric("Cost", f"₹{cost:.2f}")
    col3.metric("Profit", f"₹{profit:.2f}", delta="Today")
    low_stock = get_low_stock(conn)
    if not low_stock.empty:
        st.warning("Low Stock Alert!")
        st.dataframe(low_stock)

elif menu == "Add Purchase":
    st.header("Record Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier Name")
    img = st.text_input("Image URL (optional)")
    if st.button("Save Purchase") and veg and qty > 0:
        add_purchase(veg, qty, cost, supplier, img, conn)
        st.success(f"Added {qty} kg of {veg}!")
        st.rerun()

elif menu == "Sell":
    st.header("Sell Vegetables")
    customer_name = st.text_input("Customer Name (optional)")
    customer_phone = st.text_input("Customer Phone (for loyalty points)")
    if "cart" not in st.session_state:
        st.session_state.cart = []
    
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Select Vegetable", vegs)
        qty_sold = st.number_input("Quantity (kg)", min_value=0.0, step=0.1)
        price = st.number_input("Price per kg ₹", min_value=0.0)
        
        if st.button("Add to Cart"):
            current_qty = get_qty(veg, conn)
            if current_qty >= qty_sold:
                st.session_state.cart.append([veg, qty_sold, price, qty_sold * price])
                st.success("Added to cart!")
            else:
                st.error(f"Not enough stock! Only {current_qty} kg available.")
    
    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item", "Kg", "₹/kg", "Total"])
        st.table(df)
        total = df["Total"].sum()
        st.write(f"**Total Bill: ₹{total:.2f}**")
        
        col1, col2 = st.columns(2)
        if col1.button("Complete Sale"):
            date = datetime.now().strftime("%Y-%m-%d")
            customer = f"{customer_name} ({customer_phone})" if customer_phone else customer_name or "Guest"
            c = conn.cursor()
            for item in st.session_state.cart:
                v, q, p, t = item
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (q, v))
                c.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", (date, v, q, p, t, customer))
            if customer_phone:
                c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?, ?)", (customer_phone, customer_name))
                points = int(total // 10)
                c.execute("UPDATE customers SET points = points + ? WHERE phone = ?", (points, customer_phone))
                st.info(f"Awarded {points} loyalty points!")
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success(f"Sale completed! Total: ₹{total:.2f}")
        
        if col2.button("Print/Share Bill"):
            bill = f"Fresh Basket Bill\nCustomer: {customer}\nDate: {date}\n\n" + "\n".join(df.to_string(index=False).split("\n")[1:]) + f"\nTotal: ₹{total:.2f}"
            st.text_area("Copy & Share this Bill", bill, height=150)
        
        if st.button("Clear Cart"):
            st.session_state.cart = []

elif menu == "Inventory":
    st.header("Current Stock")
    df = pd.read_sql("SELECT * FROM inventory", conn)
    if not df.empty:
        for _, row in df.iterrows():
            col1, col2 = st.columns([1, 4])
            if row['image_url']:
                col1.image(row['image_url'], width=80, caption=row['vegetable'])
            col2.markdown(f"**{row['vegetable']}**: {row['quantity']} kg @ ₹{row['unit_price']:.2f}/kg")
        st.dataframe(df)
    else:
        st.info("No inventory yet. Add purchases first!")

elif menu == "Waste":
    st.header("Record Waste")
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    if vegs:
        veg = st.selectbox("Vegetable", vegs)
        qty = st.number_input("Quantity Wasted (kg)", min_value=0.0, step=0.1)
        reason = st.text_input("Reason")
        if st.button("Record Waste"):
            current_qty = get_qty(veg, conn)
            if current_qty >= qty:
                c = conn.cursor()
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (qty, veg))
                date = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO waste VALUES (?, ?, ?, ?)", (date, veg, qty, reason))
                conn.commit()
                st.success("Waste recorded!")
            else:
                st.error("Not enough stock!")

elif menu == "Customers":
    st.header("Customers & Loyalty")
    df = pd.read_sql("SELECT * FROM customers", conn)
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No customers yet.")
    phone = st.text_input("Phone to Redeem Points")
    redeem = st.number_input("Points to Redeem", min_value=0)
    if st.button("Redeem Points"):
        c = conn.cursor()
        c.execute("UPDATE customers SET points = points - ? WHERE phone = ? AND points >= ?", (redeem, phone, redeem))
        conn.commit()
        st.success("Points redeemed!")

elif menu == "Reports":
    st.header("Sales Reports")
    sales_df = pd.read_sql("SELECT date, SUM(total) as daily_sales FROM sales GROUP BY date ORDER BY date", conn)
    if not sales_df.empty:
        st.bar_chart(sales_df.set_index('date')['daily_sales'])
        st.dataframe(pd.read_sql("SELECT * FROM sales ORDER BY date DESC", conn))
    else:
        st.info("No sales data yet.")

elif menu == "Download":
    st.header("Download Data")
    tables = ["inventory", "purchases", "sales", "waste", "customers"]
    for t in tables:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"Download {t.title()}.csv", csv, f"{t}.csv", "text/csv")

conn.close()
