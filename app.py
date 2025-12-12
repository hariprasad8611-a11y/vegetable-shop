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
</style>
""", unsafe_allow_html=True)

st.image("https://source.unsplash.com/random/1200x300/?vegetables,market", use_column_width=True)
st.markdown("<h1>Fresh Basket</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:green;font-size:16px;'>Your Brother's Smart Vegetable Shop</p>", unsafe_allow_html=True)

# ========================== DATABASE ==========================
DB_FILE = "shop.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# Create or migrate tables with expected schema (use rowid for edits)
# Inventory with columns: vegetable, quantity, cost_price, selling_price, image_url
c.execute("CREATE TABLE IF NOT EXISTS inventory (vegetable TEXT PRIMARY KEY, quantity REAL, cost_price REAL, selling_price REAL, image_url TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS purchases (date TEXT, vegetable TEXT, quantity REAL, amount REAL, supplier TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS sales (date TEXT, vegetable TEXT, quantity_sold REAL, sale_price REAL, total REAL, customer TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS waste (date TEXT, vegetable TEXT, quantity REAL, reason TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)")
conn.commit()

# ========================== HELPERS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price) for veg (or 0s)."""
    c.execute("SELECT quantity, cost_price, selling_price FROM inventory WHERE vegetable=?", (veg,))
    row = c.fetchone()
    if row:
        qty = row[0] if row[0] is not None else 0.0
        cost = row[1] if row[1] is not None else 0.0
        sell = row[2] if row[2] is not None else 0.0
        return qty, cost, sell
    return 0.0, 0.0, 0.0

def fetch_table_with_rowid(table):
    """Return DataFrame including rowid for editing/deleting."""
    df = pd.read_sql(f"SELECT rowid, * FROM {table}", conn)
    return df

def safe_round_df(df, cols):
    for ccol in cols:
        if ccol in df.columns:
            try:
                df[ccol] = df[ccol].astype(float).round(2)
            except Exception:
                pass
    return df

# ========================== SIDEBAR MENU ==========================
menu = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Add Purchase", "Set Selling Prices", "Sell", "Inventory", "Purchases", "Sales", "Expenses", "Customers", "Waste", "Reports", "Download"]
)

