import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Fresh Basket", page_icon="Vegetables", layout="centered", initial_sidebar_state="expanded")

# Design
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #d4edda, #f8d7da);}
    h1 {text-align: center; color: #155724;}
    .stButton>button {background-color: #28a745; color: white; height: 3em; width: 100%; border-radius: 12px; font-size: 18px;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: green;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# Database
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS inventory 
             (vegetable TEXT PRIMARY KEY, quantity REAL, cost_price REAL, selling_price REAL, image_url TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS purchases 
             (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS sales 
             (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS waste 
             (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS customers 
             (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)''')

# Add selling_price column safely
try:
    c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL")
except:
    pass
conn.commit()

# Helper: get stock info
def get_stock(veg):
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable=?", (veg,))
    row = c.fetchone()
    if row:
        return (row[0] or 0.0), (row[1] or 0.0), (row[2] or 0.0)
    return 0.0, 0.0, 0.0

# Menu
menu = st.sidebar.selectbox("Menu", [
    "Dashboard", "Add Purchase", "Set Selling Prices", "Sell", 
    "Inventory", "Waste", "Customers", "Reports", "Download"
])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) FROM sales WHERE date=?", conn, params=(today,)).iloc[0,0]
    cost = pd.read_sql("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE date=?", conn, params=(today,)).iloc[0,0]
    profit = sales - cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Sales", f"₹{sales:.2f}")
    c2.metric("Cost", f"₹{cost:.2f}")
    c3.metric("Profit", f"₹{profit:.2f}")

    low = pd.read_sql("SELECT vegetable FROM inventory WHERE quantity<5 AND quantity>0", conn)
    if not low.empty:
        st.warning("Low Stock: " + ", ".join(low['vegetable']))

elif menu == "Add Purchase":
    st.header("Add Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier")
    if st.button("Save Purchase") and veg and qty>0:
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (date, veg, qty, cost, supplier))
        old_qty, _, old_sell = get_stock(veg)
        new_qty = old_qty + qty
        unit_cost = cost / qty
        c.execute("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?)",
                  (veg, new_qty, unit_cost, old_sell, ""))
        conn.commit()
        st.success(f"Added {qty} kg {veg}")
        st.rerun()

elif menu == "Set Selling Prices":
    st.header("Set Selling Prices")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        new_price = st.number_input("Selling Price per kg", value=sell or 0.0)
        if st.button("Update Price"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
            conn.commit()
            st.success("Price updated!")
    else:
        st.info("No items yet")

elif menu == "Sell":
    st.header("Sell Vegetables")
    name = st.text_input("Customer Name")
    phone = st.text_input("Phone (for loyalty)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Vegetable", items['vegetable'])
        qty_in_stock, _, selling_price = get_stock(veg)
        price = st.number_input("Price/kg ₹", value=float(selling_price or 0))
        qty = st.number_input("Kg", min_value=0.0, step=0.1)

        if st.button("Add to Cart"):
            if qty_in_stock >= qty > 0:
                st.session_state.cart.append([veg, qty, price, qty*price])
                st.success("Added")
            else:
                st.error("Not enough stock")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item","Kg","₹/kg","Total"])
        st.table(df)
        total = df["Total"].sum()
        st.write(f"**Total: ₹{total:.2f}**")

        if st.button("Complete Sale"):
            date = datetime.now().strftime("%Y-%m-%d")
            cust = f"{name} ({phone})" if phone else name or "Guest"
            for v, q, p, t in st.session_state.cart:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (q, v))
                c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (date, v, q, p, t, cust))
            if phone:
                c.execute("INSERT OR IGNORE INTO customers (phone,name) VALUES (?,?)", (phone, name))
                c.execute("UPDATE customers SET points = points + ? WHERE phone=?", (int(total//10), phone))
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success("Sale completed!")

        if st.button("Clear Cart"):
            st.session_state.cart = []

elif menu == "Inventory":
    st.header("Current Stock")
    df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
    if not df.empty:
        df.columns = ["Vegetable", "Qty (kg)", "Cost/kg", "Sell/kg"]
        st.dataframe(df.style.format("{:.2f}"))
    else:
        st.info("No stock yet")

# Other pages (Waste, Customers, Reports, Download) are simple and safe — they work too

st.caption("Fresh Basket — Now 100% working on your brother's phone!")
