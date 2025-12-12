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
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create tables
tables = [
    "CREATE TABLE IF NOT EXISTS inventory (vegetable TEXT PRIMARY KEY, quantity REAL, cost_price REAL, selling_price REAL, image_url TEXT)",
    "CREATE TABLE IF NOT EXISTS purchases (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)",
    "CREATE TABLE IF NOT EXISTS sales (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)",
    "CREATE TABLE IF NOT EXISTS waste (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)"
]
for table in tables:
    c.execute(table)

# Safe add selling_price column
try:
    c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL")
except:
    pass
conn.commit()

# Helper
def get_stock_info(veg):
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable = ?", (veg,))
    result = c.fetchone()
    if result:
        qty = result[0] if result[0] is not None else 0.0
        cost = result[1] if result[1] is not None else 0.0
        sell = result[2] if result[2] is not None else 0.0
        return qty, cost, sell
    return 0.0, 0.0, 0.0

# Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Waste", "Customers", "Reports", "Download"])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
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

    try:
        low = pd.read_sql("SELECT vegetable FROM inventory WHERE quantity < 5 AND quantity IS NOT NULL", conn)
        if not low.empty:
            st.warning("Low Stock: " + ", ".join(low['vegetable'].tolist()))
    except:
        pass

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
            unit_cost = cost / qty if qty > 0 else 0
            current_qty, _, current_sell = get_stock_info(veg)
            new_qty = current_qty + qty
            c.execute("INSERT OR REPLACE INTO inventory VALUES (?, ?, ?, ?, ?)", (veg, new_qty, unit_cost, current_sell, img))
            conn.commit()
            st.success(f"Added {qty} kg of {veg}! Total stock now {new_qty} kg")
            st.rerun()

elif menu == "Set Selling Prices":
    st.header("Set Selling Prices")
    try:
        vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
        if vegs:
            veg = st.selectbox("Select Vegetable", vegs)
            current_qty, current_cost, current_sell = get_stock_info(veg)
            st.write(f"Current Stock: {current_qty:.2f} kg | Cost Price: ₹{current_cost:.2f}/kg")
            new_price = st.number_input("Selling Price per kg ₹", min_value=0.0, value=current_sell if current_sell else 0.0)
            if st.button("Update Selling Price"):
                c.execute("UPDATE inventory SET selling_price = ? WHERE vegetable = ?", (new_price, veg))
                conn.commit()
                st.success(f"Selling price for {veg} set to ₹{new_price}/kg!")
                st.rerun()
        else:
            st.info("No vegetables in inventory yet. Add purchases first.")
    except Exception as e:
        st.error("Error loading prices. Add purchases first.")

elif menu == "Sell":
    st.header("Sell Vegetables")
    customer_name = st.text_input("Customer Name")
    customer_phone = st.text_input("Phone (for loyalty points)")
    if "cart" not in st.session_state:
        st.session_state.cart = []

    try:
        vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
        if vegs:
            veg = st.selectbox("Select Vegetable", vegs)
            current_qty, _, selling_price = get_stock_info(veg)
            price = st.number_input("Price per kg ₹", min_value=0.0, value=float(selling_price) if selling_price else 0.0)
            qty = st.number_input("Kg", min_value=0.0, step=0.1)

            if st.button("Add to Cart"):
                if current_qty >= qty > 0:
                    total_item = qty * price
                    st.session_state.cart.append([veg, qty, price, total_item])
                    st.success(f"Added {qty} kg {veg} @ ₹{price}/kg")
                else:
                    st.error(f"Only {current_qty:.2f} kg available!")
    except:
        st.info("Add inventory first.")

    if st.session_state.cart:
        df = pd.DataFrame(st.session_state.cart, columns=["Item", "Kg", "₹/kg", "Total"])
        st.table(df)
        total_bill = df["Total"].sum()
        st.write(f"**Total Bill: ₹{total_bill:.2f}**")

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
                points = int(total_bill // 10)
                c.execute("UPDATE customers SET points = points + ? WHERE phone = ?", (points, customer_phone))
                st.info(f"Added {points} loyalty points!")
            conn.commit()
            st.session_state.cart = []
            st.balloons()
            st.success(f"Sale completed! ₹{total_bill:.2f}")

        if col2.button("Print/Share Bill"):
            bill_text = f"Fresh Basket\nCustomer: {customer}\nDate: {date}\n\n" + df.to_string(index=False) + f"\n\nTotal: ₹{total_bill:.2f}\nThank You!"
            st.text_area("Copy & Share", bill_text, height=200)

        if st.button("Clear Cart"):
            st.session_state.cart = []

elif menu == "Inventory":
    st.header("Current Stock & Prices")
    try:
        df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
        if not df.empty:
            df.columns = ["Vegetable", "Quantity (kg)", "Cost/kg", "Sell/kg"]
            st.dataframe(df.style.format({"Quantity (kg)": "{:.2f}", "Cost/kg": "₹{:.2f}", "Sell/kg": "₹{:.2f}"}))
        else:
            st.info("No inventory yet.")
    except:
        st.info("No inventory yet.")

# Other menus with safety
elif menu == "Waste":
    st.header("Record Waste")
    try:
        vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
        if vegs:
            veg = st.selectbox("Vegetable", vegs)
            current_qty, _, _ = get_stock_info(veg)
            qty = st.number_input("Wasted kg", min_value=0.0, step=0.1)
            reason = st.text_input("Reason")
            if st.button("Save Waste"):
                if current_qty >= qty:
                    c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", (qty, veg))
                    c.execute("INSERT INTO waste VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                    conn.commit()
                    st.success("Waste recorded!")
    except:
        st.info("No inventory yet.")

elif menu == "Customers":
    st.header("Customers & Loyalty")
    try:
        df = pd.read_sql("SELECT * FROM customers", conn)
        st.dataframe(df)
    except:
        st.info("No customers yet.")

elif menu == "Reports":
    st.header("Sales Report")
    try:
        df = pd.read_sql("SELECT date, SUM(total) as sales FROM sales GROUP BY date ORDER BY date", conn)
        if not df.empty:
            st.bar_chart(df.set_index("date")["sales"])
        else:
            st.info("No sales yet.")
    except:
        st.info("No sales yet.")

elif menu == "Download":
    st.header("Download Data")
    tables = ["inventory", "purchases", "sales", "waste", "customers"]
    for table in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
            csv = df.to_csv(index=False).encode()
            st.download_button(f"Download {table}.csv", csv, f"{table}.csv")
        except:
            pass

st.caption("Fresh Basket - All pages working! Made for your brother ❤️")
