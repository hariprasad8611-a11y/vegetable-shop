import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🥕", layout="centered")
st.markdown("""
<style>
    .main {background: linear-gradient(90deg, #e8f5e9, #fff8e1);}
    h1 {text-align:center; color:#1b5e20; font-size:2.4em;}
    .stButton>button {height:3em; border-radius:12px; font-size:16px;}
    .primary-btn {background:#2e7d32 !important; color:white !important;}
    .secondary-btn {background:#d32f2f !important; color:white !important;}
    .muted {color:#6b7280; font-size:0.9rem;}
    .small {font-size:0.9rem}
    .alert {background:#fff3cd; padding:12px; border-radius:8px; margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:green;font-size:16px;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# ========================== DATABASE ==========================
DB_FILE = "shop.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# create tables (keeps cost_price column but UI won't show/edit it)
c.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    vegetable TEXT PRIMARY KEY,
    quantity REAL,
    cost_price REAL,
    selling_price REAL,
    image_url TEXT
)
""")
c.execute("CREATE TABLE IF NOT EXISTS purchases (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS sales (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS waste (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)")
conn.commit()

# ========================== HELPERS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price) for veg (or zeros)."""
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable=?", (veg,))
    row = c.fetchone()
    if row:
        qty = row[0] or 0.0
        cost = row[1] or 0.0
        sell = row[2] or 0.0
        return qty, cost, sell
    return 0.0, 0.0, 0.0

def fetch_table_with_rowid(table):
    return pd.read_sql(f"SELECT rowid, * FROM {table}", conn)

def safe_round_df(df, cols):
    for col in cols:
        if col in df.columns:
            try:
                df[col] = df[col].astype(float).round(2)
            except Exception:
                pass
    return df

# ensure session state keys
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of [veg, qty, price, total]
if "shortage_threshold" not in st.session_state:
    st.session_state.shortage_threshold = 5.0  # default threshold in kg

# ========================== SIDEBAR MENU ==========================
menu = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Purchases", "Sales", "Expenses", "Customers", "Waste", "Download", "Financials"]
)

# -------------------------- DASHBOARD --------------------------
if menu == "Dashboard":
    st.header("📊 Dashboard — Vegetable Shortage Alerts")
    st.markdown("This dashboard shows simple, human-friendly shortage alerts and suggested reorder quantities. Sales/Cost/Profit moved to **Financials** page.")

    # threshold control
    threshold = st.number_input("Shortage threshold (kg) — items below this are flagged", min_value=0.0, value=float(st.session_state.shortage_threshold), step=1.0)
    st.session_state.shortage_threshold = threshold

    inv = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory", conn)
    if inv.empty:
        st.info("No inventory available yet.")
    else:
        inv = inv.sort_values("quantity")
        low = inv[(inv["quantity"] > 0) & (inv["quantity"] < threshold)]
        zero = inv[inv["quantity"] <= 0]
        if zero.empty and low.empty:
            st.success("All good — no shortages right now 👍")
        else:
            st.markdown("### Shortage Alerts")
            # first show items with zero stock (out of stock)
            if not zero.empty:
                for _, r in zero.iterrows():
                    veg = r["vegetable"]
                    st.markdown(f"<div class='alert'><b>{veg}</b> is <span style='color:#d9534f;'>out of stock</span>. Please reorder immediately. Suggested reorder: <b>10 kg</b>.</div>", unsafe_allow_html=True)
            # then low stock items
            if not low.empty:
                for _, r in low.iterrows():
                    veg = r["vegetable"]
                    qty = r["quantity"]
                    suggested = max(5.0, threshold * 2)  # simple rule: suggest at least 5 or twice threshold
                    st.markdown(f"<div class='alert'><b>{veg}</b> running low — only <b>{qty:.2f} kg</b> left. Suggested reorder: <b>{suggested:.0f} kg</b>.</div>", unsafe_allow_html=True)

        # Helpful summary table
        st.markdown("### Inventory Snapshot")
        inv_display = inv.copy()
        inv_display = safe_round_df(inv_display, ["quantity", "selling_price"])
        inv_display = inv_display.rename(columns={"quantity":"Qty (kg)", "selling_price":"Sell/kg"})
        st.dataframe(inv_display)

