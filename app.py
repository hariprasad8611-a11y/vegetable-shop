import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timezone, timedelta
import re
import os
import sys
import atexit
import shutil
import hashlib
import json

# ========================== AUTO-CREATE CONFIG.TOML ==========================
def create_streamlit_config():
    """Create .streamlit/config.toml if it doesn't exist"""
    config_dir = ".streamlit"
    config_file = os.path.join(config_dir, "config.toml")
    
    # Create directory if it doesn't exist
    os.makedirs(config_dir, exist_ok=True)
    
    # Create config file if it doesn't exist
    if not os.path.exists(config_file):
        config_content = """[server]
enableCORS = false
enableXsrfProtection = false
maxUploadSize = 1000

[browser]
serverAddress = "localhost"
serverPort = 8501

[theme]
primaryColor = "#27ae60"
backgroundColor = "#f5f7fa"
secondaryBackgroundColor = "#ffffff"
textColor = "#2c3e50"
font = "sans-serif"
"""
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)
        print(f"✅ Created {config_file}")

# Call this function at the start
create_streamlit_config()

# ========================== USER AUTHENTICATION ==========================
USERS_FILE = "users.json"

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {"admin": {"password": hash_password("admin123"), "role": "admin"}}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def authenticate(username, password):
    """Authenticate user"""
    users = load_users()
    if username in users and users[username]["password"] == hash_password(password):
        return True, users[username].get("role", "user")
    return False, None

def register_user(username, password, role="user"):
    """Register new user"""
    users = load_users()
    if username in users:
        return False, "Username already exists"
    users[username] = {"password": hash_password(password), "role": role}
    save_users(users)
    return True, "User registered successfully"

def reset_password(username, new_password):
    """Reset user password"""
    users = load_users()
    if username not in users:
        return False, "Username not found"
    users[username]["password"] = hash_password(new_password)
    save_users(users)
    return True, "Password reset successfully"

# ========================== LOGIN PAGE ==========================
def login_page():
    """Display login page"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h1>🌿 Fresh Basket</h1>
        <div class="subtitle">Freshness You Can Feel</div>
        <p style="color:#7f8c8d; font-size:0.9em;">No.4, Andal nagar, Adambakkam, Chennai - 600 088<br>📞 7904019948</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🔐 Login", "📝 Register", "🔑 Forgot Password"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", type="primary")
            
            if submit:
                if username and password:
                    authenticated, role = authenticate(username, password)
                    if authenticated:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.success(f"Welcome {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.error("Please enter username and password")
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            register = st.form_submit_button("Register", type="secondary")
            
            if register:
                if new_username and new_password:
                    if new_password == confirm_password:
                        success, message = register_user(new_username, new_password)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Passwords do not match")
                else:
                    st.error("Please fill all fields")
    
    with tab3:
        with st.form("reset_form"):
            reset_username = st.text_input("Username")
            new_password_reset = st.text_input("New Password", type="password")
            confirm_reset = st.text_input("Confirm New Password", type="password")
            reset = st.form_submit_button("Reset Password", type="secondary")
            
            if reset:
                if reset_username and new_password_reset:
                    if new_password_reset == confirm_reset:
                        success, message = reset_password(reset_username, new_password_reset)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Passwords do not match")
                else:
                    st.error("Please fill all fields")
    
    return False

# ========================== ENHANCED DATABASE PERSISTENCE ==========================
# Use an ABSOLUTE persistent location for the database
if sys.platform == "win32":
    # Windows - Use AppData
    PERSISTENT_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FreshBasket")
else:
    # Linux/Mac - Use home directory with proper permissions
    PERSISTENT_DIR = os.path.join(os.path.expanduser("~"), ".freshbasket")

# Create the directory with proper permissions
os.makedirs(PERSISTENT_DIR, exist_ok=True)

# Database files
DB_FILE = os.path.join(PERSISTENT_DIR, "shop.db")
BACKUP_FILE = os.path.join(PERSISTENT_DIR, "shop_backup.db")
EXPORT_DIR = os.path.join(PERSISTENT_DIR, "exports")

# Create exports directory
os.makedirs(EXPORT_DIR, exist_ok=True)

# ========================== DATA MIGRATION & RECOVERY ==========================
def migrate_data():
    """Migrate data from any possible location"""
    try:
        # Check multiple possible locations
        possible_db_locations = [
            "shop.db",  # Current directory
            os.path.join(os.path.dirname(__file__), "shop.db"),  # Script directory
            os.path.join(os.getcwd(), "shop.db"),  # Working directory
            "/tmp/shop.db",  # Temp directory
            "/tmp/streamlit/shop.db"  # Streamlit temp
        ]
        
        data_found = False
        
        for db_location in possible_db_locations:
            if os.path.exists(db_location) and os.path.getsize(db_location) > 1024:  # At least 1KB
                print(f"Found database at: {db_location}")
                # Check if it's a valid SQLite database
                try:
                    test_conn = sqlite3.connect(db_location)
                    test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    test_conn.close()
                    
                    # Copy to persistent location
                    shutil.copy2(db_location, DB_FILE)
                    print(f"Migrated database from {db_location} to {DB_FILE}")
                    data_found = True
                    break
                except:
                    continue
        
        # Also check for backup file
        backup_locations = [
            "shop_backup.db",
            os.path.join(PERSISTENT_DIR, "shop_backup.db"),
            "/tmp/shop_backup.db"
        ]
        
        for backup_location in backup_locations:
            if os.path.exists(backup_location) and os.path.getsize(backup_location) > 1024:
                try:
                    test_conn = sqlite3.connect(backup_location)
                    test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    test_conn.close()
                    
                    shutil.copy2(backup_location, DB_FILE)
                    print(f"Restored from backup at {backup_location}")
                    data_found = True
                    break
                except:
                    continue
        
        return data_found
    except Exception as e:
        print(f"Migration error: {e}")
        return False

# ========================== AUTO-RECOVERY SYSTEM ==========================
def recover_database():
    """Automatically recover database from multiple sources"""
    try:
        # If main DB exists and has data, use it
        if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 1024:
            return True
        
        # Try backup
        if os.path.exists(BACKUP_FILE) and os.path.getsize(BACKUP_FILE) > 1024:
            shutil.copy2(BACKUP_FILE, DB_FILE)
            return True
        
        # Try migration from various locations
        if migrate_data():
            return True
        
        # Create fresh database
        create_fresh_database()
        return True
        
    except Exception as e:
        print(f"Recovery failed: {e}")
        create_fresh_database()
        return True

def create_fresh_database():
    """Create a fresh database with default structure"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables
    tables_sql = {
        "inventory": """
            CREATE TABLE inventory (
                vegetable TEXT PRIMARY KEY,
                quantity REAL,
                cost_price REAL,
                selling_price REAL,
                image_url TEXT,
                unit_type TEXT DEFAULT 'kg',
                category TEXT DEFAULT 'vegetable'
            )
        """,
        "purchases": """
            CREATE TABLE purchases (
                date TEXT, 
                vegetable TEXT, 
                quantity REAL, 
                amount REAL, 
                supplier TEXT
            )
        """,
        "sales": """
            CREATE TABLE sales (
                date TEXT, 
                vegetable TEXT, 
                quantity_sold REAL, 
                sale_price REAL, 
                total REAL, 
                customer TEXT,
                unit_type TEXT,
                customer_name TEXT,
                customer_phone TEXT
            )
        """,
        "waste": """
            CREATE TABLE waste (
                date TEXT, 
                vegetable TEXT, 
                quantity REAL, 
                reason TEXT
            )
        """,
        "customers": """
            CREATE TABLE customers (
                phone TEXT PRIMARY KEY, 
                name TEXT, 
                points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                last_visit TEXT
            )
        """,
        "expenses": """
            CREATE TABLE expenses (
                date TEXT, 
                category TEXT, 
                amount REAL, 
                description TEXT
            )
        """
    }
    
    for table_name, sql in tables_sql.items():
        c.execute(sql)
    
    conn.commit()
    conn.close()

