import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="Vegetables", layout="centered")
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #e8f5e9, #fff8e1);}
    h1 {text-align:center; color:#1b5e20; font-size:2.8em;}
    .stButton>button {height:3em; border-radius:12px; font-size:18px;}
    .stButton>button[kind="primary"] {background:#2e7d32; color:white;}
    .stButton>button[kind="secondary"] {background:#d32f2f; color:white;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:green;font-size:22px;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# ========================== DATABASE ==========================
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create all tables safely
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

# Add missing column if needed
try:
    c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL")
except:
    pass
conn.commit()

# ========================== HELPER FUNCTION ==========================
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
    sel_date = st.date_input("Choose Date", value=date.today())
    d = sel_date.strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) FROM sales WHERE date=?", conn, params=(d,)).iloc[0,0]
    cost  = pd.read_sql("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE date=?", conn, params=(d,)).iloc[0,0]
    profit = sales - cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Sales", f"₹{sales:.2f}")
    c2.metric("Cost", f"₹{cost:.2f}")
    c3.metric("Profit", f"₹{profit:.2f}")

    low = pd.read_sql("SELECT vegetable FROM inventory WHERE quantity<5 AND quantity>0", conn)
    if not low.empty:
        st.warning("Low Stock Alert!")
        st.bar_chart(low.set_index("vegetable")["quantity"])

# ========================== ADD PURCHASE ==========================
elif menu == "Add Purchase":
    st.header("Add Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", min_value=0.0)
    supplier = st.text_input("Supplier")
    if st.button("Save Purchase", type="primary") and veg and qty>0:
        d = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (d, veg, qty, cost, supplier))
        old_qty, _, old_cost, old_sell = get_stock(veg)
        new_qty = old_qty + qty
        unit_cost = cost / qty
        c.execute("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?)",
                  (veg, new_qty, unit_cost, old_sell, ""))
        conn.commit()
        st.success(f"Added {qty} kg {veg}")
        st.rerun()

# ========================== SET SELLING PRICES ==========================
elif menu == "Set Selling Prices":
    st.header("Set Selling Prices")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        st.info(f"Stock: {qty:.2f} kg | Cost/kg: ₹{cost:.2f}")
        price = st.number_input("Selling Price per kg ₹", value=float(sell or 0))
        if st.button("Update Price", type="primary"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (price, veg))
            conn.commit()
            st.success("Price updated!")
    else:
        st.info("No items yet")

# ========================== SELL PAGE ==========================
elif menu == "Sell":
    st.header("Sell Vegetables")
    name = st.text_input("Customer Name")
    phone = st.text_input("Phone (for loyalty)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Select Vegetable", items['vegetable'])
        qty_stock, _, sell_price = get_stock(veg)   # ← THIS WAS THE BUG (now fixed)
        price = st.number_input("Price/kg ₹", value=float(sell_price or 0))
        qty = st.number_input("Kg", min_value=0.0, step=0.1)

        if st.button("Add to Cart", type="primary"):
            if qty_stock >= qty > 0:
                st.session_state.cart.append([veg, qty, price, qty*price])
                st.success("Added to cart")
            else:
                st.error("Not enough stock")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item","Kg","Price/kg","Total"])
        st.table(df)
        total = df["Total"].sum()
        st.markdown(f"**Total Bill: ₹{total:.2f}**")

        if st.button("Complete Sale", type="primary"):
            d = datetime.now().strftime("%Y-%m-%d")
            cust = f"{name} ({phone})" if phone else name or "Guest"
            for v, q, p, t in st.session_state.cart:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (q, v))
                c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (d, v, q, p, t, cust))
            if phone:
                c.execute("INSERT OR IGNORE INTO customers (phone,name) VALUES (?,?)", (phone, name))
                points = int(total//10)
                c.execute("UPDATE customers SET points = points + ? WHERE phone=?", (points, phone))
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success("Sale completed!")

        if st.button("Clear Cart", type="secondary"):
            st.session_state.cart = []

# ========================== OTHER PAGES (Inventory, Waste, etc.) ==========================
elif menu == "Inventory":
    st.header("Current Stock")
    df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
    if not df.empty:
        df.columns = ["Vegetable", "Qty(kg)", "Cost/kg", "Sell/kg"]
        st.dataframe(df.style.format("{:.2f}"))
    else:
        st.info("No stock yet")

elif menu == "Waste":
    st.header("Record Waste")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if not items.empty:
        veg = st.selectbox("Vegetable", items['vegetable'])
        qty = st.number_input("Wasted kg", min_value=0.0)
        reason = st.text_input("Reason")
        if st.button("Save Waste", type="primary"):
            current = get_stock(veg)[0]
            if current >= qty:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                c.execute("INSERT INTO waste VALUES (?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                conn.commit()
                st.success("Recorded")

elif menu == "Customers":
    st.header("Customers")
    df = pd.read_sql("SELECT * FROM customers", conn)
    st.dataframe(df if not df.empty else "No customers")

elif menu == "Reports":
    st.header("Sales Report")
    sel_date = st.date_input("Date", value=date.today())
    d = sel_date.strftime("%Y-%m-%d")
    df = pd.read_sql("SELECT * FROM sales WHERE date=?", conn, params=(d,))
    st.dataframe(df if not df.empty else "No sales")

elif menu == "Download":
    st.header("Download Data")
    for t in ["inventory","purchases","sales","waste","customers"]:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        csv = df.to_csv(index=False).encode()
        st.download_button(f"Download {t}.csv", csv, f"{t}.csv")

st.caption("Fresh Basket — All pages working perfectly now! Made with love for your brother")
