import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Page config
st.set_page_config(page_title="Fresh Basket", page_icon="Vegetables", layout="centered")

# Beautiful design
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #d4edda, #f8d7da);}
    h1 {text-align: center; color: #155724; font-size: 2.5em;}
    .stButton>button {background-color: #28a745; color: white; height: 3em; width: 100%; border-radius: 12px; font-size: 18px;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?fresh-vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: green;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# Database
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

for table in [
    "inventory(vegetable TEXT PRIMARY KEY, quantity REAL, unit_price REAL, image_url TEXT)",
    "purchases(date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)",
    "sales(date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)",
    "waste(date TEXT, vegetable TEXT, quantity REAL, reason TEXT)",
    "customers(phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)"
]:
    c.execute(f"CREATE TABLE IF NOT EXISTS {table}")
conn.commit()

# Helpers
def get_qty(veg): 
    c.execute("SELECT quantity FROM inventory WHERE vegetable=?", (veg,))
    r = c.fetchone()
    return r[0] if r else 0

# Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Sell", "Inventory", "Waste", "Customers", "Reports", "Download"])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    sales = pd.read_sql(f"SELECT COALESCE(SUM(total),0) FROM sales WHERE date='{today}'", conn).iloc[0,0]
    cost = pd.read_sql(f"SELECT COALESCE(SUM(amount),0) FROM purchases WHERE date='{today}'", conn).iloc[0,0]
    profit = sales - cost
    c1, c2, c3 = st.columns(3)
    c1.metric("Sales", f"₹{sales:.2f}")
    c2.metric("Cost", f"₹{cost:.2f}")
    c3.metric("Profit", f"₹{profit:.2f}", delta="Today")
    if get_qty := pd.read_sql("SELECT vegetable FROM inventory WHERE quantity < 5", conn):
        st.warning("Low Stock: " + ", ".join(get_qty['vegetable'].tolist()))

elif menu == "Add Purchase":
    st.header("Record Purchase")
    with st.form("purchase"):
        veg = st.text_input("Vegetable")
        qty = st.number_input("Kg", 0.0, step=0.5)
        cost = st.number_input("Total Cost ₹", 0.0)
        supplier = st.text_input("Supplier")
        submitted = st.form_submit_button("Save")
        if submitted and qty > 0:
            date = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (date, veg, qty, cost, supplier))
            new_qty = qty + get_qty(veg)
            unit_price = cost / qty
            c.execute("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?)", (veg, new_qty, unit_price, ""))
            conn.commit()
            st.success("Saved!")

elif menu == "Sell":
    st.header("Sell Vegetables")
    customer_name = st.text_input("Customer Name (optional)")
    customer_phone = st.text_input("Phone (for loyalty points)")
    if "cart" not in st.session_state: st.session_state.cart = []

    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    veg = st.selectbox("Select Vegetable", vegs)
    qty = st.number_input("Kg", 0.0, step=0.1)
    price = st.number_input("Price per kg", 0.0)

    if st.button("Add to Cart", on_click=lambda: st.session_state.cart.append([veg, qty, price, qty*price]) if get_qty(veg) >= qty else st.error("Not enough!"))

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item","Kg","₹/kg","Total"])
        st.table(df)
        total = df["Total"].sum()
        st.write(f"**Total: ₹{total:.2f}**")

        col1, col2 = st.columns(2)
        if col1.button("Complete Sale"):
            date = datetime.now().strftime("%Y-%m-%d")
            cust = f"{customer_name} ({customer_phone})" if customer_phone else "Guest"
            for item in st.session_state.cart:
                v, q, p, t = item
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (q, v))
                c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (date, v, q, p, t, cust))
            if customer_phone:
                c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?,?)", (customer_phone, customer_name))
                c.execute("UPDATE customers SET points = points + ? WHERE phone = ?", (int(total//10), customer_phone))
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success(f"Sale Done! ₹{total:.2f}")

        if col2.button("Clear"): st.session_state.cart = []

# Add other menus (Inventory, Waste, Customers, Reports, Download) same as before if you want — or keep this short & fast.

st.caption("Made with love")
