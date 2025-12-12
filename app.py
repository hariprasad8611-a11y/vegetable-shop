import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

st.set_page_config(page_title="Vegetable Shop", layout="wide")

# ---------------------------
# DB INITIALIZATION
# ---------------------------
conn = sqlite3.connect("shop.db", check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute("""CREATE TABLE IF NOT EXISTS sales(
    date TEXT, item TEXT, qty REAL, price REAL, total REAL
)""")

c.execute("""CREATE TABLE IF NOT EXISTS purchases(
    date TEXT, item TEXT, qty REAL, price REAL, vendor TEXT, total REAL
)""")

c.execute("""CREATE TABLE IF NOT EXISTS expenses(
    date TEXT, category TEXT, amount REAL, description TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS inventory(
    item TEXT PRIMARY KEY, stock REAL
)""")

conn.commit()

# ---------------------------
# CSS
# ---------------------------
st.markdown("""
<style>
.stButton>button {
    background-color:#2ecc71;
    color:white;
    padding:8px 20px;
    border-radius:8px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# MENU
# ---------------------------
menu = st.sidebar.radio(
    "Menu",
    ["Home", "Sales", "Purchases", "Expenses", "Inventory"]
)

# ---------------------------
# HOME
# ---------------------------
if menu == "Home":
    st.title("🥕 Vegetable Shop Management")
    st.write("Welcome! Use the menu to navigate.")
    st.image("https://cdn.pixabay.com/photo/2016/03/05/19/02/vegetables-1238252_1280.jpg")

# ---------------------------
# SALES
# ---------------------------
elif menu == "Sales":
    st.title("🧾 Sales Entry")

    sale_date = st.date_input("Date", date.today())
    item = st.text_input("Item")
    qty = st.number_input("Quantity", min_value=0.0)
    price = st.number_input("Price", min_value=0.0)
    total = qty * price

    if st.button("Add Sale"):
        c.execute("INSERT INTO sales VALUES (?,?,?,?,?)",
                  (str(sale_date), item, qty, price, total))
        c.execute("UPDATE inventory SET stock = COALESCE(stock,0) - ? WHERE item=?",
                  (qty, item))
        conn.commit()
        st.success("Sale added!")

    df = pd.read_sql("SELECT * FROM sales", conn)
    st.subheader("Sales Records")
    st.dataframe(df)

# ---------------------------
# PURCHASES
# ---------------------------
elif menu == "Purchases":
    st.title("📦 Purchases")

    pur_date = st.date_input("Date", date.today())
    item = st.text_input("Item")
    qty = st.number_input("Quantity", min_value=0.0)
    price = st.number_input("Price", min_value=0.0)
    vendor = st.text_input("Vendor")
    total = qty * price

    if st.button("Add Purchase"):
        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?,?)",
                  (str(pur_date), item, qty, price, vendor, total))

        # Add to inventory
        current = c.execute(
            "SELECT stock FROM inventory WHERE item=?", (item,)
        ).fetchone()

        if current:
            new_stock = current[0] + qty
            c.execute("UPDATE inventory SET stock=? WHERE item=?",
                      (new_stock, item))
        else:
            c.execute("INSERT INTO inventory VALUES (?,?)", (item, qty))

        conn.commit()
        st.success("Purchase added!")

    df = pd.read_sql("SELECT * FROM purchases", conn)
    st.subheader("Purchase Records")
    st.dataframe(df)

# ---------------------------
# EXPENSES
# ---------------------------
elif menu == "Expenses":
    st.title("💰 Expenses")

    exp_date = st.date_input("Date", date.today())
    category = st.text_input("Category")
    amount = st.number_input("Amount", min_value=0.0)
    description = st.text_area("Description")

    if st.button("Add Expense"):
        c.execute("INSERT INTO expenses VALUES (?,?,?,?)",
                  (str(exp_date), category, amount, description))
        conn.commit()
        st.success("Expense added!")

    df = pd.read_sql("SELECT * FROM expenses", conn)
    st.subheader("Expense Records")
    st.dataframe(df)

# ---------------------------
# INVENTORY
# ---------------------------
elif menu == "Inventory":
    st.title("📦 Inventory")

    df = pd.read_sql("SELECT * FROM inventory", conn)
    st.dataframe(df)

    st.info("Inventory updates automatically after sales & purchases.")
