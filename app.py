import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Vegetable Shop", layout="wide")

# ---------------------------
# CSS STYLING
# ---------------------------
def load_css():
    css = """
    <style>
    body { font-family: sans-serif; }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        padding: 8px 20px;
        border-radius: 5px;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

load_css()

# ---------------------------
# DATA FILE INITIALIZATION
# ---------------------------
DATA_FILE = "data.xlsx"

def initialize_excel():
    if not os.path.exists(DATA_FILE):
        with pd.ExcelWriter(DATA_FILE) as writer:
            pd.DataFrame(columns=["Date", "Item", "Quantity", "Price", "Total"])\
                .to_excel(writer, sheet_name="Sales", index=False)
            pd.DataFrame(columns=["Date", "Item", "Quantity", "Price", "Vendor", "Total"])\
                .to_excel(writer, sheet_name="Purchases", index=False)
            pd.DataFrame(columns=["Date", "Category", "Amount", "Description"])\
                .to_excel(writer, sheet_name="Expenses", index=False)
            pd.DataFrame(columns=["Item", "Stock"])\
                .to_excel(writer, sheet_name="Inventory", index=False)

initialize_excel()

# ---------------------------
# UTILITIES
# ---------------------------
def load_sheet(sheet):
    return pd.read_excel(DATA_FILE, sheet_name=sheet)

def save_sheet(df, sheet):
    with pd.ExcelWriter(DATA_FILE, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)

# ---------------------------
# SIDEBAR MENU
# ---------------------------
menu = st.sidebar.radio(
    "Navigation",
    ["Home", "Sales", "Purchases", "Expenses", "Inventory"]
)

# ---------------------------
# HOME PAGE
# ---------------------------
if menu == "Home":
    st.title("🥕 Vegetable Shop Management System")
    st.write("Use the menu on the left to navigate across the app.")
    st.image("https://cdn.pixabay.com/photo/2016/03/05/19/02/vegetables-1238252_1280.jpg")

# ---------------------------
# SALES PAGE
# ---------------------------
elif menu == "Sales":
    st.title("🧾 Sales Entry")

    df = load_sheet("Sales")

    col1, col2, col3 = st.columns(3)
    date = col1.date_input("Date")
    item = col2.text_input("Item")
    qty = col3.number_input("Quantity", min_value=1)

    price = st.number_input("Price", min_value=0)
    total = qty * price

    if st.button("Add Sale"):
        new_row = pd.DataFrame([[date, item, qty, price, total]], columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_sheet(df, "Sales")
        st.success("Sale recorded!")

    st.subheader("📊 Sales Records")
    st.dataframe(df)

# ---------------------------
# PURCHASES PAGE
# ---------------------------
elif menu == "Purchases":
    st.title("📦 Purchases Entry")

    df = load_sheet("Purchases")

    date = st.date_input("Date")
    item = st.text_input("Item")
    qty = st.number_input("Quantity", min_value=1)
    price = st.number_input("Price", min_value=0)
    vendor = st.text_input("Vendor")

    total = qty * price

    if st.button("Add Purchase"):
        new_row = pd.DataFrame([[date, item, qty, price, vendor, total]], columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_sheet(df, "Purchases")
        st.success("Purchase added!")

    st.subheader("📋 Purchase Records")
    st.dataframe(df)

# ---------------------------
# EXPENSES PAGE
# ---------------------------
elif menu == "Expenses":
    st.title("💰 Expenses")

    df = load_sheet("Expenses")

    date = st.date_input("Date")
    category = st.text_input("Category")
    amount = st.number_input("Amount", min_value=0)
    description = st.text_area("Description")

    if st.button("Add Expense"):
        new_row = pd.DataFrame(
            [[date, category, amount, description]], columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        save_sheet(df, "Expenses")
        st.success("Expense added!")

    st.subheader("📒 Expense Records")
    st.dataframe(df)

# ---------------------------
# INVENTORY PAGE
# ---------------------------
elif menu == "Inventory":
    st.title("📦 Inventory Status")

    df_sales = load_sheet("Sales")
    df_purchases = load_sheet("Purchases")

    inventory = {}

    # Add purchases
    for _, r in df_purchases.iterrows():
        inventory[r["Item"]] = inventory.get(r["Item"], 0) + r["Quantity"]

    # Subtract sales
    for _, r in df_sales.iterrows():
        inventory[r["Item"]] = inventory.get(r["Item"], 0) - r["Quantity"]

    df_inventory = pd.DataFrame(list(inventory.items()), columns=["Item", "Stock"])
    df_inventory["Stock"] = df_inventory["Stock"].astype(int)

    st.subheader("📦 Current Inventory")
    st.dataframe(df_inventory)

    # Save to file
    save_sheet(df_inventory, "Inventory")