# -------------------------- ADD PURCHASE --------------------------
elif menu == "Add Purchase":
    st.header("🛒 Add Purchase")
    with st.form("purchase_form"):
        veg = st.text_input("Vegetable Name")
        qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.5)
        amount = st.number_input("Total Cost ₹", min_value=0.0)
        supplier = st.text_input("Supplier (optional)")
        submitted = st.form_submit_button("Save Purchase")
        if submitted:
            if not veg:
                st.error("Please enter vegetable name.")
            elif qty <= 0:
                st.error("Quantity must be > 0.")
            else:
                d = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (d, veg, qty, amount, supplier))
                # update inventory: keep cost_price in DB but UI won't show
                old_qty, old_cost, old_sell = get_stock(veg)
                new_qty = old_qty + qty
                unit_cost = (amount / qty) if qty>0 else old_cost
                # insert or update inventory (preserve selling_price if present)
                c.execute("SELECT selling_price, image_url FROM inventory WHERE vegetable=?", (veg,))
                prev = c.fetchone()
                prev_sell = prev[0] if prev else None
                prev_img = prev[1] if prev else ""
                if prev:
                    c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", (new_qty, unit_cost, veg))
                else:
                    c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)", (veg, new_qty, unit_cost, prev_sell or 0.0, prev_img or ""))
                conn.commit()
                st.success(f"Added {qty} kg of {veg} to purchases and inventory.")

    st.markdown("---")
    st.subheader("Recent Purchases")
    pur_df = fetch_table_with_rowid("purchases")
    if pur_df.empty:
        st.info("No purchases yet")
    else:
        pur_df = safe_round_df(pur_df, ["quantity", "amount"])
        st.dataframe(pur_df.drop(columns=["rowid"]))

