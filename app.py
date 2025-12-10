import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io
from PIL import Image
from pyzbar.pyzbar import decode  # For barcode scanning

# Page Config for Mobile
st.set_page_config(page_title="Fresh Basket", page_icon="🥬", layout="centered", initial_sidebar_state="expanded")

# Beautiful Theme
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #d4edda, #f8d7da);}
    h1 {text-align: center; color: #155724;}
    .stButton>button {background-color: #28a745; color: white; height: 3em; width: 100%; border-radius: 10px; font-size: 18px;}
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>select {font-size: 18px; height: 3em;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?fresh-vegetables,market", use_column_width=True)
st.markdown("<h1>🌿 Fresh Basket</h1>", unsafe_allow_html=True)

# Database Setup
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create Tables
tables = [
    "inventory(vegetable TEXT PRIMARY KEY, quantity REAL, unit_price REAL, image_url TEXT)",
    "purchases(date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)",
    "sales(date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)",
    "waste(date TEXT, vegetable TEXT, quantity REAL, reason TEXT)",
    "customers(phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)",
    "suppliers(name TEXT PRIMARY KEY, phone TEXT)"
]
for table in tables:
    c.execute(f"CREATE TABLE IF NOT EXISTS {table}")
conn.commit()

# Helpers
def get_qty(veg):
    c.execute("SELECT quantity FROM inventory WHERE vegetable=?", (veg,))
    r = c.fetchone()
    return r[0] if r else 0

def get_img(veg):
    c.execute("SELECT image_url FROM inventory WHERE vegetable=?", (veg,))
    r = c.fetchone()
    return r[0] if r and r[0] else ""

def add_purchase(veg, qty, cost, supplier, img=""):
    date = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (date, veg, qty, cost, supplier))
    new_qty = qty + get_qty(veg)
    unit_price = cost / qty if qty > 0 else 0
    c.execute("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?)", (veg, new_qty, unit_price, img or get_img(veg)))
    conn.commit()

def add_customer(phone, name):
    c.execute("INSERT OR REPLACE INTO customers (phone, name) VALUES (?, ?)", (phone, name))
    conn.commit()

def add_points(phone, points):
    c.execute("UPDATE customers SET points = points + ? WHERE phone = ?", (points, phone))
    conn.commit()

def get_low_stock():
    df = pd.read_sql("SELECT vegetable, quantity FROM inventory WHERE quantity < 5", conn)
    return df

# Sidebar Menu
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Purchase", "Sell Vegetables", "Scan Barcode", "Inventory", "Waste", "Customers", "Suppliers", "Reports", "Download Data"])

if menu == "Dashboard":
    st.header("Today's Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    col1, col2, col3 = st.columns(3)
    sales_today = pd.read_sql(f"SELECT SUM(total) FROM sales WHERE date='{today}'", conn).iloc[0,0] or 0
    cost_today = pd.read_sql(f"SELECT SUM(amount) FROM purchases WHERE date='{today}'", conn).iloc[0,0] or 0
    profit_today = sales_today - cost_today
    col1.metric("Sales", f"₹{sales_today:.2f}")
    col2.metric("Costs", f"₹{cost_today:.2f}")
    col3.metric("Profit", f"₹{profit_today:.2f}", delta="Today")
    low_df = get_low_stock()
    if not low_df.empty:
        st.warning("Low Stock Alert!")
        st.dataframe(low_df)
    st.success("Welcome to Fresh Basket!")

elif menu == "Add Purchase":
    st.header("Record Purchase")
    veg = st.text_input("Vegetable Name")
    qty = st.number_input("Quantity (kg)", 0.0, step=0.5)
    cost = st.number_input("Total Cost ₹", 0.0)
    supplier = st.text_input("Supplier Name")
    img = st.text_input("Image URL (optional)")
    if st.button("Save Purchase"):
        add_purchase(veg, qty, cost, supplier, img)
        st.success("Purchase added!")

elif menu == "Sell Vegetables":
    st.header("Sell to Customer")
    if "cart" not in st.session_state:
        st.session_state.cart = []
    
    customer_name = st.text_input("Customer Name")
    customer_phone = st.text_input("Customer Phone (for loyalty points)")
    
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    veg = st.selectbox("Vegetable", vegs)
    qty = st.number_input("Kg", 0.0, step=0.1)
    price = st.number_input("Price per kg ₹", 0.0)
    
    if st.button("Add to Bill"):
        if get_qty(veg) >= qty:
            st.session_state.cart.append([veg, qty, price, qty*price])
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
            customer = f"{customer_name} ({customer_phone})" if customer_name or customer_phone else "Guest"
            for item in st.session_state.cart:
                v, q, p, t = item
                new_qty = get_qty(v) - q
                c.execute("UPDATE inventory SET quantity=? WHERE vegetable=?", (new_qty, v))
                c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (date, v, q, p, t, customer))
            conn.commit()
            if customer_phone:
                add_customer(customer_phone, customer_name)
                points = int(total / 10)
                add_points(customer_phone, points)
                st.info(f"Added {points} loyalty points!")
            st.session_state.cart = []
            st.balloons()
            st.success(f"Sale completed! ₹{total:.2f}")
        
        if col2.button("Print/Share Bill"):
            bill_text = f"Fresh Basket Bill\nCustomer: {customer}\nDate: {date}\n\n" + df.to_string(index=False) + f"\n\nTotal: ₹{total:.2f}"
            st.text_area("Copy this Bill", bill_text, height=200)
        
        if st.button("Clear Cart"):
            st.session_state.cart = []

elif menu == "Scan Barcode":
    st.header("Barcode Scanner")
    st.info("Take a photo of the vegetable barcode using your phone camera.")
    img_file = st.camera_input("Scan Barcode")
    if img_file:
        img = Image.open(img_file)
        decoded = decode(img)
        if decoded:
            barcode_data = decoded[0].data.decode('utf-8')
            st.success(f"Scanned: {barcode_data}")
            # Simulate adding to cart (map barcode to veg, e.g., assume barcode is veg name)
            veg = barcode_data  # Customize this mapping as needed
            if veg in pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist():
                st.write(f"Found {veg}! Add to sale?")
                qty = st.number_input("Quantity (kg)", 0.0)
                if st.button("Add from Scan"):
                    # Add to cart logic here (similar to sell)
                    st.success("Added from scan!")
            else:
                st.error("Unknown barcode. Add as new veg?")
        else:
            st.error("No barcode found. Try again.")

elif menu == "Inventory":
    st.header("Current Stock")
    df = pd.read_sql("SELECT * FROM inventory", conn)
    for _, row in df.iterrows():
        col1, col2 = st.columns([1,3])
        if row['image_url']:
            col1.image(row['image_url'], width=80)
        col2.write(f"**{row['vegetable']}**: {row['quantity']} kg @ ₹{row['unit_price']:.2f}/kg")
    st.dataframe(df)

elif menu == "Waste":
    st.header("Record Waste")
    vegs = pd.read_sql("SELECT vegetable FROM inventory", conn)['vegetable'].tolist()
    veg = st.selectbox("Vegetable", vegs)
    qty = st.number_input("Quantity Wasted (kg)", 0.0)
    reason = st.text_input("Reason")
    if st.button("Record Waste"):
        if get_qty(veg) >= qty:
            new_qty = get_qty(veg) - qty
            date = datetime.now().strftime("%Y-%m-%d")
            c.execute("UPDATE inventory SET quantity=? WHERE vegetable=?", (new_qty, veg))
            c.execute("INSERT INTO waste VALUES (?,?,?,?)", (date, veg, qty, reason))
            conn.commit()
            st.success("Waste recorded!")
        else:
            st.error("Not enough stock!")

elif menu == "Customers":
    st.header("Customer List")
    df = pd.read_sql("SELECT * FROM customers", conn)
    st.dataframe(df)
    phone = st.text_input("Redeem Points for Phone")
    redeem = st.number_input("Points to Redeem", 0)
    if st.button("Redeem"):
        c.execute("UPDATE customers SET points = points - ? WHERE phone = ?", (redeem, phone))
        conn.commit()
        st.success("Points redeemed!")

elif menu == "Suppliers":
    st.header("Supplier List")
    name = st.text_input("Supplier Name")
    phone = st.text_input("Phone")
    if st.button("Add Supplier"):
        c.execute("INSERT OR REPLACE INTO suppliers VALUES (?, ?)", (name, phone))
        conn.commit()
        st.success("Added!")
    df = pd.read_sql("SELECT * FROM suppliers", conn)
    st.dataframe(df)

elif menu == "Reports":
    st.header("Reports & Graphs")
    sales_df = pd.read_sql("SELECT date, SUM(total) as daily_sales FROM sales GROUP BY date", conn)
    st.bar_chart(sales_df.set_index('date')['daily_sales'], use_container_width=True)
    st.subheader("Full Sales Data")
    st.dataframe(pd.read_sql("SELECT * FROM sales", conn))

elif menu == "Download Data":
    st.header("Download Reports")
    tables = ["inventory", "purchases", "sales", "waste", "customers", "suppliers"]
    for t in tables:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"Download {t}.csv", csv, f"{t}.csv", "text/csv")

conn.close()
