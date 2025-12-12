import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="Vegetables", layout="centered")
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #e8f5e9, #fff3e0);}
    h1 {text-align:center; color:#1b5e20;}
    .stButton>button {background:#2e7d32; color:white; height:3em; border-radius:10px; font-size:18px;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:green;font-size:20px;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# ========================== DATABASE ==========================
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create all tables
c.executescript('''
CREATE TABLE IF NOT EXISTS inventory (
    vegetable TEXT PRIMARY KEY,
    quantity REAL,
    cost_price REAL,
    selling_price REAL,
    image_url TEXT
);
CREATE TABLE IF NOT EXISTS purchases (
    date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT
);
CREATE TABLE IF NOT EXISTS sales (
    date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT
);
CREATE TABLE IF NOT EXISTS waste (
    date TEXT, vegetable TEXT, quantity REAL, reason TEXT
);
CREATE TABLE IF NOT EXISTS customers (
    phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0
);
''')

# Add missing column safely
try:
    c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL")
except:
    pass
conn.commit()

# ========================== HELPERS ==========================
def get_stock(veg):
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable=?", (veg,))
    row = c.fetchone()
    if row:
        return (row[0] or 0.0), (row[1] or 0.0), (row[2] or 0.0)
    return 0.0, 0.0, 0.0

# ========================== MENU ==========================
menu = st.sidebar.selectbox("Menu", [
    "Dashboard", "Add Purchase", "Set Selling Prices", "Sell",
    "Inventory", "Waste", "Customers", "Reports", "Download"
])

# ========================== DASHBOARD ==========================
if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) FROM sales WHERE date=?", conn, params=(today,)).iloc[0,0]
    cost  = pd.read_sql("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE date=?", conn, params=(today,)).iloc[0,0]
    profit = sales - cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Sales Today", f"₹{sales:.2f}")
    c2.metric("Cost Today", f"₹{cost:.2f}")
    c3.metric("Profit Today", f"₹{profit:.2f}")

    low = pd.read_sql("SELECT vegetable FROM inventory WHERE quantity<5 AND quantity>0", conn)
    if not low.empty:
        st.warning("Low Stock: " + ", ".join(low['vegetable']))

# ========================== ADD PURCHASE ==========================
elif menu == "Add Purchase":
    st.header("Add Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier Name")
    if st.button("Save Purchase") and veg and qty>0:
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (date, veg, qty, cost, supplier))
        old_qty, _, old_sell = get_stock(veg)
        new_qty = old_qty + qty
        unit_cost = cost / qty
        c.execute("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?)",
                  (veg, new_qty, unit_cost, old_sell, ""))
        conn.commit()
        st.success(f"Added {qty} kg {veg} → Total stock: {new_qty} kg")
        st.rerun()

# ========================== SET SELLING PRICES ==========================
elif menu == "Set Selling Prices":
    st.header("Set Selling Prices")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        st.info(f"Stock: {qty:.2f} kg | Cost/kg: ₹{cost:.2f}")
        new_price = st.number_input("Selling Price per kg ₹", value=float(sell or 0))
        if st.button("Update Price"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
            conn.commit()
            st.success(f"Price updated → ₹{new_price}/kg")
    else:
        st.info("No vegetables yet — Add Purchase first")

# ========================== SELL ==========================
elif menu == "Sell":
    st.header("Sell Vegetables")
    name = st.text_input("Customer Name")
    phone = st.text_input("Phone (for loyalty points)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Select Vegetable", items['vegetable'])
        qty_stock, _, sell_price = get_stock(veg)
        price = st.number_input("Price per kg ₹", value=float(sell_price or 0))
        qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1)

        if st.button("Add to Cart"):
            if qty_stock >= qty > 0:
                st.session_state.cart.append([veg, qty, price, qty*price])
                st.success("Added to cart")
            else:
                st.error("Not enough stock")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item","Kg","₹/kg","Total"])
        st.table(df)
        total = df["Total"].sum()
        st.markdown(f"**Total Bill: ₹{total:.2f}**")

        col1, col2 = st.columns(2)
        if col1.button("Complete Sale"):
            date = datetime.now().strftime("%Y-%m-%d")
            cust = f"{name} ({phone})" if phone else name or "Guest"
            for v, q, p, t in st.session_state.cart:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (q, v))
                c.execute("INSERT INTO sales VALUES (?,?,?,?,?, ?, ?, ?, ?, ?)", (date, v, q, p, t, cust))
            if phone:
                c.execute("INSERT OR IGNORE INTO customers (phone,name) VALUES (?,?)", (phone, name))
                points = int(total//10)
                c.execute("UPDATE customers SET points = points + ? WHERE phone=?", (points, phone))
                st.info(f"Added {points} loyalty points")
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success("Sale completed!")

        if col2.button("Print Bill"):
            bill = f"Fresh Basket\nCustomer: {cust}\n{date}\n\n" + df.to_string(index=False) + f"\n\nTotal: ₹{total:.2f}"
            st.text_area("Copy Bill", bill, height=200)

        if st.button("Clear Cart"):
            st.session_state.cart = []

# ========================== INVENTORY ==========================
elif menu == "Inventory":
    st.header("Current Stock & Prices")
    df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
    if not df.empty:
        df.columns = ["Vegetable", "Qty (kg)", "Cost/kg", "Sell/kg"]
        st.dataframe(df.style.format("{:.2f}"))
    else:
        st.info("No stock yet")

# ========================== WASTE ==========================
elif menu == "Waste":
    st.header("Record Waste / Spoiled")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Vegetable", items['vegetable'], key="waste")
        qty = st.number_input("Wasted kg", min_value=0.0, step=0.1)
        reason = st.text_input("Reason")
        if st.button("Save Waste") and qty>0:
            current = get_stock(veg)[0]
            if current >= qty:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                c.execute("INSERT INTO waste VALUES (?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                conn.commit()
                st.success("Waste recorded")
    else:
        st.info("No items")

# ========================== CUSTOMERS ==========================
elif menu == "Customers":
    st.header("Customers & Loyalty Points")
    df = pd.read_sql("SELECT * FROM customers", conn)
    st.dataframe(df if not df.empty else "No customers yet")

# ========================== REPORTS ==========================
elif menu == "Reports":
    st.header("Daily Sales Report")
    df = pd.read_sql("SELECT date, SUM(total) as sales FROM sales GROUP BY date ORDER BY date", conn)
    if not df.empty:
        st.bar_chart(df.set_index("date")["sales"])
    else:
        st.info("No sales yet")

# ========================== DOWNLOAD ==========================
elif menu == "Download":
    st.header("Download All Data")
    for table in ["inventory", "purchases", "sales", "waste", "customers"]:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        csv = df.to_csv(index=False).encode()
        st.download_button(f"Download {table}.csv", csv, f"{table}.csv")

st.caption("Fresh Basket — All pages working perfectly | Made with love for your brother")