# -------------------------- SET SELLING PRICES --------------------------
elif menu == "Set Selling Prices":
    st.header("🏷 Set Selling Prices")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("No items in inventory")
    else:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        st.info(f"Current Stock: {qty:.2f} kg")
        new_price = st.number_input("Selling Price per kg ₹", value=float(sell or 0.0))
        if st.button("Update Price"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
            conn.commit()
            st.success("Selling price updated")

# -------------------------- SELL (multi via + button) --------------------------
elif menu == "Sell":
    st.header("💵 Sell Vegetables (Add with + button)")

    cust_name = st.text_input("Customer Name (optional)")
    cust_phone = st.text_input("Customer Phone (optional)")

    inventory = pd.read_sql("SELECT vegetable, quantity, selling_price FROM inventory ORDER BY vegetable", conn)
    if inventory.empty:
        st.info("No items in inventory")
    else:
        st.markdown("Click **＋** to add 1 kg of that vegetable to the cart. You can add multiple different vegetables.")
        # Display inventory rows with + buttons
        for _, row in inventory.iterrows():
            veg = row["vegetable"]
            stock = float(row["quantity"] or 0.0)
            sell_price = float(row["selling_price"] or 0.0)
            cols = st.columns([4,1,1])
            with cols[0]:
                st.write(f"**{veg}** — {stock:.2f} kg available — Sell/kg ₹{sell_price:.2f}")
            # plus button column
            with cols[1]:
                if st.button("＋", key=f"plus_{veg}"):
                    # add 1 kg to cart for this veg (or increase if already exists)
                    # check stock
                    current_qty_in_cart = 0.0
                    for i, it in enumerate(st.session_state.cart):
                        if it[0] == veg:
                            current_qty_in_cart = st.session_state.cart[i][1]
                            break
                    if current_qty_in_cart + 1.0 > stock:
                        st.error(f"Not enough stock for {veg} (available {stock:.2f} kg).")
                    else:
                        # either update existing cart row or append
                        found = False
                        for i, it in enumerate(st.session_state.cart):
                            if it[0] == veg:
                                st.session_state.cart[i][1] = round(st.session_state.cart[i][1] + 1.0, 2)
                                st.session_state.cart[i][2] = sell_price
                                st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * sell_price, 2)
                                found = True
                                break
                        if not found:
                            st.session_state.cart.append([veg, 1.0, sell_price, round(1.0 * sell_price, 2)])
                        st.success(f"Added 1 kg {veg} to cart")
            # optional remove 1 kg button
            with cols[2]:
                if st.button("−", key=f"minus_{veg}"):
                    # reduce 1 kg from cart if present
                    for i, it in enumerate(st.session_state.cart):
                        if it[0] == veg:
                            if it[1] <= 1.0:
                                st.session_state.cart.pop(i)
                            else:
                                st.session_state.cart[i][1] = round(st.session_state.cart[i][1] - 1.0, 2)
                                st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * st.session_state.cart[i][2], 2)
                            st.success(f"Removed 1 kg from {veg} in cart")
                            break

        st.markdown("---")
        # show cart
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart, columns=["Item","Kg","Price/kg","Total"])
            st.subheader("Cart")
            st.table(cart_df)
            total_bill = cart_df["Total"].sum()
            st.markdown(f"**Total Bill: ₹{total_bill:.2f}**")

            c1, c2 = st.columns(2)
            if c1.button("Complete Sale"):
                # validate stock again and commit sale
                insufficient = []
                for v, q, p, t in st.session_state.cart:
                    stock, _, _ = get_stock(v)
                    if q > stock:
                        insufficient.append((v, stock, q))
                if insufficient:
                    for v, stock, q in insufficient:
                        st.error(f"Not enough {v}: available {stock:.2f} kg, requested {q:.2f} kg")
                else:
                    d = datetime.now().strftime("%Y-%m-%d")
                    cust = f"{cust_name} ({cust_phone})" if cust_phone else cust_name or "Guest"
                    for v, q, p, t in st.session_state.cart:
                        c.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (d, v, q, p, t, cust))
                        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (q, v))
                    if cust_phone:
                        c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?,?)", (cust_phone, cust_name))
                        points = int(total_bill // 10)
                        c.execute("UPDATE customers SET points = points + ? WHERE phone=?", (points, cust_phone))
                    conn.commit()
                    st.success("Sale completed")
                    st.balloons()
                    st.session_state.cart = []
                    st.rerun()
            if c2.button("Clear Cart"):
                st.session_state.cart = []
                st.success("Cleared cart")

# -------------------------- INVENTORY (editable but no cost/kg editing) --------------------------
elif menu == "Inventory":
    st.header("📦 Inventory (Cost/kg removed from UI)")
    df = pd.read_sql("SELECT rowid, vegetable, quantity, selling_price, image_url FROM inventory", conn)
    if df.empty:
        st.info("No stock available")
    else:
        df_display = df.copy()
        df_display = safe_round_df(df_display, ["quantity", "selling_price"])
        df_display = df_display.rename(columns={"vegetable":"Vegetable","quantity":"Qty (kg)","selling_price":"Sell/kg","image_url":"Image URL"})
        st.dataframe(df_display.drop(columns=["rowid"]))

        st.markdown("### Edit / Delete Inventory Items")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3,1,1])
            with cols[0]:
                st.write(f"**{row['vegetable']}** — {round(row['quantity'],2)} kg — Sell ₹{row['selling_price'] or 0:.2f}")
            with cols[1]:
                if st.button("Edit", key=f"edit_inv_{int(row['rowid'])}"):
                    with st.form(f"edit_inv_form_{int(row['rowid'])}"):
                        new_name = st.text_input("Vegetable", value=row['vegetable'])
                        new_qty = st.number_input("Quantity", value=float(row['quantity'] or 0.0))
                        new_sell = st.number_input("Selling Price/kg", value=float(row['selling_price'] or 0.0))
                        if st.form_submit_button("Save"):
                            # update inventory; we do NOT expose cost_price in UI so we don't edit it here
                            if new_name != row['vegetable']:
                                # delete old record then insert new (to avoid PK conflicts)
                                c.execute("DELETE FROM inventory WHERE vegetable=?", (row['vegetable'],))
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)",
                                          (new_name, new_qty, 0.0, new_sell, row['image_url']))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", (new_qty, new_sell, row['vegetable']))
                            conn.commit()
                            st.success("Inventory updated")
                            st.rerun()
            with cols[2]:
                if st.button("Delete", key=f"del_inv_{int(row['rowid'])}"):
                    c.execute("DELETE FROM inventory WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted item")
                    st.rerun()