# -------------------------- DASHBOARD --------------------------
if menu == "Dashboard":
    st.header("📊 Today's Summary")
    sel_date = st.date_input("Choose Date", value=date.today())
    d = sel_date.strftime("%Y-%m-%d")

    sales = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", conn, params=(d,))["total"].iloc[0]
    cost  = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", conn, params=(d,))["total"].iloc[0]
    profit = sales - cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Sales", f"₹{sales:.2f}")
    c2.metric("Cost", f"₹{cost:.2f}")
    c3.metric("Profit", f"₹{profit:.2f}")

    low = pd.read_sql("SELECT vegetable, quantity FROM inventory WHERE quantity>0 AND quantity<5", conn)
    if not low.empty:
        st.warning("⚠ Low Stock Alert")
        try:
            st.bar_chart(low.set_index("vegetable")["quantity"])
        except Exception:
            st.write(low)

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
                st.error("Enter vegetable name")
            elif qty <= 0:
                st.error("Enter quantity > 0")
            else:
                d = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (d, veg, qty, amount, supplier))
                # update inventory
                old_qty, old_cost, old_sell = get_stock(veg)
                new_qty = old_qty + qty
                unit_cost = (amount / qty) if qty>0 else old_cost
                # preserve existing image_url if any
                c.execute("""
                    INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url)
                    VALUES (?, ?, ?, ?, COALESCE((SELECT image_url FROM inventory WHERE vegetable=?), ''))
                    ON CONFLICT(vegetable) DO UPDATE SET
                        quantity=excluded.quantity,
                        cost_price=excluded.cost_price,
                        selling_price=COALESCE((SELECT selling_price FROM inventory WHERE vegetable=?), excluded.selling_price)
                """, (veg, new_qty, unit_cost, old_sell if old_sell else 0.0, veg, veg))
                conn.commit()
                st.success(f"Saved purchase: {qty} kg {veg}")

    st.markdown("---")
    st.subheader("Recent purchases")
    df = fetch_table_with_rowid("purchases")
    if df.empty:
        st.info("No purchases yet")
    else:
        df = safe_round_df(df, ["quantity", "amount"])
        st.dataframe(df)

        # Edit / Delete per row
        st.markdown("Edit / Delete purchases")
        for _, row in df.sort_values("rowid", ascending=False).head(10).iterrows():
            cols = st.columns([2,1,1,1,1,1])
            with cols[0]:
                st.write(f"**{row['vegetable']}** — {row['quantity']} kg — ₹{row['amount']}")
            with cols[4]:
                if st.button("Edit", key=f"edit_pur_{int(row['rowid'])}"):
                    # show form to edit
                    with st.form(f"edit_pur_form_{int(row['rowid'])}"):
                        new_date = st.date_input("Date", value=date.fromisoformat(row['date']))
                        new_veg = st.text_input("Vegetable", value=row['vegetable'])
                        new_qty = st.number_input("Quantity", value=float(row['quantity']))
                        new_amount = st.number_input("Amount", value=float(row['amount']))
                        new_supplier = st.text_input("Supplier", value=row['supplier'])
                        if st.form_submit_button("Save changes"):
                            c.execute("UPDATE purchases SET date=?, vegetable=?, quantity=?, amount=?, supplier=? WHERE rowid=?",
                                      (new_date.strftime("%Y-%m-%d"), new_veg, new_qty, new_amount, new_supplier, int(row['rowid'])))
                            # optionally update inventory (simple approach: adjust delta)
                            delta = new_qty - row['quantity']
                            c.execute("UPDATE inventory SET quantity = quantity + ? WHERE vegetable=?", (delta, new_veg))
                            conn.commit()
                            st.success("Purchase updated")
                            st.experimental_rerun()
            with cols[5]:
                if st.button("Delete", key=f"del_pur_{int(row['rowid'])}"):
                    # reduce inventory accordingly (safe: subtract qty)
                    c.execute("DELETE FROM purchases WHERE rowid=?", (int(row['rowid']),))
                    c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (row['quantity'], row['vegetable']))
                    conn.commit()
                    st.success("Deleted purchase")
                    st.experimental_rerun()

# -------------------------- SET SELLING PRICES --------------------------
elif menu == "Set Selling Prices":
    st.header("🏷 Set Selling Prices")
    items = pd.read_sql("SELECT vegetable FROM inventory", conn)
    if items.empty:
        st.info("No items in inventory")
    else:
        veg = st.selectbox("Choose Vegetable", items['vegetable'])
        qty, cost, sell = get_stock(veg)
        st.info(f"Stock: {qty:.2f} kg | Cost: ₹{cost:.2f}/kg")
        new_price = st.number_input("Selling Price per kg ₹", value=float(sell or 0.0))
        if st.button("Update Price"):
            c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, veg))
            conn.commit()
            st.success("Price updated")