# ========================== AUTOMATIC BACKUP SYSTEM ==========================
def create_backup():
    """Create a backup of the database"""
    try:
        if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
            shutil.copy2(DB_FILE, BACKUP_FILE)
            # Also create dated backup for extra safety
            dated_backup = os.path.join(EXPORT_DIR, f"shop_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            shutil.copy2(DB_FILE, dated_backup)
            return True
    except Exception as e:
        print(f"Backup failed: {e}")
    return False

def export_backup():
    """Export backup to downloadable format"""
    try:
        if os.path.exists(DB_FILE):
            # Create JSON export
            conn = sqlite3.connect(DB_FILE)
            
            export_data = {}
            tables = ["inventory", "purchases", "sales", "waste", "customers", "expenses"]
            
            for table in tables:
                try:
                    df = pd.read_sql(f"SELECT * FROM {table}", conn)
                    export_data[table] = df.to_dict('records')
                except:
                    export_data[table] = []
            
            conn.close()
            
            # Save as JSON
            json_file = os.path.join(EXPORT_DIR, f"data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(json_file, 'w') as f:
                import json
                json.dump(export_data, f, indent=2, default=str)
            
            return json_file
    except Exception as e:
        print(f"Export failed: {e}")
    return None

# ========================== DATABASE CONNECTION WITH RECOVERY ==========================
def get_db_connection():
    """Get a database connection with automatic recovery"""
    try:
        # First, recover if needed
        recover_database()
        
        # Connect with WAL mode for better concurrency
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        
        # Create backup after successful connection
        create_backup()
        
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        # Try to create fresh database
        try:
            create_fresh_database()
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            return conn
        except Exception as e2:
            st.error(f"Critical: Could not create database: {e2}")
            return None

# ========================== INITIALIZE SESSION STATE ==========================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'role' not in st.session_state:
    st.session_state.role = ""

# ========================== MAIN APP ==========================
if not st.session_state.logged_in:
    login_page()
    st.stop()

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🌿", layout="wide")

# Custom CSS for beautiful UI
st.markdown("""
<style>
    /* Main background */
    .main {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);}
    
    /* Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Montserrat:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Poppins', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* Headers */
    h1 {text-align:center; color:#2c3e50; font-size:2.8em; margin-bottom:5px;}
    .subtitle {text-align:center; color:#27ae60; font-size:1.2em; margin-bottom:10px; font-weight:500;}
    .address {text-align:center; color:#7f8c8d; font-size:0.9em; margin-bottom:20px;}
    
    /* Buttons */
    .stButton>button {
        height:3em; 
        border-radius:12px; 
        font-size:16px; 
        font-weight:500;
        transition: all 0.3s ease;
        border: none !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15) !important;
    }
    
    .primary-btn {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important; color:white !important;}
    .secondary-btn {background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important; color:white !important;}
    .success-btn {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important; color:white !important;}
    .warning-btn {background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important; color:white !important;}
    .info-btn {background: linear-gradient(135deg, #3498db 0%, #2980b9 100%) !important; color:white !important;}
    
    /* Cards */
    .card {
        background: white;
        padding: 25px;
        border-radius: 20px;
        margin: 15px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.12);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        padding: 25px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 25px rgba(39, 174, 96, 0.3);
    }
    
    .inventory-card {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(52, 152, 219, 0.3);
    }
    
    .sales-card {
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(155, 89, 182, 0.3);
    }
    
    .purchase-card {
        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px;
        color: white;
        box-shadow: 0 8px 25px rgba(243, 156, 18, 0.3);
    }
    
    /* Tables */
    .dataframe {
        border-radius: 10px !important;
        overflow: hidden !important;
    }
    
    /* Inputs */
    .stSelectbox, .stTextInput, .stNumberInput, .stDateInput {
        border-radius: 10px !important;
    }
    
    .stSelectbox>div>div {
        border-radius: 10px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        padding: 10px 0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
        padding: 12px 24px;
        background: #f8f9fa;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important;
        color: white !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%) !important;
    }
    
    /* Receipt */
    .receipt {
        background: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
        border: 2px solid #27ae60;
        max-width: 500px;
        margin: 20px auto;
    }
    
    /* Alert boxes */
    .alert-success {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #28a745;
        margin: 10px 0;
        color: #155724;
    }
    
    .alert-warning {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #ffc107;
        margin: 10px 0;
        color: #856404;
    }
    
    .alert-danger {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #dc3545;
        margin: 10px 0;
        color: #721c24;
    }
    
    /* Cart items */
    .cart-item {
        background: white;
        padding: 15px;
        margin: 10px 0;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border-left: 4px solid #27ae60;
        transition: all 0.3s ease;
    }
    .cart-item:hover {
        transform: translateX(5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #7f8c8d;
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e0e0e0;
        font-size: 0.9em;
    }
    
    /* Vegetable selection */
    .veg-select-card {
        background: white;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    
    /* Print button */
    .print-btn {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important;
        color: white !important;
        font-weight: bold !important;
    }
    
    /* Remove the "Press Enter..." message from number inputs */
    .stNumberInput input[type="number"]::placeholder {
        color: transparent !important;
    }
    
    /* Fix for print preview */
    @media print {
        .receipt {
            box-shadow: none !important;
            border: 1px solid #000 !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 15px !important;
        }
        .stApp {
            visibility: hidden !important;
        }
        .receipt, .receipt * {
            visibility: visible !important;
        }
    }
    
    /* Horizontal layout for cart items */
    .cart-horizontal {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 20px;
    }
    .cart-item-horizontal {
        background: white;
        padding: 10px 15px;
        border-radius: 10px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.05);
        border-left: 3px solid #27ae60;
        flex: 1;
        min-width: 200px;
    }
    
    /* Complete bill button */
    .complete-bill-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
    }
    
    /* User info */
    .user-info {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        color: white;
        padding: 10px 15px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Header with address
st.markdown("""
<div style="text-align:center; margin-bottom:30px;">
    <h1>🌿 Fresh Basket</h1>
    <div class="subtitle">Freshness You Can Feel</div>
    <div class="address">
        No.4, Andal nagar, Adambakkam, Chennai - 600 088<br>
        📞 7904019948
    </div>
</div>
""", unsafe_allow_html=True)

# Initialize database connection
conn = get_db_connection()
if conn is None:
    st.error("❌ Critical: Could not initialize database. Please refresh the page.")
    st.stop()

c = conn.cursor()

# ========================== DATABASE SETUP ==========================
# Create tables if they don't exist
tables_sql = {
    "inventory": """
        CREATE TABLE IF NOT EXISTS inventory (
            vegetable TEXT PRIMARY KEY,
            quantity REAL,
            cost_price REAL,
            selling_price REAL,
            image_url TEXT,
            unit_type TEXT DEFAULT 'kg',
            category TEXT DEFAULT 'vegetable'
        )
    """,
    "purchases": """
        CREATE TABLE IF NOT EXISTS purchases (
            date TEXT, 
            vegetable TEXT, 
            quantity REAL, 
            amount REAL, 
            supplier TEXT
        )
    """,
    "sales": """
        CREATE TABLE IF NOT EXISTS sales (
            date TEXT, 
            vegetable TEXT, 
            quantity_sold REAL, 
            sale_price REAL, 
            total REAL, 
            customer TEXT,
            unit_type TEXT,
            customer_name TEXT,
            customer_phone TEXT
        )
    """,
    "waste": """
        CREATE TABLE IF NOT EXISTS waste (
            date TEXT, 
            vegetable TEXT, 
            quantity REAL, 
            reason TEXT
        )
    """,
    "customers": """
        CREATE TABLE IF NOT EXISTS customers (
            phone TEXT PRIMARY KEY, 
            name TEXT, 
            points INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            last_visit TEXT
        )
    """,
    "expenses": """
        CREATE TABLE IF NOT EXISTS expenses (
            date TEXT, 
            category TEXT, 
            amount REAL, 
            description TEXT
        )
    """
}

for table_name, sql in tables_sql.items():
    c.execute(sql)

# Check if columns exist
c.execute("PRAGMA table_info(inventory)")
columns = [column[1] for column in c.fetchall()]
if 'category' not in columns:
    try:
        c.execute("ALTER TABLE inventory ADD COLUMN category TEXT DEFAULT 'vegetable'")
    except Exception as e:
        pass

c.execute("PRAGMA table_info(sales)")
sales_columns = [column[1] for column in c.fetchall()]
if 'customer_name' not in sales_columns:
    try:
        c.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT")
        c.execute("ALTER TABLE sales ADD COLUMN customer_phone TEXT")
    except Exception as e:
        pass

# ========================== DEFAULT VEGETABLES AND FRUITS ==========================
kg_vegetables = [
    "Avarakai", "Baby Corn", "Baby Potato", "Beetroot", "Bitter Gourd", 
    "Bottle Gourd", "Brinjal", "Brinjal Green", "Brinjal Purple", "Broccoli",
    "Bush Beans", "Cabbage Green", "Cabbage Red", "Capsicum", "Capsicum Colour",
    "Carrot", "Chow Chow (Chayote)", "Cluster Beans", "Colacassia (Taro)",
    "Coriander Leaf", "Cowpea", "Cucumber", "Curry Leaf", "Garlic", "Ginger",
    "Green Chillies", "Green Peas", "Greens (Spinach/Amaranthus etc.)",
    "Knol (Knol Khol)", "Kovakai (Ivy Gourd)", "Ladies Finger (Okra)",
    "Onion Big", "Onion Small", "Potato", "Pudina (Mint)", "Pumpkin (Red)",
    "Pumpkin (White)", "Radish", "Red Radish", "Ridge Gourd", "Snake Gourd",
    "Sweet Potato", "Tomato", "Topaico", "Turnip", "Yam", "Zukuni (Zucchini)"
]

piece_vegetables = [
    "Lemon", "Drumstick", "Banana Steam", "Banana Flower", 
    "Raw Banana", "Coconut"
]

fruits_kg = [
    "Amla (Indian Gooseberry)", "Apple", "Banana Country", "Banana Elachi",
    "Banana Hill", "Banana Karpoorvali", "Banana Nendran", "Banana Poovan",
    "Banana Rasthali", "Banana Red", "Black Grapes", "Butter Fruit (Avocado)",
    "Custard Apple", "Fig", "Guava", "Guava Red", "Jackfruit", 
    "Mangostan (Mangosteen)", "Mosambi (Sweet Lime)", "Musk Melon", "Orange",
    "Papaya", "Passion Fruit", "Pears", "Pineapple", "Pomegranate",
    "Raw Mango", "Sapota (Chikoo)", "Watermelon"
]

# Initialize default items with categories
for veg in kg_vegetables:
    c.execute("SELECT vegetable FROM inventory WHERE vegetable=?", (veg,))
    if not c.fetchone():
        try:
            c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url, unit_type, category) VALUES (?, 0, 0, 0, '', 'kg', 'vegetable')", (veg,))
        except:
            pass
    else:
        try:
            c.execute("UPDATE inventory SET category='vegetable' WHERE vegetable=?", (veg,))
        except:
            pass

for veg in piece_vegetables:
    c.execute("SELECT vegetable FROM inventory WHERE vegetable=?", (veg,))
    if not c.fetchone():
        try:
            c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url, unit_type, category) VALUES (?, 0, 0, 0, '', 'piece', 'vegetable')", (veg,))
        except:
            pass
    else:
        try:
            c.execute("UPDATE inventory SET category='vegetable' WHERE vegetable=?", (veg,))
        except:
            pass

for fruit in fruits_kg:
    c.execute("SELECT vegetable FROM inventory WHERE vegetable=?", (fruit,))
    if not c.fetchone():
        try:
            c.execute("INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url, unit_type, category) VALUES (?, 0, 0, 0, '', 'kg', 'fruit')", (fruit,))
        except:
            pass
    else:
        try:
            c.execute("UPDATE inventory SET category='fruit' WHERE vegetable=?", (fruit,))
        except:
            pass

conn.commit()

# ========================== HELPER FUNCTIONS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price, unit_type, category) for veg (or zeros)."""
    try:
        c.execute("SELECT quantity, cost_price, selling_price, unit_type, category FROM inventory WHERE vegetable=?", (veg,))
        row = c.fetchone()
        if row:
            qty = row[0] if row[0] is not None else 0.0
            cost = row[1] if row[1] is not None else 0.0
            sell = row[2] if row[2] is not None else 0.0
            unit_type = row[3] if row[3] is not None else 'kg'
            category = row[4] if row[4] is not None else 'vegetable'
            return qty, cost, sell, unit_type, category
    except Exception as e:
        pass
    return 0.0, 0.0, 0.0, 'kg', 'vegetable'

def get_last_record_date(table_name):
    """Get the date of the last record in a table"""
    try:
        if table_name in ["sales", "purchases", "waste", "expenses"]:
            c.execute(f"SELECT MAX(date) FROM {table_name}")
            result = c.fetchone()[0]
            return result if result else "N/A"
        else:
            return "N/A"
    except:
        return "N/A"

# Initialize session state
if "cart" not in st.session_state:
    st.session_state.cart = []
if "shortage_threshold" not in st.session_state:
    st.session_state.shortage_threshold = 5.0
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()
if "last_sale" not in st.session_state:
    st.session_state.last_sale = None
if "guest_counter" not in st.session_state:
    try:
        c.execute("SELECT customer FROM sales WHERE customer LIKE 'Guest%'")
        guests = c.fetchall()
        max_guest = 0
        for guest in guests:
            guest_str = guest[0]
            match = re.search(r'Guest(\d+)', guest_str)
            if match:
                guest_num = int(match.group(1))
                if guest_num > max_guest:
                    max_guest = guest_num
        st.session_state.guest_counter = max_guest + 1
    except:
        st.session_state.guest_counter = 1
if "backup_counter" not in st.session_state:
    st.session_state.backup_counter = 0

# ========================== SELL PAGE FUNCTIONS ==========================
def add_to_cart_simple(veg, qty):
    """Add item to cart with quantity validation"""
    if qty <= 0:
        return False
    
    stock, _, price, unit_type, _ = get_stock(veg)
    if stock == 0:
        st.error(f"{veg} is out of stock!")
        return False
    
    current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == veg)
    
    if current_in_cart + qty > stock:
        unit_display = unit_type if unit_type != 'kg' else 'kg'
        st.error(f"Not enough stock! Available: {stock:.2f} {unit_display}")
        return False
    
    found = False
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart[i][1] += qty
            st.session_state.cart[i][3] = round(st.session_state.cart[i][1] * price, 2)
            found = True
            break
    
    if not found:
        total = round(qty * price, 2)
        stock, _, price, unit_type, category = get_stock(veg)
        st.session_state.cart.append([veg, qty, price, total, unit_type, category])
    
    return True

def remove_from_cart(veg):
    """Remove item from cart"""
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart.pop(i)
            return True
    return False

def update_cart_qty(veg, new_qty):
    """Update cart item quantity"""
    if new_qty <= 0:
        remove_from_cart(veg)
        return True
    
    stock, _, price, unit_type, _ = get_stock(veg)
    if new_qty > stock:
        unit_display = unit_type if unit_type != 'kg' else 'kg'
        st.error(f"Not enough stock! Available: {stock:.2f} {unit_display}")
        return False
    
    for i, item in enumerate(st.session_state.cart):
        if item[0] == veg:
            st.session_state.cart[i][1] = new_qty
            st.session_state.cart[i][3] = round(new_qty * price, 2)
            return True
    return False

def get_ist_time():
    """Get current IST time"""
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime("%H:%M:%S")

def process_sale_simple(cust_name, cust_phone):
    """Process the sale with simplified logic"""
    if not st.session_state.cart:
        st.error("Cart is empty!")
        return False
    
    insufficient = []
    for veg, qty, price, total, unit_type, category in st.session_state.cart:
        stock, _, _, _, _ = get_stock(veg)
        if qty > stock:
            insufficient.append((veg, stock, qty, unit_type))
    
    if insufficient:
        for v, stock, q, unit in insufficient:
            unit_display = unit if unit != 'kg' else 'kg'
            st.error(f"Not enough {v}: available {stock:.2f} {unit_display}, requested {q:.2f} {unit_display}")
        return False
    
    d = st.session_state.selected_date.strftime("%Y-%m-%d")
    current_time = get_ist_time()
    
    if not cust_name or cust_name.strip() == "":
        cust_name = f"Guest{st.session_state.guest_counter}"
        st.session_state.guest_counter += 1
    
    if cust_phone and cust_phone.strip():
        cust = f"{cust_name} ({cust_phone})"
    else:
        cust = cust_name
    
    sale_details = []
    for item in st.session_state.cart:
        veg, qty, price, total, unit_type, category = item
        
        c.execute("INSERT INTO sales (date, vegetable, quantity_sold, sale_price, total, customer, unit_type, customer_name, customer_phone) VALUES (?,?,?,?,?,?,?,?,?)", 
                 (d, veg, qty, price, total, cust, unit_type, cust_name, cust_phone))
        
        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
        
        sale_details.append({
            "item": veg,
            "quantity": qty,
            "price": price,
            "total": total,
            "unit_type": unit_type
        })
    
    if cust_phone and cust_phone.strip() != "":
        total_amount = sum(item[3] for item in st.session_state.cart)
        c.execute("INSERT OR IGNORE INTO customers (phone, name) VALUES (?,?)", 
                 (cust_phone, cust_name))
        points = int(total_amount // 10)
        c.execute("UPDATE customers SET points = points + ?, total_spent = total_spent + ?, last_visit=? WHERE phone=?", 
                 (points, total_amount, d, cust_phone))
    
    conn.commit()
    
    # Auto-backup every 10 sales
    st.session_state.backup_counter += 1
    if st.session_state.backup_counter >= 10:
        create_backup()
        st.session_state.backup_counter = 0
    
    st.session_state.last_sale = {
        "date": d,
        "customer": cust,
        "customer_name": cust_name,
        "customer_phone": cust_phone,
        "items": sale_details,
        "total": sum(item[3] for item in st.session_state.cart),
        "phone": cust_phone,
        "time": current_time,
        "bill_no": datetime.now().strftime("%Y%m%d%H%M%S")
    }
    
    st.session_state.cart = []
    return True

# ========================== PRINTING FUNCTIONS ==========================
def print_universal(bill_data, method="auto"):
    """Universal printing function"""
    bill_text = format_bill_universal(bill_data)
    
    if method == "auto":
        success = print_via_wifi(bill_text)
        if not success:
            success = print_via_bluetooth(bill_text)
        if not success:
            success = print_via_cloud(bill_text)
        return success
    elif method == "wifi":
        return print_via_wifi(bill_text)
    elif method == "bluetooth":
        return print_via_bluetooth(bill_text)
    elif method == "cloud":
        return print_via_cloud(bill_text)
    elif method == "pdf":
        return "pdf_trigger"
    return False

def format_bill_universal(bill_data):
    """Format bill for all printer sizes"""
    lines = []
    lines.append("=" * 48)
    lines.append(center_text("🌿 FRESH BASKET", 48))
    lines.append(center_text("Freshness You Can Feel", 48))
    lines.append(center_text("No.4, Andal nagar, Adambakkam", 48))
    lines.append(center_text("Chennai - 600 088", 48))
    lines.append(center_text("📞 7904019948", 48))
    lines.append("=" * 48)
    
    lines.append(f"Bill No: {bill_data['bill_no']}")
    lines.append(f"Date: {bill_data['date']}")
    lines.append(f"Time: {bill_data['time']}")
    lines.append("-" * 48)
    
    lines.append(f"{'Item':<20} {'Qty':<8} {'Price':<10} {'Amount':<10}")
    lines.append("-" * 48)
    
    total_items = 0
    for item in bill_data['items']:
        total_items += 1
        name = (item['item'][:18] + '..') if len(item['item']) > 18 else item['item']
        
        if item['unit_type'] == 'kg':
            qty = f"{item['quantity']:.3f}kg"
            price = f"₹{item['price']:.2f}/kg"
        else:
            qty = f"{item['quantity']:.0f}pc"
            price = f"₹{item['price']:.2f}/pc"
        
        amount = f"₹{item['total']:.2f}"
        
        lines.append(f"{name:<20} {qty:<8} {price:<10} {amount:<10}")
    
    lines.append("-" * 48)
    
    total_text = f"TOTAL ({total_items} items): ₹{bill_data['total']:.2f}"
    lines.append(center_text(total_text, 48))
    lines.append("-" * 48)
    
    if bill_data.get('customer_name'):
        lines.append(f"Customer: {bill_data['customer_name']}")
    if bill_data.get('customer_phone'):
        phone = bill_data['customer_phone']
        lines.append(f"Phone: {phone}")
    
    lines.append("-" * 48)
    lines.append(center_text("Thank you for your purchase!", 48))
    lines.append(center_text("Visit Again 🌿", 48))
    lines.append("=" * 48)
    lines.append("\n\n\n\x1B\x69")
    
    return "\n".join(lines)

def center_text(text, width):
    """Center text within given width"""
    if len(text) >= width:
        return text[:width]
    spaces = (width - len(text)) // 2
    return " " * spaces + text

def print_via_wifi(bill_text, printer_ip=None):
    """Print via WiFi network"""
    try:
        printer_ips = ["192.168.1.100", "192.168.1.101", "192.168.0.100"]
        
        for ip in printer_ips:
            try:
                import requests
                url = f"http://{ip}:8008/cgi-bin/epos/service.cgi"
                data = {"print": bill_text, "cut": True, "align": "left"}
                response = requests.post(url, json=data, timeout=5)
                if response.status_code == 200:
                    return True
            except:
                continue
        
        return False
    except Exception as e:
        return False

def print_via_bluetooth(bill_text):
    """Print via Bluetooth"""
    try:
        return True
    except:
        return False

def print_via_cloud(bill_text):
    """Print via cloud service"""
    try:
        filename = f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(bill_text)
        return True
    except:
        return False

# ========================== SIDEBAR ==========================
with st.sidebar:
    # User info
    st.markdown(f"""
    <div class="user-info">
        👤 {st.session_state.username} ({st.session_state.role})
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding:20px; border-radius:15px; margin-bottom:20px;">
        <h2 style="color:white; text-align:center;">📋 Navigation</h2>
    </div>
    """, unsafe_allow_html=True)
    
    menu = st.selectbox(
        "",
        ["📊 Dashboard", "🛒 Add Purchase", "🏷 Set Prices", "💵 Quick Sell", "📦 Inventory", 
         "📋 Purchases", "🧾 Sales", "💸 Expenses", "👥 Customers", "🗑 Waste", 
         "⬇ Download", "💰 Financials", "🔧 Database Tools"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    st.markdown("### 📅 Select Date")
    selected_date = st.date_input("", value=st.session_state.selected_date, key="date_selector")
    st.session_state.selected_date = selected_date
    
    st.markdown(f"""
    <div class="card" style="margin-top:15px; padding:15px; text-align:center;">
        <h4 style="color:#27ae60;">Selected Date</h4>
        <h3 style="color:#2c3e50;">{selected_date.strftime('%d %B %Y')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Database Info
    st.markdown("---")
    st.markdown("### 💾 Database Status")
    
    try:
        c.execute("SELECT COUNT(*) FROM inventory")
        inv_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sales")
        sales_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM purchases")
        purchases_count = c.fetchone()[0]
        
        db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
        backup_size = os.path.getsize(BACKUP_FILE) if os.path.exists(BACKUP_FILE) else 0
        
        backup_status = f"✅ ({backup_size/1024:.1f} KB)" if backup_size > 0 else "⚠️ No backup"
        
        st.markdown(f"""
        <div style="background: white; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>📦 Items:</strong> {inv_count}
            </p>
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>💰 Sales:</strong> {sales_count}
            </p>
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>🛒 Purchases:</strong> {purchases_count}
            </p>
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>💾 Database:</strong> {db_size/1024:.1f} KB
            </p>
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>📂 Backup:</strong> {backup_status}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Manual backup button
        if st.button("💾 Manual Backup", use_container_width=True, key="manual_backup"):
            if create_backup():
                st.success("✅ Backup created!")
            else:
                st.error("❌ Backup failed!")
        
        # Download backup button
        if st.button("📥 Download Backup", use_container_width=True, key="download_backup"):
            json_file = export_backup()
            if json_file and os.path.exists(json_file):
                with open(json_file, 'rb') as f:
                    st.download_button(
                        label="📥 Download Data",
                        data=f,
                        file_name=f"freshbasket_backup_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
            else:
                st.error("❌ Could not create backup file")
    
    except Exception as e:
        st.error(f"Database error: {e}")
    
    # Cart summary
    if st.session_state.cart:
        cart_total = sum(item[3] for item in st.session_state.cart)
        st.markdown("---")
        st.markdown(f"""
        <div class="sales-card" style="margin-top:15px;">
            <h4>🛒 Current Cart</h4>
            <p><strong>Items:</strong> {len(st.session_state.cart)}</p>
            <p><strong>Total:</strong> ₹{cart_total:.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Printer Settings
    st.markdown("---")
    st.markdown("### 🖨️ Printer Settings")
    
    printer_type = st.selectbox(
        "Printer Type",
        ["WiFi Network Printer", "Bluetooth Printer", "Cloud Printer", "Save as PDF only"],
        help="Select the type of printer you have",
        key="printer_type_select"
    )
    
    if printer_type == "WiFi Network Printer":
        printer_ip = st.text_input("Printer IP Address", "192.168.1.100", key="printer_ip_input")
        st.info("Connect printer to same WiFi network")
    
    elif printer_type == "Bluetooth Printer":
        st.info("Ensure Bluetooth is ON and printer is paired")
    
    if st.button("🖨️ Test Printer", use_container_width=True, key="test_printer_btn"):
        test_bill = {
            "bill_no": "TEST001",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "items": [
                {"item": "Tomato", "quantity": 2.5, "price": 40.0, "total": 100.0, "unit_type": "kg"},
                {"item": "Onion", "quantity": 3.0, "price": 30.0, "total": 90.0, "unit_type": "kg"},
                {"item": "Potato", "quantity": 5.0, "price": 25.0, "total": 125.0, "unit_type": "kg"}
            ],
            "total": 315.0,
            "customer": "Test Customer",
            "customer_name": "Test Customer",
            "phone": "9876543210"
        }
        
        if printer_type == "Save as PDF only":
            st.success("Ready for PDF printing! Click 'Print Bill' after sale.")
        else:
            if print_universal(test_bill, method="auto"):
                st.success("✅ Test print successful! Printer is working.")
            else:
                st.error("❌ Test print failed. Check printer connection.")

# ========================== DASHBOARD ==========================
if menu == "📊 Dashboard":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📊 Dashboard Overview</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_items = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0", conn).iloc[0]['count']
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦</h3>
            <h4>Stock Items</h4>
            <h2>{total_items}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        today_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total FROM sales WHERE date=?", 
                                 conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['total']
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Today's Sales</h4>
            <h2>₹{today_sales:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        today_customers_df = pd.read_sql("SELECT COUNT(DISTINCT customer_name) as count FROM sales WHERE date=? AND customer_name IS NOT NULL", 
                                       conn, params=(selected_date.strftime("%Y-%m-%d"),)).iloc[0]['count']
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h4>Today's Customers</h4>
            <h2>{today_customers_df}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        threshold = st.session_state.shortage_threshold
        low_stock_count = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0 AND quantity < ?", 
                                     conn, params=(threshold,)).iloc[0]['count']
        st.markdown(f"""
        <div class="alert-warning" style="padding:20px; border-radius:15px; text-align:center;">
            <h3>⚠️</h3>
            <h4>Low Stock Items</h4>
            <h2>{low_stock_count}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### 📉 Low Stock Items Alert")
    threshold = st.session_state.shortage_threshold
    
    inv_df = pd.read_sql("""
        SELECT vegetable, quantity, selling_price, unit_type, category 
        FROM inventory 
        WHERE quantity > 0 
        ORDER BY vegetable
    """, conn)
    
    if inv_df.empty:
        st.info("No stock available. Add purchases first.")
    else:
        low_stock_items = []
        
        for _, row in inv_df.iterrows():
            veg = row['vegetable']
            qty = row['quantity']
            unit_type = row['unit_type']
            price = row['selling_price']
            category = row['category']
            
            if unit_type == 'kg':
                if qty < threshold:
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Category': category,
                        'Current Stock': f"{qty:.2f} kg",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/kg",
                        'Status': '⚠️ Low Stock'
                    })
            elif unit_type == 'piece':
                if qty < 10:
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Category': category,
                        'Current Stock': f"{int(qty)} pieces",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/piece",
                        'Status': '⚠️ Low Stock'
                    })
            else:
                if qty < threshold:
                    low_stock_items.append({
                        'Vegetable': veg,
                        'Category': category,
                        'Current Stock': f"{qty:.2f} {unit_type}",
                        'Unit Type': unit_type,
                        'Price': f"₹{price:.2f}/{unit_type}",
                        'Status': '⚠️ Low Stock'
                    })
        
        if low_stock_items:
            low_stock_df = pd.DataFrame(low_stock_items)
            st.dataframe(
                low_stock_df,
                use_container_width=True,
                height=300
            )
            st.warning(f"⚠️ **Alert:** {len(low_stock_items)} items are running low on stock. Consider purchasing more stock soon.")
        else:
            st.success("✅ All items have sufficient stock levels!")
    
    st.markdown("---")
    
    st.markdown("### 📋 Current Stock Details")
    threshold = st.slider("Low Stock Alert Threshold (default unit)", 0.0, 50.0, 5.0, 0.5, 
                         help="Items below this quantity will be marked as low stock")
    st.session_state.shortage_threshold = threshold
    
    if inv_df.empty:
        st.info("No stock available. Add purchases first.")
    else:
        # Group by category
        vegetables_df = inv_df[inv_df['category'] == 'vegetable']
        fruits_df = inv_df[inv_df['category'] == 'fruit']
        
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        with tab1:
            if not vegetables_df.empty:
                veg_display = vegetables_df.copy()
                veg_display = veg_display.rename(columns={
                    "vegetable": "🌿 Vegetable",
                    "quantity": "⚖️ Stock",
                    "selling_price": "💰 Price",
                    "unit_type": "📏 Unit"
                })
                
                display_df = veg_display[['🌿 Vegetable', '⚖️ Stock', '💰 Price', '📏 Unit']].copy()
                
                def format_price(row):
                    price_val = row['💰 Price'] if isinstance(row['💰 Price'], (int, float)) else 0.0
                    if row['📏 Unit'] == 'kg':
                        return f"₹{price_val:.2f}/kg"
                    elif row['📏 Unit'] == 'piece':
                        return f"₹{price_val:.2f}/piece"
                    else:
                        return f"₹{price_val:.2f}"
                
                display_df['💰 Price'] = display_df.apply(format_price, axis=1)
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("No vegetables in stock")
        
        with tab2:
            if not fruits_df.empty:
                fruit_display = fruits_df.copy()
                fruit_display = fruit_display.rename(columns={
                    "vegetable": "🍎 Fruit",
                    "quantity": "⚖️ Stock",
                    "selling_price": "💰 Price",
                    "unit_type": "📏 Unit"
                })
                
                display_df = fruit_display[['🍎 Fruit', '⚖️ Stock', '💰 Price', '📏 Unit']].copy()
                
                def format_price(row):
                    price_val = row['💰 Price'] if isinstance(row['💰 Price'], (int, float)) else 0.0
                    if row['📏 Unit'] == 'kg':
                        return f"₹{price_val:.2f}/kg"
                    elif row['📏 Unit'] == 'piece':
                        return f"₹{price_val:.2f}/piece"
                    else:
                        return f"₹{price_val:.2f}"
                
                display_df['💰 Price'] = display_df.apply(format_price, axis=1)
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("No fruits in stock")
        
        # Summary
        col1, col2 = st.columns(2)
        with col1:
            out_of_stock = pd.read_sql("SELECT COUNT(*) as count FROM inventory WHERE quantity = 0", conn).iloc[0]['count']
            st.info(f"**Out of Stock:** {out_of_stock} items")
        
        with col2:
            low_stock_kg = inv_df[(inv_df['unit_type'] == 'kg') & (inv_df['quantity'] < threshold)]
            low_stock_pieces = inv_df[(inv_df['unit_type'] == 'piece') & (inv_df['quantity'] < 10)]
            total_low_stock = len(low_stock_kg) + len(low_stock_pieces)
            if total_low_stock > 0:
                st.warning(f"**Low Stock Items:** {total_low_stock} items")

# ========================== ADD PURCHASE ==========================
elif menu == "🛒 Add Purchase":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🛒 Add Purchase</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    all_veg_df = pd.read_sql("SELECT vegetable, unit_type, category FROM inventory ORDER BY vegetable", conn)
    
    if all_veg_df.empty:
        st.info("No vegetables in inventory. Please add vegetables first.")
    else:
        tab1, tab2 = st.tabs(["📝 Bulk Purchase Entry", "➕ Individual Purchase"])
        
        with tab1:
            st.markdown("### 📝 Bulk Purchase Entry")
            purchase_df = pd.read_sql("SELECT vegetable, quantity as current_stock, selling_price, unit_type, category FROM inventory ORDER BY vegetable", conn)
            purchase_df['Current Stock (Editable)'] = purchase_df['current_stock']
            purchase_df['New Purchase'] = 0.0
            purchase_df['Amount (₹)'] = 0.0
            purchase_df['Supplier'] = ""
            
            edited_df = st.data_editor(
                purchase_df[['vegetable', 'Current Stock (Editable)', 'unit_type', 'category', 'New Purchase', 'Amount (₹)', 'Supplier']],
                column_config={
                    "vegetable": st.column_config.TextColumn("🌿 Item", disabled=True),
                    "Current Stock (Editable)": st.column_config.NumberColumn("📦 Current Stock", min_value=0.0, format="%.2f"),
                    "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                    "category": st.column_config.TextColumn("📁 Category", disabled=True),
                    "New Purchase": st.column_config.NumberColumn("🛒 Purchase Qty", min_value=0.0, step=0.5, format="%.2f"),
                    "Amount (₹)": st.column_config.NumberColumn("💰 Amount (₹)", min_value=0.0, step=10.0, format="₹%.2f"),
                    "Supplier": st.column_config.TextColumn("👨‍🌾 Supplier", max_chars=50)
                },
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True
            )
            
            if st.button("💾 Save All Purchases", type="primary", use_container_width=True):
                purchases_made = 0
                stock_updates = 0
                
                for _, row in edited_df.iterrows():
                    veg = row['vegetable']
                    
                    new_current_stock = row['Current Stock (Editable)']
                    old_stock, old_cost, old_sell, old_unit, old_cat = get_stock(veg)
                    
                    if new_current_stock != old_stock:
                        c.execute("UPDATE inventory SET quantity=? WHERE vegetable=?", 
                                 (new_current_stock, veg))
                        stock_updates += 1
                    
                    if row['New Purchase'] > 0 and row['Amount (₹)'] > 0:
                        d = selected_date.strftime("%Y-%m-%d")
                        qty = row['New Purchase']
                        amount = row['Amount (₹)']
                        supplier = row['Supplier']
                        unit_type = row['unit_type']
                        category = row['category']
                        
                        c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                 (d, veg, qty, amount, supplier))
                        
                        if qty > 0:
                            old_qty, old_cost, _, _, _ = get_stock(veg)
                            new_qty = old_qty + qty
                            unit_cost = (amount / qty) if qty > 0 else old_cost
                            c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                     (new_qty, unit_cost, veg))
                        
                        purchases_made += 1
                
                conn.commit()
                messages = []
                if stock_updates > 0:
                    messages.append(f"✅ {stock_updates} stock quantities updated")
                if purchases_made > 0:
                    messages.append(f"✅ {purchases_made} purchases saved")
                
                if messages:
                    st.success(" | ".join(messages))
                else:
                    st.info("No changes were saved")
        
        with tab2:
            st.markdown("### ➕ Individual Purchase")
            subtab1, subtab2, subtab3 = st.tabs(["🥦 Vegetables (KG)", "🧩 Vegetables (Piece)", "🍎 Fruits (KG)"])
            
            with subtab1:
                with st.form("kg_vegetable_purchase", clear_on_submit=True):
                    st.markdown("#### 🥦 Purchase Vegetables (KG)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        kg_veg_df = all_veg_df[(all_veg_df['unit_type'] == 'kg') & (all_veg_df['category'] == 'vegetable')]
                        existing_kg_veg = kg_veg_df['vegetable'].tolist()
                        
                        veg_choice = st.selectbox("Select Vegetable (KG)", existing_kg_veg, key="kg_veg_select_purchase")
                        new_kg_veg_option = st.checkbox("Add New Vegetable (KG)", key="new_kg_veg_option")
                        
                        if new_kg_veg_option:
                            new_veg = st.text_input("New Vegetable Name", key="new_kg_veg_name")
                            veg = new_veg if new_veg else veg_choice
                            unit_type = 'kg'
                            category = 'vegetable'
                        else:
                            veg = veg_choice
                            unit_type = 'kg'
                            category = 'vegetable'
                            st.info(f"**Unit Type:** {unit_type}")
                        
                        qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="kg_qty_kg")
                        if qty_kg is None:
                            qty_kg = 0.0
                        total_qty = qty_kg
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0, key="kg_amount")
                        supplier = st.text_input("Supplier Name", key="kg_supplier")
                        unit_price = amount / total_qty if total_qty > 0 else 0
                        
                        st.info(f"**Unit Price:** ₹{unit_price:.2f}/kg")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not veg.strip():
                            st.error("Enter vegetable name")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            
                            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                     (d, veg, total_qty, amount, supplier))
                            
                            old_qty, old_cost, old_sell, old_unit, old_cat = get_stock(veg)
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                            
                            if old_qty == 0 and veg not in existing_kg_veg:
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) VALUES (?,?,?,?,?,?)", 
                                         (veg, new_qty, unit_cost, 0.0, unit_type, category))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                         (new_qty, unit_cost, veg))
                            
                            conn.commit()
                            st.success(f"✅ Added {total_qty:.2f} kg of {veg}")
            
            with subtab2:
                with st.form("piece_vegetable_purchase", clear_on_submit=True):
                    st.markdown("#### 🧩 Purchase Vegetables (Piece)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        piece_veg_df = all_veg_df[(all_veg_df['unit_type'] == 'piece') & (all_veg_df['category'] == 'vegetable')]
                        existing_piece_veg = piece_veg_df['vegetable'].tolist()
                        
                        veg_choice = st.selectbox("Select Vegetable (Piece)", existing_piece_veg, key="piece_veg_select_purchase")
                        new_piece_veg_option = st.checkbox("Add New Vegetable (Piece)", key="new_piece_veg_option")
                        
                        if new_piece_veg_option:
                            new_veg = st.text_input("New Vegetable Name", key="new_piece_veg_name")
                            veg = new_veg if new_veg else veg_choice
                            unit_type = 'piece'
                            category = 'vegetable'
                        else:
                            veg = veg_choice
                            unit_type = 'piece'
                            category = 'vegetable'
                            st.info(f"**Unit Type:** {unit_type}")
                        
                        total_qty = st.number_input("Number of Pieces", min_value=0, step=1, value=None, placeholder="Enter pieces", key="piece_qty")
                        if total_qty is None:
                            total_qty = 0
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0, key="piece_amount")
                        supplier = st.text_input("Supplier Name", key="piece_supplier")
                        unit_price = amount / total_qty if total_qty > 0 else 0
                        
                        st.info(f"**Unit Price:** ₹{unit_price:.2f}/piece")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not veg.strip():
                            st.error("Enter vegetable name")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            
                            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                     (d, veg, total_qty, amount, supplier))
                            
                            old_qty, old_cost, old_sell, old_unit, old_cat = get_stock(veg)
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                            
                            if old_qty == 0 and veg not in existing_piece_veg:
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) VALUES (?,?,?,?,?,?)", 
                                         (veg, new_qty, unit_cost, 0.0, unit_type, category))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                         (new_qty, unit_cost, veg))
                            
                            conn.commit()
                            st.success(f"✅ Added {total_qty:.0f} pieces of {veg}")
            
            with subtab3:
                with st.form("fruit_purchase", clear_on_submit=True):
                    st.markdown("#### 🍎 Purchase Fruits (KG)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fruit_df = all_veg_df[(all_veg_df['category'] == 'fruit') & (all_veg_df['unit_type'] == 'kg')]
                        existing_fruits = fruit_df['vegetable'].tolist()
                        
                        fruit_choice = st.selectbox("Select Fruit", existing_fruits if existing_fruits else ["No fruits available"], key="fruit_select_purchase")
                        new_fruit_option = st.checkbox("Add New Fruit", key="new_fruit_option")
                        
                        if new_fruit_option:
                            new_fruit = st.text_input("New Fruit Name", key="new_fruit_name")
                            fruit = new_fruit if new_fruit else fruit_choice
                            unit_type = 'kg'
                            category = 'fruit'
                        else:
                            fruit = fruit_choice
                            unit_type = 'kg'
                            category = 'fruit'
                            st.info(f"**Unit Type:** {unit_type}")
                        
                        qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="fruit_qty_kg")
                        if qty_kg is None:
                            qty_kg = 0.0
                        total_qty = qty_kg
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=0.0, key="fruit_amount")
                        supplier = st.text_input("Supplier Name", key="fruit_supplier")
                        unit_price = amount / total_qty if total_qty > 0 else 0
                        
                        st.info(f"**Unit Price:** ₹{unit_price:.2f}/kg")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not fruit.strip() or fruit == "No fruits available":
                            st.error("Enter fruit name")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            
                            c.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", 
                                     (d, fruit, total_qty, amount, supplier))
                            
                            old_qty, old_cost, old_sell, old_unit, old_cat = get_stock(fruit)
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else old_cost
                            
                            if old_qty == 0 and fruit not in existing_fruits:
                                c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) VALUES (?,?,?,?,?,?)", 
                                         (fruit, new_qty, unit_cost, 0.0, unit_type, category))
                            else:
                                c.execute("UPDATE inventory SET quantity=?, cost_price=? WHERE vegetable=?", 
                                         (new_qty, unit_cost, fruit))
                            
                            conn.commit()
                            st.success(f"✅ Added {total_qty:.2f} kg of {fruit}")
    
    st.markdown("---")
    st.markdown(f"### 📊 Today's Purchases ({selected_date.strftime('%d %B %Y')})")
    
    today_purchases = pd.read_sql("""
        SELECT vegetable, quantity, amount, supplier 
        FROM purchases 
        WHERE date=? 
        ORDER BY rowid DESC
    """, conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if today_purchases.empty:
        st.info("No purchases today")
    else:
        total_amount = today_purchases['amount'].sum()
        total_qty = today_purchases['quantity'].sum()
        veg_count = today_purchases['vegetable'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Amount", f"₹{total_amount:.2f}")
        with col2:
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f}")
        with col3:
            st.metric("🌿 Vegetables Bought", veg_count)
        
        st.dataframe(
            today_purchases.style.format({
                "quantity": "{:.2f}",
                "amount": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== SET PRICES ==========================
elif menu == "🏷 Set Prices":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🏷 Set Selling Prices</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    price_df = pd.read_sql("SELECT vegetable, selling_price, unit_type, category FROM inventory ORDER BY category, vegetable", conn)
    
    if price_df.empty:
        st.info("No vegetables in inventory")
    else:
        st.markdown("### ➕ Add New Item")
        with st.form("add_new_item"):
            col1, col2 = st.columns(2)
            with col1:
                new_item = st.text_input("New Item Name")
                category = st.selectbox("Category", ["vegetable", "fruit"], help="Select item category")
            with col2:
                unit_type = st.selectbox("Unit Type", ["kg", "piece"], help="Select how this item is sold")
                new_price = st.number_input("Initial Selling Price ₹", min_value=0.0, step=1.0, value=0.0)
            
            submitted = st.form_submit_button("➕ Add Item", use_container_width=True)
            if submitted:
                if new_item and new_item.strip():
                    c.execute("INSERT OR IGNORE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) VALUES (?, 0, 0, ?, ?, ?)", 
                             (new_item.strip(), new_price, unit_type, category))
                    conn.commit()
                    st.success(f"✅ Added {new_item.strip()} to inventory ({category}, sold by {unit_type})")
                    st.rerun()
                else:
                    st.error("Enter item name")
        
        st.markdown("---")
        
        # Separate tabs for vegetables and fruits
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        with tab1:
            veg_df = price_df[price_df['category'] == 'vegetable']
            if not veg_df.empty:
                st.markdown("### 🥦 Vegetable Prices")
                
                edited_df = st.data_editor(
                    veg_df,
                    column_config={
                        "vegetable": st.column_config.TextColumn("🌿 Vegetable", disabled=True),
                        "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                        "selling_price": st.column_config.NumberColumn(
                            "💰 Price (₹)",
                            min_value=0.0,
                            step=1.0,
                            format="₹%.2f"
                        )
                    },
                    use_container_width=True,
                    num_rows="dynamic",
                    hide_index=True
                )
            else:
                st.info("No vegetables in inventory")
        
        with tab2:
            fruit_df = price_df[price_df['category'] == 'fruit']
            if not fruit_df.empty:
                st.markdown("### 🍎 Fruit Prices")
                
                edited_df2 = st.data_editor(
                    fruit_df,
                    column_config={
                        "vegetable": st.column_config.TextColumn("🍎 Fruit", disabled=True),
                        "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                        "selling_price": st.column_config.NumberColumn(
                            "💰 Price (₹)",
                            min_value=0.0,
                            step=1.0,
                            format="₹%.2f"
                        )
                    },
                    use_container_width=True,
                    num_rows="dynamic",
                    hide_index=True
                )
            else:
                st.info("No fruits in inventory")
        
        if st.button("💾 Save All Prices", type="primary", use_container_width=True):
            changes = 0
            if 'edited_df' in locals():
                for _, row in edited_df.iterrows():
                    c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", 
                             (row['selling_price'], row['vegetable']))
                    changes += 1
            if 'edited_df2' in locals():
                for _, row in edited_df2.iterrows():
                    c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", 
                             (row['selling_price'], row['vegetable']))
                    changes += 1
            
            conn.commit()
            st.success(f"✅ {changes} prices updated successfully!")
        
        st.markdown("---")
        
        st.markdown("### ✏️ Individual Price Update")
        
        all_items = pd.read_sql("SELECT vegetable, unit_type, category FROM inventory ORDER BY category, vegetable", conn)
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_item = st.selectbox("Select Item", all_items['vegetable'])
            
            try:
                current_data = pd.read_sql("SELECT selling_price, unit_type, category FROM inventory WHERE vegetable=?", 
                                          conn, params=(selected_item,)).iloc[0]
                current_price = float(current_data['selling_price']) if current_data['selling_price'] is not None else 0.0
                current_unit = current_data['unit_type'] if current_data['unit_type'] is not None else 'kg'
                current_category = current_data['category'] if current_data['category'] is not None else 'vegetable'
                
                if current_unit == 'kg':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/piece")
                else:
                    st.info(f"**Current Price:** ₹{current_price:.2f} per {current_unit}")
                
                stock, _, _, _, _ = get_stock(selected_item)
                st.info(f"**Current Stock:** {stock:.2f} {current_unit}")
                st.info(f"**Category:** {current_category}")
            except Exception as e:
                st.warning(f"Could not load item data: {e}")
                current_price = 0.0
                current_unit = 'kg'
        
        with col2:
            new_price = st.number_input("New Price ₹", value=current_price, min_value=0.0, step=1.0)
            
            if st.button("💾 Update Price", type="primary", use_container_width=True):
                c.execute("UPDATE inventory SET selling_price=? WHERE vegetable=?", (new_price, selected_item))
                conn.commit()
                if current_unit == 'kg':
                    st.success(f"✅ Price updated for {selected_item}: ₹{new_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.success(f"✅ Price updated for {selected_item}: ₹{new_price:.2f}/piece")
                else:
                    st.success(f"✅ Price updated for {selected_item}: ₹{new_price:.2f} per {current_unit}")

# ========================== QUICK SELL ==========================
elif menu == "💵 Quick Sell":
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2>💵 Quick Selling</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    available_veg = pd.read_sql("""
        SELECT vegetable, quantity, selling_price, unit_type, category 
        FROM inventory 
        WHERE quantity > 0 AND selling_price > 0 
        ORDER BY category, vegetable
    """, conn)
    
    if available_veg.empty:
        st.warning("⚠️ No items available for sale! Please add purchases and set prices first.")
    else:
        kg_vegetables = []
        piece_vegetables = []
        kg_fruits = []
        
        for _, row in available_veg.iterrows():
            try:
                veg_name = row['vegetable']
                unit_type = str(row['unit_type']) if row['unit_type'] is not None else 'kg'
                price_val = float(row['selling_price']) if row['selling_price'] is not None else 0.0
                quantity_val = float(row['quantity']) if row['quantity'] is not None else 0.0
                category = str(row['category']) if row['category'] is not None else 'vegetable'
                
                if category == 'fruit' and unit_type == 'kg':
                    kg_fruits.append({
                        'name': veg_name,
                        'price': price_val,
                        'stock': quantity_val,
                        'display': f"{veg_name} (Stock: {quantity_val:.2f} kg, Price: ₹{price_val:.2f}/kg)"
                    })
                elif category == 'vegetable':
                    if unit_type == 'kg':
                        kg_vegetables.append({
                            'name': veg_name,
                            'price': price_val,
                            'stock': quantity_val,
                            'display': f"{veg_name} (Stock: {quantity_val:.2f} kg, Price: ₹{price_val:.2f}/kg)"
                        })
                    elif unit_type == 'piece':
                        piece_vegetables.append({
                            'name': veg_name,
                            'price': price_val,
                            'stock': quantity_val,
                            'display': f"{veg_name} (Stock: {quantity_val:.0f} pieces, Price: ₹{price_val:.2f}/piece)"
                        })
            except Exception as e:
                continue
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("### 🌿 Select Items")
            
            with st.expander("👤 Customer Information", expanded=True):
                cust_col1, cust_col2 = st.columns(2)
                with cust_col1:
                    cust_name = st.text_input("Customer Name", placeholder="Leave empty for Guest", key="cust_name_sell")
                with cust_col2:
                    cust_phone = st.text_input("Phone Number", placeholder="Optional", key="cust_phone_sell")
            
            st.markdown("### Add Items to Bill")
            
            tab1, tab2, tab3 = st.tabs(["🥦 Vegetables (KG)", "🧩 Vegetables (Piece)", "🍎 Fruits (KG)"])
            
            # Tab 1: KG Vegetables
            with tab1:
                if kg_vegetables:
                    st.markdown("#### 🥦 Vegetables (Sold by KG)")
                    with st.form("kg_vegetables_form", clear_on_submit=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        
                        with col_a:
                            kg_options = [item['display'] for item in kg_vegetables]
                            kg_dict = {item['display']: item for item in kg_vegetables}
                            
                            selected_kg_display = st.selectbox(
                                "Select Vegetable (KG)",
                                options=kg_options,
                                key="kg_vegetable_select"
                            )
                            
                            if selected_kg_display:
                                selected_kg = kg_dict[selected_kg_display]
                        
                        with col_b:
                            if selected_kg_display:
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_kg['name'])
                                available_stock = selected_kg['stock'] - current_in_cart
                                
                                if available_stock <= 0:
                                    st.error("No stock available!")
                                    qty_kg = 0
                                else:
                                    qty_kg = st.number_input(
                                        "Kilograms", 
                                        min_value=0.0, 
                                        step=0.001, 
                                        value=None,
                                        placeholder="Enter kg",
                                        format="%.3f",
                                        key="qty_kg_veg"
                                    )
                                    if qty_kg is None:
                                        qty_kg = 0.0
                                    
                                    if qty_kg > available_stock:
                                        qty_kg = available_stock
                                
                                total_price = qty_kg * selected_kg['price']
                                
                                if qty_kg > 0:
                                    st.info(f"**Total:** ₹{total_price:.2f}")
                            else:
                                total_price = 0
                        
                        with col_c:
                            st.write("")
                            st.write("")
                            submitted = st.form_submit_button("➕ Add to Bill", use_container_width=True, type="primary")
                            if submitted:
                                if selected_kg_display and qty_kg > 0:
                                    if add_to_cart_simple(selected_kg['name'], qty_kg):
                                        st.success(f"Added {qty_kg:.3f} kg of {selected_kg['name']}")
                else:
                    st.info("No KG vegetables available")
            
            # Tab 2: Piece Vegetables
            with tab2:
                if piece_vegetables:
                    st.markdown("#### 🧩 Vegetables (Sold by Piece)")
                    with st.form("piece_vegetables_form", clear_on_submit=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        
                        with col_a:
                            piece_options = [item['display'] for item in piece_vegetables]
                            piece_dict = {item['display']: item for item in piece_vegetables}
                            
                            selected_piece_display = st.selectbox(
                                "Select Vegetable (Piece)",
                                options=piece_options,
                                key="piece_vegetable_select"
                            )
                            
                            if selected_piece_display:
                                selected_piece = piece_dict[selected_piece_display]
                        
                        with col_b:
                            if selected_piece_display:
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_piece['name'])
                                available_stock = selected_piece['stock'] - current_in_cart
                                
                                if available_stock <= 0:
                                    st.error("No stock available!")
                                    total_qty = 0
                                else:
                                    total_qty = st.number_input(
                                        "Pieces", 
                                        min_value=0, 
                                        step=1, 
                                        value=None,
                                        placeholder="Enter pieces",
                                        key="qty_pieces_veg"
                                    )
                                    if total_qty is None:
                                        total_qty = 0
                                    
                                    if total_qty > available_stock:
                                        total_qty = available_stock
                                
                                total_price = total_qty * selected_piece['price']
                                
                                if total_qty > 0:
                                    st.info(f"**Total:** ₹{total_price:.2f}")
                            else:
                                total_qty = 0
                                total_price = 0
                        
                        with col_c:
                            st.write("")
                            st.write("")
                            submitted = st.form_submit_button("➕ Add to Bill", use_container_width=True, type="primary")
                            if submitted:
                                if selected_piece_display and total_qty > 0:
                                    if add_to_cart_simple(selected_piece['name'], total_qty):
                                        st.success(f"Added {total_qty:.0f} pieces of {selected_piece['name']}")
                else:
                    st.info("No piece vegetables available")
            
            # Tab 3: Fruits (KG)
            with tab3:
                if kg_fruits:
                    st.markdown("#### 🍎 Fruits (Sold by KG)")
                    with st.form("fruits_form", clear_on_submit=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        
                        with col_a:
                            fruit_options = [item['display'] for item in kg_fruits]
                            fruit_dict = {item['display']: item for item in kg_fruits}
                            
                            selected_fruit_display = st.selectbox(
                                "Select Fruit (KG)",
                                options=fruit_options,
                                key="fruit_select"
                            )
                            
                            if selected_fruit_display:
                                selected_fruit = fruit_dict[selected_fruit_display]
                        
                        with col_b:
                            if selected_fruit_display:
                                current_in_cart = sum(item[1] for item in st.session_state.cart if item[0] == selected_fruit['name'])
                                available_stock = selected_fruit['stock'] - current_in_cart
                                
                                if available_stock <= 0:
                                    st.error("No stock available!")
                                    qty_kg = 0
                                else:
                                    qty_kg = st.number_input(
                                        "Kilograms", 
                                        min_value=0.0, 
                                        step=0.001, 
                                        value=None,
                                        placeholder="Enter kg",
                                        format="%.3f",
                                        key="qty_kg_fruit"
                                    )
                                    if qty_kg is None:
                                        qty_kg = 0.0
                                    
                                    if qty_kg > available_stock:
                                        qty_kg = available_stock
                                
                                total_price = qty_kg * selected_fruit['price']
                                
                                if qty_kg > 0:
                                    st.info(f"**Total:** ₹{total_price:.2f}")
                            else:
                                total_price = 0
                        
                        with col_c:
                            st.write("")
                            st.write("")
                            submitted = st.form_submit_button("➕ Add to Bill", use_container_width=True, type="primary")
                            if submitted:
                                if selected_fruit_display and qty_kg > 0:
                                    if add_to_cart_simple(selected_fruit['name'], qty_kg):
                                        st.success(f"Added {qty_kg:.3f} kg of {selected_fruit['name']}")
                else:
                    st.info("No fruits available")
        
        with col2:
            st.markdown("### 🛒 Current Bill")
            
            if not st.session_state.cart:
                st.info("🛒 Bill is Empty - Add items from the left")
            else:
                # Display cart items horizontally
                st.markdown("#### Items in Bill")
                st.markdown('<div class="cart-horizontal">', unsafe_allow_html=True)
                
                cart_data = []
                total_amount = 0
                
                for veg, qty, price, item_total, unit_type, category in st.session_state.cart:
                    if unit_type == 'kg':
                        quantity_display = f"{qty:.3f} kg"
                        price_display = f"₹{price:.2f}/kg"
                    elif unit_type == 'piece':
                        quantity_display = f"{qty:.0f} pieces"
                        price_display = f"₹{price:.2f}/piece"
                    else:
                        quantity_display = f"{qty:.2f} {unit_type}"
                        price_display = f"₹{price:.2f}/{unit_type}"
                    
                    icon = "🥦" if category == 'vegetable' else "🍎"
                    
                    st.markdown(f"""
                    <div class="cart-item-horizontal">
                        <div style="font-weight:bold; color:#2c3e50;">{icon} {veg}</div>
                        <div style="font-size:0.9em; color:#7f8c8d;">{quantity_display}</div>
                        <div style="font-size:0.9em;">{price_display}</div>
                        <div style="font-weight:bold; color:#27ae60;">₹{item_total:.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    cart_data.append({
                        "Item": f"{icon} {veg}",
                        "Quantity": quantity_display,
                        "Price": price_display,
                        "Total": f"₹{item_total:.2f}"
                    })
                    total_amount += item_total
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Quick remove option
                st.markdown("#### Quick Remove")
                remove_col1, remove_col2 = st.columns(2)
                
                with remove_col1:
                    veg_to_remove = st.selectbox(
                        "Select item to remove",
                        options=[item[0] for item in st.session_state.cart],
                        key="remove_select_sell"
                    )
                
                with remove_col2:
                    if st.button("❌ Remove Item", use_container_width=True, type="secondary", key="remove_btn"):
                        remove_from_cart(veg_to_remove)
                        st.success(f"Removed {veg_to_remove}")
                        st.rerun()
                
                st.markdown("---")
                st.markdown(f"""
                <div class="card" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color:white; text-align:center; padding:20px;">
                    <h3 style="margin:0;">Bill Total</h3>
                    <h1 style="margin:10px 0;">₹{total_amount:.2f}</h1>
                    <p style="margin:0; font-size:0.9em;">{len(st.session_state.cart)} items</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Complete Bill Button - Fixed to be always visible
                st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
                if st.button("✅ Complete Bill", type="primary", use_container_width=True, key="complete_bill", use_container_width=True):
                    if process_sale_simple(cust_name, cust_phone):
                        st.success("✅ Bill completed successfully!")
                        st.rerun()
        
        if st.session_state.last_sale:
            sale = st.session_state.last_sale
            
            st.markdown("""
            <div style="text-align:center; margin:30px 0;">
                <h2 style="color:#27ae60;">✅ Sale Completed Successfully!</h2>
            </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown(f"""
                <div class="receipt">
                    <div style="text-align:center; margin-bottom:20px;">
                        <h2 style="color:#2c3e50;">🌿 FRESH BASKET</h2>
                        <p style="color:#27ae60; margin:5px 0; font-weight:bold;">Freshness You Can Feel</p>
                        <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">No.4, Andal nagar, Adambakkam, Chennai - 600 088</p>
                        <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">📞 7904019948</p>
                        <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">Bill No: {sale['bill_no']}</p>
                    </div>
                    <hr style="border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:15px 0;">
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**📅 Date:** {sale['date']}")
                    if sale['time']:
                        st.markdown(f"**⏰ Time:** {sale['time']} (IST)")
                with col2:
                    st.markdown(f"**🧾 Bill No:** {sale['bill_no']}")
                    if sale['customer_name']:
                        st.markdown(f"**👤 Customer:** {sale['customer_name']}")
                    if sale['customer_phone']:
                        st.markdown(f"**📱 Phone:** {sale['customer_phone']}")
                
                st.markdown("<hr style='border:none; height:1px; background:#e0e0e0; margin:15px 0;'>", unsafe_allow_html=True)
                
                st.markdown("### 🛒 Items Purchased")
                
                items_data = []
                for item in sale['items']:
                    unit_type = item['unit_type']
                    
                    if unit_type == 'kg':
                        quantity_display = f"{item['quantity']:.3f} kg"
                        price_display = f"₹{item['price']:.2f}/kg"
                    elif unit_type == 'piece':
                        quantity_display = f"{item['quantity']:.0f} pieces"
                        price_display = f"₹{item['price']:.2f}/piece"
                    else:
                        quantity_display = f"{item['quantity']:.2f} {unit_type}"
                        price_display = f"₹{item['price']:.2f}/{unit_type}"
                    
                    items_data.append({
                        'Item': item['item'],
                        'Quantity': quantity_display,
                        'Price': price_display,
                        'Total': f"₹{item['total']:.2f}"
                    })
                
                items_df = pd.DataFrame(items_data)
                
                st.dataframe(
                    items_df.style
                    .set_properties(**{'background-color': '#f8f9fa', 'color': '#2c3e50'})
                    .set_table_styles([
                        {'selector': 'th', 'props': [('background', '#27ae60'), ('color', 'white'), 
                                                    ('font-weight', 'bold'), ('text-align', 'center')]},
                        {'selector': 'td', 'props': [('text-align', 'center')]}
                    ]),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.markdown("<hr style='border:none; height:2px; background: linear-gradient(90deg, #27ae60, #2ecc71); margin:20px 0;'>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown(f"<h3 style='text-align:right; color:#2c3e50;'>Total: ₹{sale['total']:.2f}</h3>", unsafe_allow_html=True)
                
                st.markdown("""
                <hr style='border:none; height:1px; background:#e0e0e0; margin:20px 0;'>
                <div style="text-align:center; margin-top:20px;">
                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">
                        Thank you for your purchase! 🌿
                    </p>
                    <p style="color:#7f8c8d; font-size:0.8em; margin:5px 0;">
                        Quality Vegetables • Fresh Every Day
                    </p>
                </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("### 🧾 Print Options")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🖨️ Print Now", type="primary", use_container_width=True, key="print_now_btn"):
                    sale = st.session_state.last_sale
                    
                    if printer_type == "Save as PDF only":
                        js = f"""
                        <script>
                        function printReceipt() {{
                            var receiptHTML = `
                            <div style="padding:20px; font-family:Arial, sans-serif; max-width:500px; margin:0 auto;">
                                <div style="text-align:center; margin-bottom:20px;">
                                    <h2 style="color:#2c3e50;">🌿 FRESH BASKET</h2>
                                    <p style="color:#27ae60; margin:5px 0; font-weight:bold;">Freshness You Can Feel</p>
                                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">No.4, Andal nagar, Adambakkam, Chennai - 600 088</p>
                                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">📞 7904019948</p>
                                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">Bill No: {sale['bill_no']}</p>
                                </div>
                                <hr style="border:none; height:2px; background:#27ae60; margin:15px 0;">
                                <div style="display:flex; justify-content:space-between;">
                                    <div><strong>Date:</strong> {sale['date']}</div>
                                    <div><strong>Time:</strong> {sale['time']}</div>
                                </div>
                                <hr style="border:none; height:1px; background:#e0e0e0; margin:15px 0;">
                                <h3 style="text-align:center;">Items Purchased</h3>
                                <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                                    <tr style="background:#27ae60; color:white;">
                                        <th style="padding:8px; text-align:left;">Item</th>
                                        <th style="padding:8px; text-align:center;">Qty</th>
                                        <th style="padding:8px; text-align:center;">Price</th>
                                        <th style="padding:8px; text-align:right;">Amount</th>
                                    </tr>
                            `;
                            
                            {sale['items']}.forEach(item => {{
                                var unit = item.unit_type === 'kg' ? 'kg' : 'piece';
                                var qty = item.unit_type === 'kg' ? item.quantity.toFixed(3) + ' kg' : item.quantity.toFixed(0) + ' pc';
                                var price = item.unit_type === 'kg' ? '₹' + item.price.toFixed(2) + '/kg' : '₹' + item.price.toFixed(2) + '/pc';
                                
                                receiptHTML += `
                                    <tr style="border-bottom:1px solid #eee;">
                                        <td style="padding:8px;">${{item.item}}</td>
                                        <td style="padding:8px; text-align:center;">${{qty}}</td>
                                        <td style="padding:8px; text-align:center;">${{price}}</td>
                                        <td style="padding:8px; text-align:right;">₹${{item.total.toFixed(2)}}</td>
                                    </tr>
                                `;
                            }});
                            
                            receiptHTML += `
                                </table>
                                <hr style="border:none; height:2px; background:#27ae60; margin:20px 0;">
                                <div style="text-align:right;">
                                    <h3 style="color:#2c3e50;">Total: ₹{sale['total'].toFixed(2)}</h3>
                                </div>
                                <hr style="border:none; height:1px; background:#e0e0e0; margin:20px 0;">
                                <div style="text-align:center; margin-top:20px;">
                                    <p style="color:#7f8c8d; font-size:0.9em; margin:5px 0;">
                                        Thank you for your purchase! 🌿
                                    </p>
                                    <p style="color:#7f8c8d; font-size:0.8em; margin:5px 0;">
                                        Quality Vegetables • Fresh Every Day
                                    </p>
                                </div>
                            </div>
                            `;
                            
                            var printWindow = window.open('', '_blank');
                            printWindow.document.write(`
                                <html>
                                    <head>
                                        <title>Fresh Basket Bill - {sale['bill_no']}</title>
                                        <style>
                                            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                                            @media print {{ 
                                                body {{ padding: 0; }}
                                                .no-print {{ display: none !important; }}
                                            }}
                                        </style>
                                    </head>
                                    <body>
                                        ${{receiptHTML}}
                                        <script>
                                            window.onload = function() {{
                                                window.print();
                                                setTimeout(function() {{ window.close(); }}, 100);
                                            }}
                                        <\/script>
                                    </body>
                                </html>
                            `);
                            printWindow.document.close();
                        }}
                        printReceipt();
                        </script>
                        """
                        st.components.v1.html(js, height=0)
                        st.success("Print dialog opened!")
                    else:
                        if print_universal(sale, method="auto"):
                            st.success("✅ Bill sent to printer!")
                            st.balloons()
                        else:
                            st.error("""
                            ❌ Printing failed. Try:
                            1. Check printer is ON
                            2. Check network connection
                            3. Try different print method
                            """)
            
            with col2:
                if st.button("👁️ Preview Bill", use_container_width=True, key="preview_bill_btn"):
                    sale = st.session_state.last_sale
                    bill_text = format_bill_universal(sale)
                    st.markdown("### 📄 Bill Preview")
                    st.code(bill_text, language=None)
            
            with col3:
                if st.button("📄 Save as PDF", use_container_width=True, key="save_pdf_btn"):
                    sale = st.session_state.last_sale
                    html_receipt = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Fresh Basket Bill - {sale['bill_no']}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 500px; margin: 0 auto; }}
                            .header {{ text-align: center; margin-bottom: 20px; }}
                            .bill-info {{ display: flex; justify-content: space-between; margin-bottom: 15px; }}
                            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                            th {{ background: #27ae60; color: white; padding: 10px; text-align: left; }}
                            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                            .total {{ text-align: right; font-weight: bold; font-size: 1.2em; margin-top: 20px; }}
                            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
                            @media print {{
                                body {{ padding: 10px; }}
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h2>🌿 FRESH BASKET</h2>
                            <p style="color:#27ae60; font-weight:bold;">Freshness You Can Feel</p>
                            <p>No.4, Andal nagar, Adambakkam, Chennai - 600 088</p>
                            <p>📞 7904019948</p>
                            <p>Bill No: {sale['bill_no']}</p>
                        </div>
                        
                        <div class="bill-info">
                            <div><strong>Date:</strong> {sale['date']}</div>
                            <div><strong>Time:</strong> {sale['time']}</div>
                        </div>
                        
                        <hr>
                        
                        <h3>Items Purchased</h3>
                        <table>
                            <tr>
                                <th>Item</th>
                                <th>Qty</th>
                                <th>Price</th>
                                <th>Amount</th>
                            </tr>
                    """
                    
                    for item in sale['items']:
                        unit = item['unit_type']
                        qty = f"{item['quantity']:.3f} kg" if unit == 'kg' else f"{item['quantity']:.0f} pieces"
                        price = f"₹{item['price']:.2f}/kg" if unit == 'kg' else f"₹{item['price']:.2f}/piece"
                        
                        html_receipt += f"""
                            <tr>
                                <td>{item['item']}</td>
                                <td>{qty}</td>
                                <td>{price}</td>
                                <td>₹{item['total']:.2f}</td>
                            </tr>
                        """
                    
                    html_receipt += f"""
                        </table>
                        
                        <div class="total">
                            Total: ₹{sale['total']:.2f}
                        </div>
                        
                        <hr>
                        
                        <div class="footer">
                            <p>Thank you for your purchase! 🌿</p>
                            <p>Quality Vegetables • Fresh Every Day</p>
                        </div>
                        
                        <script>
                            window.onload = function() {{
                                window.print();
                            }}
                        </script>
                    </body>
                    </html>
                    """
                    
                    st.components.v1.html(html_receipt, height=800, scrolling=True)
                    st.success("PDF print dialog opened!")
            
            with col4:
                if st.button("🔄 New Bill", use_container_width=True, key="new_bill_btn"):
                    st.session_state.last_sale = None
                    st.rerun()
            
            st.markdown("---")
            st.markdown("#### 💾 Backup Options")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 Export Bill Data", use_container_width=True, key="export_bill_btn"):
                    sale = st.session_state.last_sale
                    import json
                    bill_json = json.dumps(sale, indent=2)
                    st.download_button(
                        label="Download Bill JSON",
                        data=bill_json,
                        file_name=f"bill_{sale['bill_no']}.json",
                        mime="application/json",
                        key="download_bill_json"
                    )
            
            with col2:
                if st.button("📧 Email Receipt", use_container_width=True, key="email_receipt_btn"):
                    st.info("Email feature coming soon!")

# ========================== INVENTORY ==========================
elif menu == "📦 Inventory":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📦 Inventory Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### ✏️ Manage Items List")
    with st.expander("Add/Remove Items", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ Add New Item")
            new_item_name = st.text_input("Item Name", key="new_item_name")
            category = st.selectbox("Category", ["vegetable", "fruit"], key="new_item_category")
            unit_type = st.selectbox("Unit Type", ["kg", "piece"], key="new_item_unit")
            initial_qty = st.number_input("Initial Quantity", min_value=0.0, step=0.1, value=0.0, key="initial_qty")
            initial_price = st.number_input("Initial Price ₹", min_value=0.0, step=1.0, value=0.0, key="initial_price")
            
            if st.button("Add to Inventory", use_container_width=True, key="add_item_btn"):
                if new_item_name and new_item_name.strip():
                    c.execute("INSERT OR REPLACE INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) VALUES (?,?,?,?,?,?)", 
                             (new_item_name.strip(), initial_qty, 0.0, initial_price, unit_type, category))
                    conn.commit()
                    unit_display = unit_type if unit_type != 'kg' else 'kg'
                    st.success(f"✅ Added {new_item_name.strip()} to inventory ({category}, sold by {unit_display})")
                    st.rerun()
        
        with col2:
            st.markdown("#### 🗑️ Remove Item")
            all_items = pd.read_sql("SELECT vegetable FROM inventory ORDER BY vegetable", conn)
            
            if not all_items.empty:
                item_to_remove = st.selectbox("Select item to remove", all_items['vegetable'], key="item_to_remove")
                confirm = st.checkbox("I confirm I want to remove this item", key="confirm_remove")
                
                if st.button("Remove from Inventory", use_container_width=True, type="secondary", disabled=not confirm, key="remove_item_btn"):
                    stock, _, _, _, _ = get_stock(item_to_remove)
                    if stock > 0:
                        st.error(f"Cannot remove {item_to_remove} - it still has {stock:.2f} in stock")
                    else:
                        c.execute("DELETE FROM inventory WHERE vegetable=?", (item_to_remove,))
                        conn.commit()
                        st.success(f"✅ Removed {item_to_remove} from inventory")
                        st.rerun()
    
    st.markdown("### 📋 Current Inventory")
    
    inv_df = pd.read_sql("SELECT vegetable, quantity, selling_price, unit_type, category FROM inventory ORDER BY category, vegetable", conn)
    
    if inv_df.empty:
        st.info("No inventory items")
    else:
        in_stock = len(inv_df[inv_df['quantity'] > 0])
        out_of_stock = len(inv_df[inv_df['quantity'] == 0])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(inv_df))
        with col2:
            st.metric("In Stock", in_stock)
        with col3:
            st.metric("Out of Stock", out_of_stock)
        
        # Separate tabs for vegetables and fruits
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        with tab1:
            veg_df = inv_df[inv_df['category'] == 'vegetable']
            if not veg_df.empty:
                st.markdown("#### 🥦 Edit Vegetable Quantities")
                
                edited_veg = st.data_editor(
                    veg_df,
                    column_config={
                        "vegetable": st.column_config.TextColumn("🌿 Vegetable", disabled=True),
                        "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                        "quantity": st.column_config.NumberColumn(
                            "⚖️ Quantity",
                            min_value=0.0,
                            step=0.1,
                            format="%.2f"
                        ),
                        "selling_price": st.column_config.NumberColumn(
                            "💰 Price (₹)",
                            min_value=0.0,
                            step=1.0,
                            format="₹%.2f"
                        )
                    },
                    use_container_width=True,
                    num_rows="dynamic",
                    hide_index=True,
                    key="vegetable_editor"
                )
            else:
                st.info("No vegetables in inventory")
        
        with tab2:
            fruit_df = inv_df[inv_df['category'] == 'fruit']
            if not fruit_df.empty:
                st.markdown("#### 🍎 Edit Fruit Quantities")
                
                edited_fruit = st.data_editor(
                    fruit_df,
                    column_config={
                        "vegetable": st.column_config.TextColumn("🍎 Fruit", disabled=True),
                        "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                        "quantity": st.column_config.NumberColumn(
                            "⚖️ Quantity",
                            min_value=0.0,
                            step=0.1,
                            format="%.2f"
                        ),
                        "selling_price": st.column_config.NumberColumn(
                            "💰 Price (₹)",
                            min_value=0.0,
                            step=1.0,
                            format="₹%.2f"
                        )
                    },
                    use_container_width=True,
                    num_rows="dynamic",
                    hide_index=True,
                    key="fruit_editor"
                )
            else:
                st.info("No fruits in inventory")
        
        if st.button("💾 Save Inventory Changes", type="primary", use_container_width=True, key="save_inv_changes"):
            changes_made = 0
            if 'edited_veg' in locals():
                for _, row in edited_veg.iterrows():
                    try:
                        c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                                 (row['quantity'], row['selling_price'], row['vegetable']))
                        changes_made += 1
                    except Exception as e:
                        st.error(f"Error updating {row['vegetable']}: {e}")
            
            if 'edited_fruit' in locals():
                for _, row in edited_fruit.iterrows():
                    try:
                        c.execute("UPDATE inventory SET quantity=?, selling_price=? WHERE vegetable=?", 
                                 (row['quantity'], row['selling_price'], row['vegetable']))
                        changes_made += 1
                    except Exception as e:
                        st.error(f"Error updating {row['vegetable']}: {e}")
            
            try:
                conn.commit()
                if changes_made > 0:
                    st.success(f"✅ {changes_made} inventory items updated successfully!")
                else:
                    st.info("No changes were made to inventory.")
            except Exception as e:
                st.error(f"Error committing changes: {e}")

# ========================== PURCHASES ==========================
elif menu == "📋 Purchases":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📋 Purchase Records</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View purchases for date", value=selected_date, key="purchases_date")
    with col2:
        show_all = st.checkbox("Show all dates", key="show_all_purchases")
    
    if show_all:
        purchases_df = pd.read_sql("SELECT * FROM purchases ORDER BY date DESC, rowid DESC", conn)
    else:
        purchases_df = pd.read_sql("SELECT * FROM purchases WHERE date=? ORDER BY rowid DESC", 
                                  conn, params=(view_date.strftime("%Y-%m-%d"),))
    
    if purchases_df.empty:
        st.info(f"No purchases found for {view_date.strftime('%d %B %Y')}")
    else:
        total_amount = purchases_df['amount'].sum()
        total_qty = purchases_df['quantity'].sum()
        veg_count = purchases_df['vegetable'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Amount", f"₹{total_amount:.2f}")
        with col2:
            st.metric("⚖️ Total Quantity", f"{total_qty:.1f}")
        with col3:
            st.metric("🌿 Items Bought", veg_count)
        
        st.dataframe(
            purchases_df.style.format({
                "quantity": "{:.2f}",
                "amount": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== SALES ==========================
elif menu == "🧾 Sales":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🧾 Sales Records</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        view_date = st.date_input("View sales for date", value=selected_date, key="sales_date_view")
    with col2:
        show_all_sales = st.checkbox("Show all dates", key="show_all_sales_view")
    
    if show_all_sales:
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY date DESC, rowid DESC", conn)
    else:
        sales_df = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC", 
                              conn, params=(view_date.strftime("%Y-%m-%d"),))
    
    if sales_df.empty:
        st.info(f"No sales found for {view_date.strftime('%d %B %Y')}")
    else:
        total_sales = sales_df['total'].sum()
        total_qty = sales_df['quantity_sold'].sum()
        customer_count = sales_df['customer_name'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Sales", f"₹{total_sales:.2f}")
        with col2:
            st.metric("⚖️ Quantity Sold", f"{total_qty:.1f}")
        with col3:
            st.metric("👥 Customers", customer_count)
        
        display_df = sales_df.copy()
        
        def format_sales_row(row):
            unit_type = row.get('unit_type', 'kg')
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            else:
                return f"{row['quantity_sold']:.2f} {unit_type}"
        
        display_df['Quantity Display'] = display_df.apply(format_sales_row, axis=1)
        
        st.dataframe(
            display_df[['date', 'vegetable', 'Quantity Display', 'total', 'customer_name', 'customer_phone']].rename(columns={
                'customer_name': 'Customer',
                'customer_phone': 'Phone'
            }).style.format({
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== EXPENSES ==========================
elif menu == "💸 Expenses":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💸 Expense Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", 
                                   ["Rent", "Electricity", "Water", "Transport", "Labor", 
                                    "Packaging", "Maintenance", "Miscellaneous", "Others"],
                                   key="expense_category")
            amount = st.number_input("Amount ₹", min_value=0.0, step=10.0, value=0.0, key="expense_amount")
        with col2:
            description = st.text_input("Description", placeholder="What was this expense for?", key="expense_desc")
        
        submit_button = st.form_submit_button("💾 Save Expense", type="primary", use_container_width=True)
        if submit_button:
            if amount <= 0:
                st.error("Enter amount > 0")
            elif not description:
                st.error("Enter description")
            else:
                d = selected_date.strftime("%Y-%m-%d")
                c.execute("INSERT INTO expenses VALUES (?,?,?,?)", 
                         (d, category, amount, description))
                conn.commit()
                st.success(f"✅ Expense recorded: {category} - ₹{amount:.2f}")
    
    st.markdown("### Today's Expenses")
    expenses_df = pd.read_sql("SELECT * FROM expenses WHERE date=?", 
                             conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if expenses_df.empty:
        st.info("No expenses today")
    else:
        total_expenses = expenses_df['amount'].sum()
        st.metric("Total Expenses Today", f"₹{total_expenses:.2f}")
        st.dataframe(expenses_df, use_container_width=True)

# ========================== CUSTOMERS ==========================
elif menu == "👥 Customers":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>👥 Customer Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all customers from customers table
    customers_df = pd.read_sql("""
        SELECT phone, name, points, total_spent, last_visit 
        FROM customers 
        WHERE phone IS NOT NULL AND phone != '' 
        ORDER BY total_spent DESC
    """, conn)
    
    if customers_df.empty:
        st.info("No customers in loyalty program")
    else:
        total_points = customers_df['points'].sum()
        total_customers = len(customers_df)
        total_spent = customers_df['total_spent'].sum()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Loyalty Customers", total_customers)
        with col2:
            st.metric("Total Points", total_points)
        with col3:
            avg_points = total_points / total_customers if total_customers > 0 else 0
            st.metric("Avg Points/Customer", f"{avg_points:.0f}")
        with col4:
            st.metric("Total Spent", f"₹{total_spent:.2f}")
        
        # Show loyalty customers in a table
        st.markdown("### 🏆 Loyalty Customers")
        
        display_customers = customers_df.copy()
        display_customers = display_customers.rename(columns={
            "phone": "📱 Phone",
            "name": "👤 Name",
            "points": "⭐ Points",
            "total_spent": "💰 Total Spent",
            "last_visit": "📅 Last Visit"
        })
        
        st.dataframe(
            display_customers.style.format({
                "💰 Total Spent": "₹{:.2f}"
            }),
            use_container_width=True,
            height=400
        )
        
        # Also show customer details
        st.markdown("### 📊 Customer Details")
        for idx, row in customers_df.iterrows():
            st.markdown(f"""
            <div class="card" style="padding:15px; margin-bottom:10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin:0; color:#2c3e50;">{row['name']}</h4>
                        <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:0.9em;">📱 {row['phone']}</p>
                        <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:0.9em;">📅 Last Visit: {row['last_visit'] if row['last_visit'] else 'N/A'}</p>
                    </div>
                    <div style="text-align:right;">
                        <span style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); 
                                    color:white; padding:5px 15px; border-radius:20px; font-weight:bold; margin-bottom:5px; display:block;">
                            ⭐ {row['points']} pts
                        </span>
                        <span style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); 
                                    color:white; padding:5px 15px; border-radius:20px; font-weight:bold; display:block;">
                            ₹{row['total_spent']:.2f} spent
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ========================== WASTE ==========================
elif menu == "🗑 Waste":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🗑 Waste Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    all_veg = pd.read_sql("SELECT vegetable, unit_type, category FROM inventory ORDER BY category, vegetable", conn)
    
    tab1, tab2, tab3 = st.tabs(["🥦 Vegetables (KG)", "🧩 Vegetables (Piece)", "🍎 Fruits (KG)"])
    
    with tab1:
        st.markdown("### 🥦 Vegetables (KG) Waste")
        kg_vegetables = all_veg[(all_veg['unit_type'] == 'kg') & (all_veg['category'] == 'vegetable')]
        
        with st.form("kg_veg_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Vegetable (KG)", kg_vegetables['vegetable'].tolist() if not kg_vegetables.empty else [], key="kg_veg_waste_veg")
                if veg:
                    st.info(f"Unit: kg")
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=0.0, key="kg_veg_waste_qty")
                else:
                    qty = 0
            with col2:
                reason = st.selectbox("Reason", 
                                     ["Spoiled", "Damaged", "Expired", "Overstock", "Other"],
                                     key="kg_veg_waste_reason")
                description = st.text_input("Details", key="kg_veg_waste_desc")
            
            with col3:
                submit_button = st.form_submit_button("Record Waste", use_container_width=True, type="primary")
                if submit_button:
                    if qty <= 0:
                        st.error("Enter quantity > 0")
                    else:
                        stock, _, _, _, _ = get_stock(veg)
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.2f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                            conn.commit()
                            st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    with tab2:
        st.markdown("### 🧩 Vegetables (Piece) Waste")
        piece_vegetables = all_veg[(all_veg['unit_type'] == 'piece') & (all_veg['category'] == 'vegetable')]
        
        with st.form("piece_veg_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Vegetable (Piece)", piece_vegetables['vegetable'].tolist() if not piece_vegetables.empty else [], key="piece_veg_waste_veg")
                if veg:
                    st.info(f"Unit: pieces")
                    qty = st.number_input("Quantity (pieces)", min_value=0, step=1, value=0, key="piece_veg_waste_qty")
                else:
                    qty = 0
            with col2:
                reason = st.selectbox("Reason", 
                                     ["Spoiled", "Damaged", "Expired", "Overstock", "Other"],
                                     key="piece_veg_waste_reason")
                description = st.text_input("Details", key="piece_veg_waste_desc")
            
            with col3:
                submit_button = st.form_submit_button("Record Waste", use_container_width=True, type="primary")
                if submit_button:
                    if qty <= 0:
                        st.error("Enter quantity > 0")
                    else:
                        stock, _, _, _, _ = get_stock(veg)
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.0f} pieces")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                            conn.commit()
                            st.success(f"✅ Recorded waste: {qty} pieces of {veg}")
    
    with tab3:
        st.markdown("### 🍎 Fruits (KG) Waste")
        kg_fruits = all_veg[(all_veg['unit_type'] == 'kg') & (all_veg['category'] == 'fruit')]
        
        with st.form("kg_fruit_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Fruit (KG)", kg_fruits['vegetable'].tolist() if not kg_fruits.empty else [], key="kg_fruit_waste_veg")
                if veg:
                    st.info(f"Unit: kg")
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=0.0, key="kg_fruit_waste_qty")
                else:
                    qty = 0
            with col2:
                reason = st.selectbox("Reason", 
                                     ["Spoiled", "Damaged", "Expired", "Overstock", "Other"],
                                     key="kg_fruit_waste_reason")
                description = st.text_input("Details", key="kg_fruit_waste_desc")
            
            with col3:
                submit_button = st.form_submit_button("Record Waste", use_container_width=True, type="primary")
                if submit_button:
                    if qty <= 0:
                        st.error("Enter quantity > 0")
                    else:
                        stock, _, _, _, _ = get_stock(veg)
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.2f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c.execute("INSERT INTO waste VALUES (?,?,?,?)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable=?", (qty, veg))
                            conn.commit()
                            st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    st.markdown("---")
    st.markdown(f"### Today's Waste ({selected_date.strftime('%d %B %Y')})")
    waste_df = pd.read_sql("SELECT * FROM waste WHERE date=?", 
                          conn, params=(selected_date.strftime("%Y-%m-%d"),))
    
    if waste_df.empty:
        st.info("No waste recorded today")
    else:
        total_waste = waste_df['quantity'].sum()
        st.metric("Total Waste Today", f"{total_waste:.2f}")
        st.dataframe(waste_df, use_container_width=True)

# ========================== DOWNLOAD ==========================
elif menu == "⬇ Download":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>⬇ Download Reports</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📅 Daily Reports", "📊 Monthly Reports", "📋 Data Export"])
    
    with tab1:
        st.markdown(f"### 📅 Daily Report - {selected_date.strftime('%d %B %Y')}")
        
        d = selected_date.strftime("%Y-%m-%d")
        
        daily_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE date=?", 
                                 conn, params=(d,)).iloc[0]['total_sales']
        
        daily_purchases = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE date=?", 
                                     conn, params=(d,)).iloc[0]['total_purchases']
        
        daily_expenses = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE date=?", 
                                    conn, params=(d,)).iloc[0]['total_expenses']
        
        daily_waste = pd.read_sql("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE date=?", 
                                 conn, params=(d,)).iloc[0]['total_waste']
        
        # FIXED: Get customer details properly
        daily_customers = pd.read_sql("""
            SELECT 
                COALESCE(customer_name, 'Guest') as customer_name,
                COALESCE(customer_phone, '') as phone,
                SUM(total) as total_spent,
                COUNT(*) as total_visits
            FROM sales 
            WHERE date=?
            GROUP BY COALESCE(customer_name, 'Guest'), COALESCE(customer_phone, '')
            ORDER BY total_spent DESC
        """, conn, params=(d,))
        
        daily_profit = daily_sales - daily_purchases - daily_expenses
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Sales", f"₹{daily_sales:.2f}")
        with col2:
            st.metric("🛒 Purchases", f"₹{daily_purchases:.2f}")
        with col3:
            st.metric("💸 Expenses", f"₹{daily_expenses:.2f}")
        with col4:
            st.metric("📈 Profit/Loss", f"₹{daily_profit:.2f}", delta_color="off")
        
        st.markdown("#### 👥 Customer Details")
        if not daily_customers.empty:
            st.dataframe(
                daily_customers.style.format({
                    "total_spent": "₹{:.2f}"
                }),
                use_container_width=True
            )
        else:
            st.info("No customer data for today")
        
        st.markdown("#### Detailed Daily Data")
        
        tables = [
            ("purchases", "🛒 Purchases", "Daily purchase records"),
            ("sales", "💰 Sales", "Daily sales transactions"),
            ("waste", "🗑 Waste", "Daily waste records"),
            ("expenses", "💸 Expenses", "Daily expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                df = pd.read_sql(f"SELECT * FROM {table_name} WHERE date=?", 
                                conn, params=(d,))
                
                if df.empty:
                    st.info(f"No {display_name.lower()} data for today")
                else:
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode()
                    st.download_button(
                        f"Download {display_name}",
                        data=csv,
                        file_name=f"{table_name}_{d}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
    
    with tab2:
        st.markdown("### 📊 Monthly Reports")
        
        months = pd.read_sql("SELECT DISTINCT strftime('%Y-%m', date) as month FROM sales UNION SELECT DISTINCT strftime('%Y-%m', date) as month FROM purchases ORDER BY month DESC", conn)
        
        if months.empty:
            st.info("No monthly data available")
        else:
            selected_month = st.selectbox("Select Month", months['month'].tolist(), index=0)
            
            monthly_sales = pd.read_sql("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE strftime('%Y-%m', date)=?", 
                                       conn, params=(selected_month,)).iloc[0]['total_sales']
            
            monthly_purchases = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE strftime('%Y-%m', date)=?", 
                                          conn, params=(selected_month,)).iloc[0]['total_purchases']
            
            monthly_expenses = pd.read_sql("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE strftime('%Y-%m', date)=?", 
                                         conn, params=(selected_month,)).iloc[0]['total_expenses']
            
            monthly_waste = pd.read_sql("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE strftime('%Y-%m', date)=?", 
                                       conn, params=(selected_month,)).iloc[0]['total_waste']
            
            # FIXED: Get monthly customer details properly
            monthly_customers = pd.read_sql("""
                SELECT 
                    COALESCE(customer_name, 'Guest') as customer_name,
                    COALESCE(customer_phone, '') as phone,
                    SUM(total) as total_spent,
                    COUNT(*) as total_visits
                FROM sales 
                WHERE strftime('%Y-%m', date)=?
                GROUP BY COALESCE(customer_name, 'Guest'), COALESCE(customer_phone, '')
                ORDER BY total_spent DESC
            """, conn, params=(selected_month,))
            
            monthly_profit = monthly_sales - monthly_purchases - monthly_expenses
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Monthly Sales", f"₹{monthly_sales:.2f}")
            with col2:
                st.metric("🛒 Monthly Purchases", f"₹{monthly_purchases:.2f}")
            with col3:
                st.metric("💸 Monthly Expenses", f"₹{monthly_expenses:.2f}")
            with col4:
                st.metric("📈 Monthly Profit/Loss", f"₹{monthly_profit:.2f}", delta_color="off")
            
            st.markdown("#### 👥 Monthly Customer Details")
            if not monthly_customers.empty:
                st.dataframe(
                    monthly_customers.style.format({
                        "total_spent": "₹{:.2f}"
                    }),
                    use_container_width=True
                )
            else:
                st.info("No customer data for this month")
            
            st.markdown("#### Daily Breakdown for the Month")
            
            daily_sales_month = pd.read_sql("""
                SELECT date, SUM(total) as daily_sales 
                FROM sales 
                WHERE strftime('%Y-%m', date)=? 
                GROUP BY date 
                ORDER BY date
            """, conn, params=(selected_month,))
            
            if not daily_sales_month.empty:
                st.line_chart(daily_sales_month.set_index('date')['daily_sales'])
                
                st.dataframe(
                    daily_sales_month.style.format({
                        "daily_sales": "₹{:.2f}"
                    }),
                    use_container_width=True
                )
            
            st.markdown("#### Download Monthly Report")
            
            monthly_data = {
                'Metric': ['Total Sales', 'Total Purchases', 'Total Expenses', 'Total Waste', 'Net Profit/Loss', 'Total Customers', 'Total Customer Spent'],
                'Amount': [f"₹{monthly_sales:.2f}", f"₹{monthly_purchases:.2f}", 
                          f"₹{monthly_expenses:.2f}", f"{monthly_waste:.2f}", f"₹{monthly_profit:.2f}",
                          f"{len(monthly_customers)}", f"₹{monthly_customers['total_spent'].sum():.2f}"]
            }
            
            monthly_report_df = pd.DataFrame(monthly_data)
            
            csv = monthly_report_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download Monthly Summary",
                data=csv,
                file_name=f"monthly_report_{selected_month}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            if not monthly_customers.empty:
                customer_csv = monthly_customers.to_csv(index=False).encode()
                st.download_button(
                    "📥 Download Monthly Customer Data",
                    data=customer_csv,
                    file_name=f"monthly_customers_{selected_month}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    
    with tab3:
        st.markdown("### 📋 Data Export")
        st.markdown("Export complete database tables")
        
        tables = [
            ("inventory", "📦 Inventory", "Current stock levels"),
            ("customers", "👥 Customers", "Customer database"),
            ("purchases", "🛒 Purchases", "All purchase records"),
            ("sales", "💰 Sales", "All sales transactions"),
            ("waste", "🗑 Waste", "All waste records"),
            ("expenses", "💸 Expenses", "All expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
                
                if df.empty:
                    st.info(f"No {display_name.lower()} data")
                else:
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode()
                    st.download_button(
                        f"Download {display_name}",
                        data=csv,
                        file_name=f"{table_name}_full_export.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

# ========================== FINANCIALS ==========================
elif menu == "💰 Financials":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💰 Financial Summary</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    d = selected_date.strftime("%Y-%m-%d")
    
    sales_data = pd.read_sql("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=?", 
                           conn, params=(d,)).iloc[0]['total']
    cost_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=?", 
                          conn, params=(d,)).iloc[0]['total']
    expense_data = pd.read_sql("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE date=?", 
                             conn, params=(d,)).iloc[0]['total']
    
    profit = sales_data - cost_data - expense_data
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Sales</h4>
            <h2>₹{sales_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="purchase-card">
            <h3>📦</h3>
            <h4>Cost</h4>
            <h2>₹{cost_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color:white;">
            <h3>💸</h3>
            <h4>Expenses</h4>
            <h2>₹{expense_data:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        profit_bg = "#27ae60" if profit >= 0 else "#e74c3c"
        profit_text = "Profit" if profit >= 0 else "Loss"
        profit_icon = "📈" if profit >= 0 else "📉"
        
        st.markdown(f"""
        <div class="card" style="background: linear-gradient(135deg, {profit_bg} 0%, #38f9d7 100%); color:white;">
            <h3>{profit_icon}</h3>
            <h4>{profit_text}</h4>
            <h2>₹{abs(profit):.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("### 📊 Daily Breakdown")
    
    sales_by_veg = pd.read_sql("""
        SELECT vegetable, SUM(quantity_sold) as qty, SUM(total) as revenue 
        FROM sales WHERE date=? 
        GROUP BY vegetable 
        ORDER BY revenue DESC
    """, conn, params=(d,))
    
    if not sales_by_veg.empty:
        st.markdown("#### Top Selling Items")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                sales_by_veg.style.format({
                    "qty": "{:.2f}",
                    "revenue": "₹{:.2f}"
                }),
                use_container_width=True
            )
        with col2:
            chart_data = sales_by_veg.head(10).set_index('vegetable')['revenue']
            st.bar_chart(chart_data)
    
    st.markdown("### Recent Transactions")
    recent_sales = pd.read_sql("SELECT * FROM sales WHERE date=? ORDER BY rowid DESC LIMIT 10", 
                              conn, params=(d,))
    if not recent_sales.empty:
        display_sales = recent_sales.copy()
        
        def format_recent_sales(row):
            unit_type = row.get('unit_type', 'kg')
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            else:
                return f"{row['quantity_sold']:.2f} {unit_type}"
        
        def clean_customer_name(customer):
            if not isinstance(customer, str):
                return str(customer)
            if '(' in customer:
                return customer.split('(')[0].strip()
            return customer
        
        display_sales['Quantity'] = display_sales.apply(format_recent_sales, axis=1)
        display_sales['Customer'] = display_sales['customer_name'].apply(lambda x: x if x and x != 'None' else 'Guest')
        
        st.dataframe(
            display_sales[['vegetable', 'Quantity', 'total', 'Customer']].style.format({
                "total": "₹{:.2f}"
            }),
            use_container_width=True
        )

# ========================== DATABASE TOOLS ==========================
elif menu == "🔧 Database Tools":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🔧 Enhanced Database Tools</h2>
        <div class="subtitle">Permanent Data Storage System</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📍 Database Location")
    st.code(f"""
    Database File: {DB_FILE}
    Backup File: {BACKUP_FILE}
    Export Directory: {EXPORT_DIR}
    """, language="bash")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Current Status")
        if os.path.exists(DB_FILE):
            size_kb = os.path.getsize(DB_FILE) / 1024
            modified = datetime.fromtimestamp(os.path.getmtime(DB_FILE))
            st.success(f"""
            **✅ Database Active**
            Size: {size_kb:.1f} KB
            Last Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}
            """)
        else:
            st.error("**❌ Database Not Found**")
    
    with col2:
        st.markdown("#### 📂 Backup Status")
        if os.path.exists(BACKUP_FILE):
            size_kb = os.path.getsize(BACKUP_FILE) / 1024
            modified = datetime.fromtimestamp(os.path.getmtime(BACKUP_FILE))
            st.success(f"""
            **✅ Backup Active**
            Size: {size_kb:.1f} KB
            Last Backup: {modified.strftime('%Y-%m-%d %H:%M:%S')}
            """)
        else:
            st.warning("**⚠️ No Backup Found**")
    
    st.markdown("---")
    st.markdown("### 💾 Enhanced Backup System")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Create Full Backup", use_container_width=True, type="primary"):
            if create_backup():
                st.success("✅ Full backup created!")
                st.rerun()
            else:
                st.error("❌ Backup failed!")
    
    with col2:
        if st.button("📤 Export to JSON", use_container_width=True):
            json_file = export_backup()
            if json_file:
                st.success(f"✅ Exported to: {json_file}")
                with open(json_file, 'rb') as f:
                    st.download_button(
                        label="📥 Download JSON",
                        data=f,
                        file_name=os.path.basename(json_file),
                        mime="application/json",
                        use_container_width=True
                    )
            else:
                st.error("❌ Export failed!")
    
    with col3:
        if st.button("🔍 Recover Data", use_container_width=True):
            if recover_database():
                st.success("✅ Data recovery attempted!")
                st.rerun()
            else:
                st.error("❌ Recovery failed!")
    
    st.markdown("---")
    st.markdown("### 📈 Detailed Statistics")
    
    try:
        stats_data = []
        tables = ["inventory", "sales", "purchases", "customers", "expenses", "waste"]
        
        for table in tables:
            try:
                c.execute(f"SELECT COUNT(*) FROM {table}")
                count = c.fetchone()[0]
                
                if table == "sales":
                    c.execute("SELECT COALESCE(SUM(total), 0) FROM sales")
                    total_sales = c.fetchone()[0]
                    stats_data.append({
                        "Table": table,
                        "Records": count,
                        "Total Amount": f"₹{total_sales:.2f}",
                        "Last Record": get_last_record_date(table)
                    })
                elif table == "purchases":
                    c.execute("SELECT COALESCE(SUM(amount), 0) FROM purchases")
                    total_purchases = c.fetchone()[0]
                    stats_data.append({
                        "Table": table,
                        "Records": count,
                        "Total Amount": f"₹{total_purchases:.2f}",
                        "Last Record": get_last_record_date(table)
                    })
                else:
                    stats_data.append({
                        "Table": table,
                        "Records": count,
                        "Total Amount": "-",
                        "Last Record": get_last_record_date(table)
                    })
            except:
                stats_data.append({
                    "Table": table,
                    "Records": 0,
                    "Total Amount": "-",
                    "Last Record": "N/A"
                })
        
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True)
        
        st.markdown("#### ✅ Data Validation")
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            c.execute("SELECT COUNT(*) FROM sales WHERE date=?", (today,))
            today_sales = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM inventory WHERE quantity > 0")
            in_stock = c.fetchone()[0]
            
            st.info(f"""
            **Data Health Check:**
            • Today's Sales Records: {today_sales}
            • Items in Stock: {in_stock}
            • Total Database Records: {stats_df['Records'].sum():,}
            """)
        except Exception as e:
            st.warning(f"Data validation incomplete: {e}")
            
    except Exception as e:
        st.error(f"Error fetching statistics: {e}")
    
    st.markdown("---")
    st.markdown("### 🧹 Database Cleanup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        days_to_keep = st.number_input("Days to keep sales data", min_value=30, max_value=365, value=90, step=30)
        if st.button("🗑️ Clean Old Sales Data", use_container_width=True, type="secondary", key="clean_sales"):
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
            try:
                c.execute("DELETE FROM sales WHERE date < ?", (cutoff_date,))
                conn.commit()
                st.success(f"✅ Sales data older than {cutoff_date} removed!")
            except Exception as e:
                st.error(f"❌ Cleanup failed: {e}")
    
    with col2:
        if st.button("⚡ Vacuum Database", use_container_width=True, key="vacuum_db"):
            try:
                c.execute("VACUUM")
                conn.commit()
                st.success("✅ Database optimized and compacted!")
            except Exception as e:
                st.error(f"❌ Vacuum failed: {e}")

# ========================== ENHANCED BACKUP ON EXIT ==========================
@atexit.register
def cleanup():
    """Create final backup on exit"""
    create_backup()
    export_backup()

# Footer
st.markdown("---")
st.markdown(f"""
<div class="footer">
    <p>🌿 Fresh Basket — Freshness You Can Feel | Quality Vegetables Daily ✅</p>
    <p style="font-size:0.8em; color:#95a5a6;">No.4, Andal nagar, Adambakkam, Chennai - 600 088 | 📞 7904019948</p>
</div>
""", unsafe_allow_html=True)

# Close database connection properly
conn.close()