# -------------------------- PURCHASES --------------------------
elif menu == "Purchases":
    st.header("📋 Purchases")
    pur_df = fetch_table_with_rowid("purchases")
    if pur_df.empty:
        st.info("No purchases recorded")
    else:
        pur_df2 = safe_round_df(pur_df.copy(), ["quantity", "amount"])
        st.dataframe(pur_df2.drop(columns=["rowid"]))
        st.markdown("Edit / Delete purchases")
        for _, row in pur_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3,1])
            with cols[0]:
                st.write(f"{row['date']} — {row['vegetable']} — {row['quantity']} kg — ₹{row['amount']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_pur2_{int(row['rowid'])}"):
                    with st.form(f"edit_pur2_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        nv = st.text_input("Vegetable", value=row['vegetable'])
                        nq = st.number_input("Qty", value=float(row['quantity']))
                        na = st.number_input("Amount", value=float(row['amount']))
                        ns = st.text_input("Supplier", value=row['supplier'])
                        if st.form_submit_button("Save"):
                            c.execute("UPDATE purchases SET date=?, vegetable=?, quantity=?, amount=?, supplier=? WHERE rowid=?",
                                      (nd.strftime("%Y-%m-%d"), nv, nq, na, ns, int(row['rowid'])))
                            conn.commit()
                            st.success("Updated purchase")
                            st.rerun()
                if st.button("Delete", key=f"del_pur2_{int(row['rowid'])}"):
                    c.execute("DELETE FROM purchases WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.rerun()

# -------------------------- SALES --------------------------
elif menu == "Sales":
    st.header("🧾 Sales")
    sales_df = fetch_table_with_rowid("sales")
    if sales_df.empty:
        st.info("No sales recorded")
    else:
        sales_df2 = safe_round_df(sales_df.copy(), ["quantity_sold", "sale_price", "total"])
        st.dataframe(sales_df2.drop(columns=["rowid"]))
        st.markdown("Edit / Delete sales")
        for _, row in sales_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3,1])
            with cols[0]:
                st.write(f"{row['date']} — {row['vegetable']} — {row['quantity_sold']} kg — ₹{row['total']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_sale_{int(row['rowid'])}"):
                    with st.form(f"edit_sale_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        nv = st.text_input("Vegetable", value=row['vegetable'])
                        nq = st.number_input("Qty", value=float(row['quantity_sold']))
                        np = st.number_input("Price/kg", value=float(row['sale_price']))
                        if st.form_submit_button("Save"):
                            new_total = nq * np
                            c.execute("UPDATE sales SET date=?, vegetable=?, quantity_sold=?, sale_price=?, total=? WHERE rowid=?",
                                      (nd.strftime("%Y-%m-%d"), nv, nq, np, new_total, int(row['rowid'])))
                            conn.commit()
                            st.success("Sale updated")
                            st.rerun()
                if st.button("Delete", key=f"del_sale_{int(row['rowid'])}"):
                    c.execute("DELETE FROM sales WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted sale")
                    st.rerun()

# -------------------------- EXPENSES --------------------------
elif menu == "Expenses":
    st.header("💸 Expenses")
    exp_df = fetch_table_with_rowid("expenses")
    if exp_df.empty:
        st.info("No expenses yet")
    else:
        st.dataframe(exp_df.drop(columns=["rowid"]))
        st.markdown("Edit / Delete expenses")
        for _, row in exp_df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3,1])
            with cols[0]:
                st.write(f"{row['date']} — {row['category']} — ₹{row['amount']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_exp_{int(row['rowid'])}"):
                    with st.form(f"edit_exp_form_{int(row['rowid'])}"):
                        nd = st.date_input("Date", value=date.fromisoformat(row['date']))
                        cat = st.text_input("Category", value=row['category'])
                        amt = st.number_input("Amount", value=float(row['amount']))
                        desc = st.text_input("Description", value=row['description'])
                        if st.form_submit_button("Save"):
                            c.execute("UPDATE expenses SET date=?, category=?, amount=?, description=? WHERE rowid=?",
                                      (nd.strftime("%Y-%m-%d"), cat, amt, desc, int(row['rowid'])))
                            conn.commit()
                            st.success("Updated expense")
                            st.rerun()
                if st.button("Delete", key=f"del_exp_{int(row['rowid'])}"):
                    c.execute("DELETE FROM expenses WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.rerun()

# -------------------------- CUSTOMERS --------------------------
elif menu == "Customers":
    st.header("👥 Customers")
    df = pd.read_sql("SELECT * FROM customers", conn)
    if df.empty:
        st.info("No customers yet")
    else:
        st.dataframe(df)
        st.markdown("Edit / Delete customers")
        for _, row in df.iterrows():
            cols = st.columns([3,1])
            with cols[0]:
                st.write(f"{row['name']} — {row['phone']} — Points: {row['points']}")
            with cols[1]:
                if st.button("Edit", key=f"edit_cust_{row['phone']}"):
                    with st.form(f"edit_cust_form_{row['phone']}"):
                        name = st.text_input("Name", value=row['name'])
                        phone = st.text_input("Phone", value=row['phone'])
                        points = st.number_input("Points", value=int(row['points'] or 0))
                        if st.form_submit_button("Save"):
                            if phone != row['phone']:
                                c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                                c.execute("INSERT OR REPLACE INTO customers (phone,name,points) VALUES (?,?,?)", (phone, name, points))
                            else:
                                c.execute("UPDATE customers SET name=?, points=? WHERE phone=?", (name, points, phone))
                            conn.commit()
                            st.success("Customer updated")
                            st.rerun()
                if st.button("Delete", key=f"del_cust_{row['phone']}"):
                    c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                    conn.commit()
                    st.success("Deleted customer")
                    st.rerun()

# -------------------------- WASTE --------------------------
elif menu == "Waste":
    st.header("🗑 Record Waste")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("No inventory")
    else:
        veg = st.selectbox("Vegetable", items['vegetable'])
        qty = st.number_input("Wasted kg", min_value=0.0, step=0.1)
        reason = st.text_input("Reason")
        if st.button("Save Waste"):
            current = get_stock(veg)[0]
            if qty <= 0:
                st.error("Enter a positive quantity")
            elif current < qty:
                st.error("Not enough stock")
            else:
                c.execute("INSERT INTO waste VALUES (?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), veg, qty, reason))
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                conn.commit()
                st.success("Waste recorded")
    df = fetch_table_with_rowid("waste")
    if df.empty:
        st.info("No waste recorded")
    else:
        st.dataframe(df.drop(columns=["rowid"]))

# -------------------------- DOWNLOAD --------------------------
elif menu == "Download":
    st.header("⬇ Download Records")
    for t in ["inventory","purchases","sales","waste","customers","expenses"]:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        if df.empty:
            st.info(f"No records in {t}")
        else:
            st.download_button(f"Download {t}.csv", df.to_csv(index=False).encode(), f"{t}.csv")

# -------------------------- FINANCIALS (moved from dashboard) --------------------------
elif menu == "Financials":
    st.header("💼 Financials — Sales, Cost & Profit")
    sel_date = st.date_input("Choose Date", value=date.today())
    d = sel_date.strftime("%Y-%m-%d")
    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", conn, params=(d,))["total"].iloc[0]
    cost  = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", conn, params=(d,))["total"].iloc[0]
    profit = sales - cost

    st.metric("Sales", f"₹{sales:.2f}")
    st.metric("Cost", f"₹{cost:.2f}")
    st.metric("Profit", f"₹{profit:.2f}")

    st.markdown("### Sales Records for selected date")
    df = pd.read_sql("SELECT * FROM sales WHERE date=?", conn, params=(d,))
    if df.empty:
        st.info("No sales")
    else:
        st.dataframe(df)
        st.download_button("Download sales CSV", df.to_csv(index=False).encode(), f"sales_{d}.csv")

st.caption("Fresh Basket — Updated: +button cart, no cost/kg in inventory, financials moved to last page ✅")