# -------------------------- SELL (MULTI-ITEM) --------------------------
elif menu == "Sell":
    st.header("💵 Sell Vegetables (Multi-item cart)")
    cust_name = st.text_input("Customer Name (optional)")
    cust_phone = st.text_input("Customer Phone (optional)")

    items_df = pd.read_sql("SELECT vegetable, quantity, cost_price, selling_price FROM inventory", conn)
    if items_df.empty:
        st.info("No items in inventory")
    else:
        veg_list = items_df["vegetable"].tolist()
        selected = st.multiselect("Select vegetables to sell (multiple)", veg_list)

        # per-selected input areas
        cart = st.session_state.get("cart", [])
        temp_entries = []
        if selected:
            st.markdown("Enter quantities and optionally adjust per-item price:")
            for veg in selected:
                qty_stock, cost_price, sell_price = get_stock(veg)
                cols = st.columns([3,2,2])
                with cols[0]:
                    st.markdown(f"**{veg}** (Stock: {qty_stock:.2f} kg, Cost/kg: ₹{cost_price:.2f})")
                with cols[1]:
                    q = st.number_input(f"Qty — {veg}", min_value=0.0, step=0.1, key=f"sell_qty_{veg}")
                with cols[2]:
                    p = st.number_input(f"Price/kg — {veg}", min_value=0.0, value=float(sell_price or cost_price or 0.0), key=f"sell_price_{veg}")
                if q and q>0:
                    temp_entries.append([veg, q, p, round(q*p,2)])

            if st.button("Add Selected to Cart"):
                # validate stock and append
                added = 0
                for entry in temp_entries:
                    veg, q, p, total = entry
                    stock, _, _ = get_stock(veg)
                    if q <= 0:
                        st.warning(f"Zero qty skipped for {veg}")
                        continue
                    if q > stock:
                        st.error(f"Not enough stock for {veg} (available {stock})")
                        continue
                    # append to session cart
                    cart.append(entry)
                    added += 1
                st.session_state.cart = cart
                st.rerun()

        # show cart
        if st.session_state.get("cart"):
            st.markdown("### Cart")
            cart_df = pd.DataFrame(st.session_state["cart"], columns=["Item","Kg","Price/kg","Total"])
            st.table(cart_df)
            total_bill = cart_df["Total"].sum()
            st.markdown(f"**Total Bill: ₹{total_bill:.2f}**")

            col1, col2 = st.columns(2)
            if col1.button("Complete Sale"):
                d = datetime.now().strftime("%Y-%m-%d")
                cust = f"{cust_name} ({cust_phone})" if cust_phone else (cust_name or "Guest")
                for v, q, p, t in st.session_state["cart"]:
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
                st.experimental_rerun()
            if col2.button("Clear Cart"):
                st.session_state.cart = []
                st.experimental_rerun()

# -------------------------- INVENTORY (EDITABLE) --------------------------
elif menu == "Inventory":
    st.header("📦 Inventory")
    df = pd.read_sql("SELECT rowid, vegetable, quantity, cost_price, selling_price, image_url FROM inventory", conn)
    if df.empty:
        st.info("No stock available")
    else:
        df_display = df.copy()
        df_display = safe_round_df(df_display, ["quantity", "cost_price", "selling_price"])
        df_display = df_display.rename(columns={"rowid":"rowid","vegetable":"Vegetable","quantity":"Qty (kg)","cost_price":"Cost/kg","selling_price":"Sell/kg","image_url":"Image URL"})
        st.dataframe(df_display.drop(columns=["rowid"]))

        st.markdown("### Edit / Delete Inventory Items")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
            cols = st.columns([3,1,1])
            with cols[0]:
                st.write(f"**{row['vegetable']}** — {round(row['quantity'],2)} kg — Cost ₹{row['cost_price'] or 0:.2f} — Sell ₹{row['selling_price'] or 0:.2f}")
            with cols[1]:
                if st.button("Edit", key=f"edit_inv_{int(row['rowid'])}"):
                    with st.form(f"edit_inv_form_{int(row['rowid'])}"):
                        new_name = st.text_input("Vegetable", value=row['vegetable'])
                        new_qty = st.number_input("Quantity", value=float(row['quantity'] or 0.0))
                        new_cost = st.number_input("Cost Price/kg", value=float(row['cost_price'] or 0.0))
                        new_sell = st.number_input("Selling Price/kg", value=float(row['selling_price'] or 0.0))
                        if st.form_submit_button("Save"):
                            # If vegetable name changed, careful: update primary key by inserting/updating
                            if new_name != row['vegetable']:
                                # remove old and add new to avoid PK conflict
                                c.execute("DELETE FROM inventory WHERE vegetable=?", (row['vegetable'],))
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, image_url) VALUES (?,?,?,?,?)",
                                          (new_name, new_qty, new_cost, new_sell, row['image_url']))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=?, selling_price=? WHERE vegetable=?",
                                          (new_qty, new_cost, new_sell, row['vegetable']))
                            conn.commit()
                            st.success("Inventory updated")
                            st.experimental_rerun()
            with cols[2]:
                if st.button("Delete", key=f"del_inv_{int(row['rowid'])}"):
                    c.execute("DELETE FROM inventory WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted item")
                    st.experimental_rerun()

# -------------------------- PURCHASES (full editable) --------------------------
elif menu == "Purchases":
    st.header("📋 Purchases")
    df = fetch_table_with_rowid("purchases")
    if df.empty:
        st.info("No purchases recorded")
    else:
        df2 = safe_round_df(df.copy(), ["quantity", "amount"])
        st.dataframe(df2.drop(columns=["rowid"]))
        st.markdown("Edit / Delete purchases")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
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
                            # adjust inventory delta: simple approach (not tracking original redo complexities)
                            conn.commit()
                            st.success("Updated purchase")
                            st.experimental_rerun()
                if st.button("Delete", key=f"del_pur2_{int(row['rowid'])}"):
                    c.execute("DELETE FROM purchases WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.experimental_rerun()

# -------------------------- SALES (editable) --------------------------
elif menu == "Sales":
    st.header("🧾 Sales")
    df = fetch_table_with_rowid("sales")
    if df.empty:
        st.info("No sales recorded")
    else:
        df2 = safe_round_df(df.copy(), ["quantity_sold", "sale_price", "total"])
        st.dataframe(df2.drop(columns=["rowid"]))
        st.markdown("Edit / Delete sales")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
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
                            st.experimental_rerun()
                if st.button("Delete", key=f"del_sale_{int(row['rowid'])}"):
                    # optionally increase inventory back
                    c.execute("DELETE FROM sales WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted sale")
                    st.experimental_rerun()

# -------------------------- EXPENSES (editable) --------------------------
elif menu == "Expenses":
    st.header("💸 Expenses")
    df = fetch_table_with_rowid("expenses")
    if df.empty:
        st.info("No expenses yet")
    else:
        st.dataframe(df.drop(columns=["rowid"]))
        st.markdown("Edit / Delete expenses")
        for _, row in df.sort_values("rowid", ascending=False).iterrows():
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
                            st.experimental_rerun()
                if st.button("Delete", key=f"del_exp_{int(row['rowid'])}"):
                    c.execute("DELETE FROM expenses WHERE rowid=?", (int(row['rowid']),))
                    conn.commit()
                    st.success("Deleted")
                    st.experimental_rerun()

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
                            # phone PK: if changed, delete old and insert new
                            if phone != row['phone']:
                                c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                                c.execute("INSERT OR REPLACE INTO customers (phone,name,points) VALUES (?,?,?)", (phone, name, points))
                            else:
                                c.execute("UPDATE customers SET name=?, points=? WHERE phone=?", (name, points, phone))
                            conn.commit()
                            st.success("Customer updated")
                            st.experimental_rerun()
                if st.button("Delete", key=f"del_cust_{row['phone']}"):
                    c.execute("DELETE FROM customers WHERE phone=?", (row['phone'],))
                    conn.commit()
                    st.success("Deleted customer")
                    st.experimental_rerun()

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

# -------------------------- REPORTS --------------------------
elif menu == "Reports":
    st.header("📈 Reports")
    choice = st.selectbox("Report type", ["Daily Sales (by date)", "Inventory Snapshot", "Customer Points"])
    if choice == "Daily Sales (by date)":
        sel = st.date_input("Pick date", value=date.today())
        d = sel.strftime("%Y-%m-%d")
        df = pd.read_sql("SELECT * FROM sales WHERE date=?", conn, params=(d,))
        if df.empty:
            st.info("No sales")
        else:
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False).encode(), f"sales_{d}.csv")
    elif choice == "Inventory Snapshot":
        df = pd.read_sql("SELECT * FROM inventory", conn)
        if df.empty:
            st.info("No inventory")
        else:
            st.dataframe(safe_round_df(df, ["quantity", "cost_price", "selling_price"]))
            st.download_button("Download Inventory CSV", df.to_csv(index=False).encode(), "inventory.csv")
    else:
        df = pd.read_sql("SELECT * FROM customers", conn)
        if df.empty:
            st.info("No customers yet")
        else:
            st.dataframe(df)

# -------------------------- DOWNLOAD --------------------------
elif menu == "Download":
    st.header("⬇ Download Records")
    for t in ["inventory","purchases","sales","waste","customers","expenses"]:
        df = pd.read_sql(f"SELECT * FROM {t}", conn)
        if df.empty:
            st.info(f"No records in {t}")
        else:
            st.download_button(f"Download {t}.csv", df.to_csv(index=False).encode(), f"{t}.csv")

st.caption("Fresh Basket — Enhanced: edit, delete, multi-item sell, and full CRUD support ✅")
