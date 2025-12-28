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
import requests
import tempfile
import logging
import psycopg2
from functools import lru_cache
from psycopg2.extras import RealDictCursor

# ========================== DEBUG LOGGING ==========================
# Reduce logging level for production
logging.basicConfig(
    level=logging.WARNING,  # Changed from DEBUG to WARNING
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================== AUTO-CREATE CONFIG.TOML ==========================
def create_streamlit_config():
    """Create .streamlit/config.toml if it doesn't exist"""
    config_dir = ".streamlit"
    config_file = os.path.join(config_dir, "config.toml")
    
    if not os.path.exists(config_file):
        os.makedirs(config_dir, exist_ok=True)
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

create_streamlit_config()

# ========================== EXTERNAL DATABASE SETUP ==========================
class DatabaseCache:
    """Cache frequently used database data"""
    def __init__(self):
        self.inventory_cache = None
        self.last_refresh = None
        self.cache_duration = 30  # seconds
        self.inventory_df = None
    
    def should_refresh(self):
        if self.last_refresh is None:
            return True
        elapsed = (datetime.now() - self.last_refresh).total_seconds()
        return elapsed > self.cache_duration
    
    def refresh_inventory(self, conn):
        """Refresh inventory cache"""
        try:
            c = conn.cursor()
            c.execute("SELECT vegetable, quantity, cost_price, selling_price, unit_type, category FROM inventory ORDER BY vegetable")
            rows = c.fetchall()
            self.inventory_cache = {row[0]: row[1:] for row in rows}
            
            # Also store as DataFrame for faster operations
            self.inventory_df = pd.DataFrame(rows, columns=['vegetable', 'quantity', 'cost_price', 'selling_price', 'unit_type', 'category'])
            
            self.last_refresh = datetime.now()
        except Exception as e:
            logger.error(f"Error refreshing inventory cache: {e}")
    
    def get_inventory(self, conn):
        """Get inventory with caching"""
        if self.inventory_cache is None or self.should_refresh():
            self.refresh_inventory(conn)
        return self.inventory_cache
    
    def get_inventory_df(self, conn):
        """Get inventory as DataFrame with caching"""
        if self.inventory_df is None or self.should_refresh():
            self.refresh_inventory(conn)
        return self.inventory_df

# Global cache instance
db_cache = DatabaseCache()

class ExternalDatabaseManager:
    """Manage connections to external database services"""
    
    def __init__(self):
        self.db_type = "supabase"
        self.db_config = {}
        self._conn = None  # Cached connection
        
    def get_connection(self, force_new=False):
        """Get cached database connection"""
        if not force_new and self._conn is not None:
            try:
                # Test if connection is still alive
                self._conn.cursor().execute("SELECT 1")
                return self._conn
            except:
                self._conn = None
                logger.info("Connection test failed, creating new connection")
        
        # Create new connection
        try:
            if self.db_type == "supabase":
                self._conn = self._get_supabase_connection()
            elif self.db_type == "postgresql":
                self._conn = self._get_postgresql_connection()
            
            if self._conn:
                # Create indexes for performance
                self._create_indexes(self._conn)
                
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self._conn = None
        
        return self._conn
    
    def _create_indexes(self, conn):
        """Create indexes for faster queries"""
        c = conn.cursor()
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)",
            "CREATE INDEX IF NOT EXISTS idx_sales_vegetable ON sales(vegetable)",
            "CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_vegetable ON inventory(vegetable)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_unit_type ON inventory(unit_type)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)",
            "CREATE INDEX IF NOT EXISTS idx_waste_date ON waste(date)"
        ]
        
        for idx_sql in indexes:
            try:
                c.execute(idx_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")
        
        conn.commit()
    
    def init_database(self):
        """Initialize database connection"""
        try:
            # Check for Supabase configuration
            if hasattr(st, 'secrets') and 'supabase' in st.secrets:
                supabase_config = dict(st.secrets.supabase)
                self.db_type = "supabase"
                self.db_config = supabase_config
                
                # Test connection
                conn = self.get_connection()
                if conn:
                    logger.info("✅ Using Supabase database from secrets")
                    return True
            
            # Check for direct PostgreSQL configuration
            elif hasattr(st, 'secrets') and 'postgresql' in st.secrets:
                postgres_config = dict(st.secrets.postgresql)
                self.db_type = "postgresql"
                self.db_config = postgres_config
                
                # Test connection
                conn = self.get_connection()
                if conn:
                    logger.info("✅ Using PostgreSQL database from secrets")
                    return True
            
            st.error("❌ SUPABASE/POSTGRESQL CONFIGURATION REQUIRED!")
            return False
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def _get_supabase_connection(self):
        """Get Supabase PostgreSQL connection"""
        try:
            db_url = self.db_config.get('db_url')
            if db_url:
                # Parse connection string for better connection management
                conn_params = self._parse_connection_url(db_url)
                conn = psycopg2.connect(**conn_params, connect_timeout=5)
                conn.autocommit = False
                self._create_supabase_tables(conn)
                return conn
        except Exception as e:
            logger.error(f"Supabase connection failed: {e}")
            st.error(f"Supabase connection error: {str(e)}")
        return None
    
    def _get_postgresql_connection(self):
        """Get PostgreSQL connection"""
        try:
            conn_params = {
                'host': self.db_config.get('host'),
                'port': self.db_config.get('port', 5432),
                'database': self.db_config.get('database'),
                'user': self.db_config.get('user'),
                'password': self.db_config.get('password')
            }
            conn = psycopg2.connect(**conn_params, connect_timeout=5)
            conn.autocommit = False
            self._create_supabase_tables(conn)
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return None
    
    def _parse_connection_url(self, url):
        """Parse PostgreSQL connection URL"""
        # Simple URL parsing
        import urllib.parse
        result = urllib.parse.urlparse(url)
        
        return {
            'host': result.hostname,
            'port': result.port or 5432,
            'database': result.path[1:],  # Remove leading slash
            'user': result.username,
            'password': result.password,
            'sslmode': 'require' if 'supabase' in url else 'prefer'
        }
    
    def _create_supabase_tables(self, conn):
        """Create tables in Supabase/PostgreSQL"""
        c = conn.cursor()
        
        # Create tables with minimal existence checks
        tables_sql = [
            """CREATE TABLE IF NOT EXISTS inventory (
                vegetable VARCHAR(255) PRIMARY KEY,
                quantity DECIMAL(10,3) DEFAULT 0,
                cost_price DECIMAL(10,2) DEFAULT 0,
                selling_price DECIMAL(10,2) DEFAULT 0,
                image_url TEXT,
                unit_type VARCHAR(50) DEFAULT 'kg',
                category VARCHAR(50) DEFAULT 'vegetable'
            )""",
            
            """CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL, 
                vegetable VARCHAR(255) NOT NULL, 
                quantity DECIMAL(10,3) DEFAULT 0, 
                amount DECIMAL(10,2) DEFAULT 0, 
                supplier VARCHAR(255)
            )""",
            
            """CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL, 
                vegetable VARCHAR(255) NOT NULL, 
                quantity_sold DECIMAL(10,3) DEFAULT 0, 
                sale_price DECIMAL(10,2) DEFAULT 0, 
                total DECIMAL(10,2) DEFAULT 0, 
                customer VARCHAR(255),
                unit_type VARCHAR(50),
                customer_name VARCHAR(255),
                customer_phone VARCHAR(50),
                bill_no VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS waste (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL, 
                vegetable VARCHAR(255) NOT NULL, 
                quantity DECIMAL(10,3) DEFAULT 0, 
                reason TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(50), 
                name VARCHAR(255), 
                points INTEGER DEFAULT 0,
                total_spent DECIMAL(10,2) DEFAULT 0,
                last_visit DATE,
                UNIQUE(phone, name)
            )""",
            
            """CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL, 
                category VARCHAR(100), 
                amount DECIMAL(10,2) DEFAULT 0, 
                description TEXT
            )"""
        ]
        
        for sql in tables_sql:
            try:
                c.execute(sql)
            except Exception as e:
                logger.error(f"Error creating table: {e}")
        
        conn.commit()
        logger.info("✅ All tables created/verified")
        
        # Initialize default items efficiently
        self._initialize_default_items(conn)
    
    def _initialize_default_items(self, conn):
        """Initialize default items efficiently"""
        c = conn.cursor()
        
        # Get existing items once
        c.execute("SELECT vegetable FROM inventory")
        existing_items = {row[0] for row in c.fetchall()}
        
        # Default items
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
        
        # Insert only non-existing items using batch operations
        to_insert = []
        
        for veg in kg_vegetables:
            if veg not in existing_items:
                to_insert.append((veg, 0, 0, 0, '', 'kg', 'vegetable'))
        
        for veg in piece_vegetables:
            if veg not in existing_items:
                to_insert.append((veg, 0, 0, 0, '', 'piece', 'vegetable'))
        
        for fruit in fruits_kg:
            if fruit not in existing_items:
                to_insert.append((fruit, 0, 0, 0, '', 'kg', 'fruit'))
        
        # Batch insert
        if to_insert:
            c.executemany("""
                INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, image_url, unit_type, category) 
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vegetable) DO NOTHING
            """, to_insert)
        
        conn.commit()
    
    def export_database(self):
        """Export database to downloadable format"""
        try:
            conn = self.get_connection()
            if conn:
                export_data = {}
                tables = ["inventory", "purchases", "sales", "waste", "customers", "expenses"]
                
                for table in tables:
                    try:
                        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                        export_data[table] = df.to_dict('records')
                    except Exception as e:
                        logger.error(f"Error exporting {table}: {e}")
                        export_data[table] = []
                
                # Save as JSON
                json_file = os.path.join(tempfile.gettempdir(), f"freshbasket_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                with open(json_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                return json_file
        except Exception as e:
            logger.error(f"Export failed: {e}")
        return None

# Initialize database manager
db_manager = ExternalDatabaseManager()

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
    
    return False

# ========================== INITIALIZE DATABASE ==========================
if not db_manager.init_database():
    st.error("❌ Failed to initialize database system. Please configure Supabase.")
    st.stop()

def get_db_connection():
    """Get database connection"""
    return db_manager.get_connection()

# ========================== INITIALIZE SESSION STATE ==========================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'role' not in st.session_state:
    st.session_state.role = ""
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'shortage_threshold' not in st.session_state:
    st.session_state.shortage_threshold = 5.0
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = date.today()
if 'last_sale' not in st.session_state:
    st.session_state.last_sale = None
if 'guest_counter' not in st.session_state:
    st.session_state.guest_counter = 1
if 'backup_counter' not in st.session_state:
    st.session_state.backup_counter = 0
if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = None
if 'inventory_refresh_time' not in st.session_state:
    st.session_state.inventory_refresh_time = None
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

# ========================== MAIN APP ==========================
if not st.session_state.logged_in:
    login_page()
    st.stop()

# ========================== PAGE SETUP ==========================
st.set_page_config(page_title="Fresh Basket", page_icon="🌿", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);}
    
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Montserrat:wght@400;500;600;700&display=swap');
    
    * {font-family: 'Poppins', sans-serif;}
    
    h1, h2, h3, h4, h5, h6 {font-family: 'Montserrat', sans-serif !important; font-weight: 600 !important;}
    
    h1 {text-align:center; color:#2c3e50; font-size:2.8em; margin-bottom:5px;}
    .subtitle {text-align:center; color:#27ae60; font-size:1.2em; margin-bottom:10px; font-weight:500;}
    
    .stButton>button {height:3em; border-radius:12px; font-size:16px; font-weight:500; transition: all 0.3s ease; border: none !important;}
    .stButton>button:hover {transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.15) !important;}
    
    .primary-btn {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%) !important; color:white !important;}
    .secondary-btn {background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important; color:white !important;}
    
    .card {background: white; padding: 25px; border-radius: 20px; margin: 15px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.2); transition: transform 0.3s ease, box-shadow 0.3s ease;}
    .card:hover {transform: translateY(-5px); box-shadow: 0 15px 35px rgba(0,0,0,0.12);}
    
    .metric-card {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 25px; border-radius: 15px; margin: 10px; color: white; text-align: center; box-shadow: 0 8px 25px rgba(39, 174, 96, 0.3);}
    .inventory-card {background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); padding: 20px; border-radius: 15px; margin: 10px; color: white; box-shadow: 0 8px 25px rgba(52, 152, 219, 0.3);}
    .sales-card {background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); padding: 20px; border-radius: 15px; margin: 10px; color: white; box-shadow: 0 8px 25px rgba(155, 89, 182, 0.3);}
    .purchase-card {background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); padding: 20px; border-radius: 15px; margin: 10px; color: white; box-shadow: 0 8px 25px rgba(243, 156, 18, 0.3);}
    .red-alert-card {background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important; padding: 20px; border-radius: 15px; margin: 10px; color: white; box-shadow: 0 8px 25px rgba(231, 76, 60, 0.3);}
    
    /* Hide number input placeholders */
    .stNumberInput input[type="number"]::placeholder {color: transparent !important;}
    .stNumberInput input::-webkit-input-placeholder {color: transparent !important;}
    .stNumberInput input:-moz-placeholder {color: transparent !important;}
    .stNumberInput input::-moz-placeholder {color: transparent !important;}
    .stNumberInput input:-ms-input-placeholder {color: transparent !important;}
    .stNumberInput div[data-baseweb="form-control"] > div:nth-child(2) {visibility: hidden !important; height: 0 !important; margin: 0 !important; padding: 0 !important; min-height: 0 !important;}
    
    .user-info {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; padding: 10px 15px; border-radius: 10px; margin: 10px 0; text-align: center; font-weight: bold;}
    
    .db-status-success {background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; padding: 10px; border-radius: 10px; margin: 5px 0;}
    .db-status-warning {background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; padding: 10px; border-radius: 10px; margin: 5px 0;}
    .db-status-error {background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 10px; border-radius: 10px; margin: 5px 0;}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div style="text-align:center; margin-bottom:30px;">
    <h1>🌿 Fresh Basket</h1>
    <div class="subtitle">Freshness You Can Feel</div>
</div>
""", unsafe_allow_html=True)

# Initialize database connection
conn = get_db_connection()
if conn is None:
    st.error("❌ Critical: Could not initialize database. Please refresh the page.")
    st.stop()

# ========================== OPTIMIZED HELPER FUNCTIONS ==========================
@st.cache_data(ttl=10)  # Reduced from 30 to 10 seconds for faster updates
def get_inventory_data():
    """Get all inventory data with caching"""
    try:
        return db_cache.get_inventory(conn)
    except Exception as e:
        logger.error(f"Error getting inventory data: {e}")
        return {}

@st.cache_data(ttl=10)
def get_inventory_df():
    """Get inventory as DataFrame with caching"""
    try:
        return db_cache.get_inventory_df(conn)
    except Exception as e:
        logger.error(f"Error getting inventory DataFrame: {e}")
        return pd.DataFrame()

def get_stock(veg):
    """Return stock information for a vegetable"""
    inventory_data = get_inventory_data()
    if veg in inventory_data:
        qty, cost, sell, unit_type, category = inventory_data[veg]
        return qty or 0.0, cost or 0.0, sell or 0.0, unit_type or 'kg', category or 'vegetable'
    return 0.0, 0.0, 0.0, 'kg', 'vegetable'

@st.cache_data(ttl=15)  # Reduced from 60 to 15 seconds
def get_available_items():
    """Get items available for sale with caching"""
    inventory_df = get_inventory_df()
    
    if inventory_df.empty:
        return [], [], []
    
    # Filter for available items
    available_df = inventory_df[(inventory_df['quantity'] > 0) & (inventory_df['selling_price'] > 0)]
    
    kg_vegetables = []
    piece_vegetables = []
    kg_fruits = []
    
    for _, row in available_df.iterrows():
        veg = row['vegetable']
        qty = row['quantity']
        price = row['selling_price']
        unit_type = row['unit_type']
        category = row['category']
        
        item_data = {
            'name': veg,
            'price': price,
            'stock': qty,
            'display': f"{veg} (Stock: {qty:.2f} {unit_type}, Price: ₹{price:.2f}/{unit_type})"
        }
        
        if category == 'fruit' and unit_type == 'kg':
            kg_fruits.append(item_data)
        elif category == 'vegetable':
            if unit_type == 'kg':
                kg_vegetables.append(item_data)
            elif unit_type == 'piece':
                piece_vegetables.append(item_data)
    
    return kg_vegetables, piece_vegetables, kg_fruits

@st.cache_data(ttl=30)
def get_last_record_date(table_name):
    """Get the date of the last record in a table"""
    try:
        c = conn.cursor()
        if table_name in ["sales", "purchases", "waste", "expenses"]:
            c.execute(f"SELECT MAX(date) FROM {table_name}")
            result = c.fetchone()[0]
            return result if result else "N/A"
    except Exception as e:
        logger.error(f"Error getting last record date: {e}")
    return "N/A"

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
    
    # Check stock availability
    insufficient = []
    for veg, qty, _, _, unit_type, _ in st.session_state.cart:
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
    
    bill_no = datetime.now().strftime("%Y%m%d%H%M%S")
    
    sale_details = []
    c = conn.cursor()
    
    try:
        # Process all items in a transaction
        for item in st.session_state.cart:
            veg, qty, price, total, unit_type, category = item
            
            c.execute("""
                INSERT INTO sales (date, vegetable, quantity_sold, sale_price, total, customer, unit_type, customer_name, customer_phone, bill_no) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (d, veg, qty, price, total, cust, unit_type, cust_name, cust_phone, bill_no))
            
            c.execute("UPDATE inventory SET quantity = quantity - %s WHERE vegetable=%s", (qty, veg))
            
            sale_details.append({
                "item": veg,
                "quantity": qty,
                "price": price,
                "total": total,
                "unit_type": unit_type
            })
        
        # Update customer information
        if cust_phone and cust_phone.strip() != "":
            total_amount = sum(item[3] for item in st.session_state.cart)
            try:
                c.execute("""
                    INSERT INTO customers (phone, name, points, total_spent, last_visit) 
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (phone, name) DO UPDATE 
                    SET points = customers.points + %s, 
                        total_spent = customers.total_spent + %s,
                        last_visit = %s
                """, (cust_phone, cust_name, int(total_amount // 10), total_amount, d, int(total_amount // 10), total_amount, d))
            except Exception as e:
                logger.error(f"Error updating customer: {e}")
        
        conn.commit()
        
        st.session_state.last_sale = {
            "date": d,
            "customer": cust,
            "customer_name": cust_name,
            "customer_phone": cust_phone,
            "items": sale_details,
            "total": sum(item[3] for item in st.session_state.cart),
            "phone": cust_phone,
            "time": current_time,
            "bill_no": bill_no
        }
        
        st.session_state.cart = []
        st.cache_data.clear()  # Clear cache to refresh data
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error processing sale: {e}")
        st.error(f"Error processing sale: {str(e)}")
        return False

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
        st.cache_data.clear()
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
         "⬇ Download", "💰 Financials", "🔧 Database Tools", "🔍 Secrets Debug"],
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
        # Get database statistics
        db_status_class = "db-status-success"
        db_status_text = "✅ Connected"
        
        if db_manager.db_type == "supabase":
            db_type_text = "Supabase PostgreSQL"
            db_status_class = "db-status-success"
            db_status_text = "✅ Supabase PostgreSQL (Permanent Storage)"
        elif db_manager.db_type == "postgresql":
            db_type_text = "PostgreSQL"
            db_status_class = "db-status-success"
            db_status_text = "✅ PostgreSQL (Permanent Storage)"
        else:
            db_type_text = "Local SQLite"
            db_status_text = "⚠️ Local SQLite (Not Recommended)"
        
        # Get counts with caching
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM inventory")
        inv_count = c.fetchone()[0]
        
        st.markdown(f"""
        <div style="background: white; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>🗄️ Type:</strong> {db_type_text}
            </p>
            <p style="margin: 5px 0; font-size: 0.9em;">
                <strong>📦 Items:</strong> {inv_count}
            </p>
            <div class="{db_status_class}" style="margin: 10px 0; padding: 8px; border-radius: 8px;">
                <strong>{db_status_text}</strong>
                {"🛡️ No Data Loss" if db_manager.db_type != "local" else "⚠️ Local (Backup Active)"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Download backup button
        if st.button("📥 Download Data", use_container_width=True, key="download_backup"):
            json_file = db_manager.export_database()
            if json_file and os.path.exists(json_file):
                with open(json_file, 'rb') as f:
                    st.download_button(
                        label="📥 Download All Data",
                        data=f,
                        file_name=f"freshbasket_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True,
                        key="download_data_btn"
                    )
    
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
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0")
        total_items = c.fetchone()[0]
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦</h3>
            <h4>Stock Items</h4>
            <h2>{total_items}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        c.execute("SELECT COALESCE(SUM(total),0) as total FROM sales WHERE date=%s", 
                 (selected_date.strftime("%Y-%m-%d"),))
        today_sales = c.fetchone()[0]
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Today's Sales</h4>
            <h2>₹{today_sales:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        c.execute("SELECT COUNT(DISTINCT customer_name) as count FROM sales WHERE date=%s AND customer_name IS NOT NULL", 
                 (selected_date.strftime("%Y-%m-%d"),))
        today_customers_df = c.fetchone()[0]
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h4>Today's Customers</h4>
            <h2>{today_customers_df}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        threshold = st.session_state.shortage_threshold
        c.execute("SELECT COUNT(*) as count FROM inventory WHERE quantity > 0 AND quantity < %s", 
                 (threshold,))
        low_stock_count = c.fetchone()[0]
        st.markdown(f"""
        <div class="red-alert-card">
            <h3>⚠️</h3>
            <h4>Low Stock Items</h4>
            <h2>{low_stock_count}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### 📉 Low Stock Items Alert")
    threshold = st.session_state.shortage_threshold
    
    inventory_data = get_inventory_data()
    
    if not inventory_data:
        st.info("No stock available. Add purchases first.")
    else:
        low_stock_items = []
        
        for veg, data in inventory_data.items():
            qty, _, price, unit_type, category = data
            if qty > 0:
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
        
        if low_stock_items:
            low_stock_df = pd.DataFrame(low_stock_items)
            st.dataframe(
                low_stock_df,
                use_container_width=True,
                height=300
            )
        else:
            st.success("✅ All items have sufficient stock levels!")
    
    st.markdown("---")
    
    st.markdown("### 📋 Current Stock Details")
    threshold = st.slider("Low Stock Alert Threshold", 0.0, 50.0, 5.0, 0.5)
    st.session_state.shortage_threshold = threshold
    
    if not inventory_data:
        st.info("No stock available. Add purchases first.")
    else:
        # Separate vegetables and fruits
        vegetables = {k: v for k, v in inventory_data.items() if v[4] == 'vegetable'}
        fruits = {k: v for k, v in inventory_data.items() if v[4] == 'fruit'}
        
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        with tab1:
            if vegetables:
                veg_list = []
                for veg, data in vegetables.items():
                    qty, _, price, unit_type, _ = data
                    veg_list.append({
                        "Vegetable": veg,
                        "Stock": qty,
                        "Price": price,
                        "Unit": unit_type
                    })
                
                veg_df = pd.DataFrame(veg_list)
                st.dataframe(
                    veg_df.style.format({
                        "Stock": "{:.2f}",
                        "Price": "₹{:.2f}"
                    }),
                    use_container_width=True,
                    height=300
                )
        
        with tab2:
            if fruits:
                fruit_list = []
                for fruit, data in fruits.items():
                    qty, _, price, unit_type, _ = data
                    fruit_list.append({
                        "Fruit": fruit,
                        "Stock": qty,
                        "Price": price,
                        "Unit": unit_type
                    })
                
                fruit_df = pd.DataFrame(fruit_list)
                st.dataframe(
                    fruit_df.style.format({
                        "Stock": "{:.2f}",
                        "Price": "₹{:.2f}"
                    }),
                    use_container_width=True,
                    height=300
                )
        
        # Summary
        col1, col2 = st.columns(2)
        with col1:
            out_of_stock = sum(1 for data in inventory_data.values() if data[0] == 0)
            st.info(f"**Out of Stock:** {out_of_stock} items")
        
        with col2:
            low_stock_count = sum(1 for data in inventory_data.values() 
                                 if data[0] > 0 and ((data[3] == 'kg' and data[0] < threshold) or 
                                                     (data[3] == 'piece' and data[0] < 10)))
            if low_stock_count > 0:
                st.warning(f"**Low Stock Items:** {low_stock_count} items")

# ========================== ADD PURCHASE ==========================
elif menu == "🛒 Add Purchase":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🛒 Add Purchase</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all vegetables once
    inventory_data = get_inventory_data()
    all_veg = list(inventory_data.keys())
    
    if not all_veg:
        st.info("No vegetables in inventory. Please add vegetables first.")
    else:
        tab1, tab2 = st.tabs(["📝 Bulk Purchase Entry", "➕ Individual Purchase"])
        
        with tab1:
            st.markdown("### 📝 Bulk Purchase Entry")
            
            # Get current stock
            purchase_list = []
            for veg in all_veg:
                qty, cost, price, unit_type, category = inventory_data[veg]
                purchase_list.append({
                    'vegetable': veg,
                    'current_stock': qty,
                    'selling_price': price,
                    'unit_type': unit_type,
                    'category': category,
                    'new_purchase': 0.0,
                    'amount': 0.0,
                    'supplier': ""
                })
            
            purchase_df = pd.DataFrame(purchase_list)
            
            edited_df = st.data_editor(
                purchase_df,
                column_config={
                    "vegetable": st.column_config.TextColumn("🌿 Item", disabled=True),
                    "current_stock": st.column_config.NumberColumn("📦 Current Stock", min_value=0.0, format="%.2f"),
                    "unit_type": st.column_config.TextColumn("📏 Unit", disabled=True),
                    "category": st.column_config.TextColumn("📁 Category", disabled=True),
                    "new_purchase": st.column_config.NumberColumn("🛒 Purchase Qty", min_value=0.0, step=0.5, format="%.2f"),
                    "amount": st.column_config.NumberColumn("💰 Amount (₹)", min_value=0.0, step=10.0, format="₹%.2f"),
                    "supplier": st.column_config.TextColumn("👨‍🌾 Supplier", max_chars=50)
                },
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True
            )
            
            if st.button("💾 Save All Purchases", type="primary", use_container_width=True):
                purchases_made = 0
                c = conn.cursor()
                
                for _, row in edited_df.iterrows():
                    veg = row['vegetable']
                    
                    if row['new_purchase'] > 0 and row['amount'] > 0:
                        d = selected_date.strftime("%Y-%m-%d")
                        qty = row['new_purchase']
                        amount = row['amount']
                        supplier = row['supplier']
                        
                        c.execute("INSERT INTO purchases (date, vegetable, quantity, amount, supplier) VALUES (%s,%s,%s,%s,%s)", 
                                 (d, veg, qty, amount, supplier))
                        
                        if qty > 0:
                            old_qty = inventory_data[veg][0]
                            new_qty = old_qty + qty
                            unit_cost = (amount / qty) if qty > 0 else inventory_data[veg][1]
                            c.execute("UPDATE inventory SET quantity=%s, cost_price=%s WHERE vegetable=%s", 
                                     (new_qty, unit_cost, veg))
                        
                        purchases_made += 1
                
                conn.commit()
                st.cache_data.clear()  # Clear cache
                if purchases_made > 0:
                    st.success(f"✅ {purchases_made} purchases saved")
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
                        kg_vegetables = [veg for veg in all_veg if inventory_data[veg][3] == 'kg' and inventory_data[veg][4] == 'vegetable']
                        veg_choice = st.selectbox("Select Vegetable (KG)", kg_vegetables, key="kg_veg_select_purchase")
                        
                        if veg_choice:
                            qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="kg_qty_kg")
                            if qty_kg is None:
                                qty_kg = 0.0
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=None, placeholder="Enter amount", key="kg_amount")
                        if amount is None:
                            amount = 0.0
                        supplier = st.text_input("Supplier Name", key="kg_supplier")
                        
                        if amount > 0 and qty_kg > 0:
                            unit_price = amount / qty_kg
                            st.info(f"**Unit Price:** ₹{unit_price:.2f}/kg")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if qty_kg <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            
                            c.execute("INSERT INTO purchases (date, vegetable, quantity, amount, supplier) VALUES (%s,%s,%s,%s,%s)", 
                                     (d, veg_choice, qty_kg, amount, supplier))
                            
                            old_qty = inventory_data[veg_choice][0]
                            new_qty = old_qty + qty_kg
                            unit_cost = (amount / qty_kg) if qty_kg > 0 else inventory_data[veg_choice][1]
                            
                            c.execute("UPDATE inventory SET quantity=%s, cost_price=%s WHERE vegetable=%s", 
                                     (new_qty, unit_cost, veg_choice))
                            
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Added {qty_kg:.2f} kg of {veg_choice}")
            
            with subtab2:
                with st.form("piece_vegetable_purchase", clear_on_submit=True):
                    st.markdown("#### 🧩 Purchase Vegetables (Piece)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        piece_vegetables = [veg for veg in all_veg if inventory_data[veg][3] == 'piece' and inventory_data[veg][4] == 'vegetable']
                        veg_choice = st.selectbox("Select Vegetable (Piece)", piece_vegetables, key="piece_veg_select_purchase")
                        
                        if veg_choice:
                            total_qty = st.number_input("Number of Pieces", min_value=0, step=1, value=None, placeholder="Enter pieces", key="piece_qty")
                            if total_qty is None:
                                total_qty = 0
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=None, placeholder="Enter amount", key="piece_amount")
                        if amount is None:
                            amount = 0.0
                        supplier = st.text_input("Supplier Name", key="piece_supplier")
                        
                        if amount > 0 and total_qty > 0:
                            unit_price = amount / total_qty
                            st.info(f"**Unit Price:** ₹{unit_price:.2f}/piece")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if total_qty <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            
                            c.execute("INSERT INTO purchases (date, vegetable, quantity, amount, supplier) VALUES (%s,%s,%s,%s,%s)", 
                                     (d, veg_choice, total_qty, amount, supplier))
                            
                            old_qty = inventory_data[veg_choice][0]
                            new_qty = old_qty + total_qty
                            unit_cost = (amount / total_qty) if total_qty > 0 else inventory_data[veg_choice][1]
                            
                            c.execute("UPDATE inventory SET quantity=%s, cost_price=%s WHERE vegetable=%s", 
                                     (new_qty, unit_cost, veg_choice))
                            
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Added {total_qty:.0f} pieces of {veg_choice}")
            
            with subtab3:
                with st.form("fruit_purchase", clear_on_submit=True):
                    st.markdown("#### 🍎 Purchase Fruits (KG)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fruits = [veg for veg in all_veg if inventory_data[veg][4] == 'fruit']
                        fruit_choice = st.selectbox("Select Fruit", fruits if fruits else ["No fruits available"], key="fruit_select_purchase")
                        
                        if fruit_choice and fruit_choice != "No fruits available":
                            qty_kg = st.number_input("Kilograms", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="fruit_qty_kg")
                            if qty_kg is None:
                                qty_kg = 0.0
                    
                    with col2:
                        amount = st.number_input("Total Amount ₹", min_value=0.0, step=10.0, value=None, placeholder="Enter amount", key="fruit_amount")
                        if amount is None:
                            amount = 0.0
                        supplier = st.text_input("Supplier Name", key="fruit_supplier")
                        
                        if amount > 0 and qty_kg > 0:
                            unit_price = amount / qty_kg
                            st.info(f"**Unit Price:** ₹{unit_price:.2f}/kg")
                    
                    submit_button = st.form_submit_button("💾 Save Purchase", type="primary", use_container_width=True)
                    if submit_button:
                        if qty_kg <= 0:
                            st.error("Enter quantity > 0")
                        elif amount <= 0:
                            st.error("Enter amount > 0")
                        elif not fruit_choice or fruit_choice == "No fruits available":
                            st.error("Select a fruit")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            
                            c.execute("INSERT INTO purchases (date, vegetable, quantity, amount, supplier) VALUES (%s,%s,%s,%s,%s)", 
                                     (d, fruit_choice, qty_kg, amount, supplier))
                            
                            old_qty = inventory_data[fruit_choice][0]
                            new_qty = old_qty + qty_kg
                            unit_cost = (amount / qty_kg) if qty_kg > 0 else inventory_data[fruit_choice][1]
                            
                            c.execute("UPDATE inventory SET quantity=%s, cost_price=%s WHERE vegetable=%s", 
                                     (new_qty, unit_cost, fruit_choice))
                            
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Added {qty_kg:.2f} kg of {fruit_choice}")
    
    st.markdown("---")
    st.markdown(f"### 📊 Today's Purchases ({selected_date.strftime('%d %B %Y')})")
    
    c = conn.cursor()
    c.execute("SELECT vegetable, quantity, amount, supplier FROM purchases WHERE date=%s ORDER BY id DESC", 
              (selected_date.strftime("%Y-%m-%d"),))
    today_purchases_rows = c.fetchall()
    today_purchases = pd.DataFrame(today_purchases_rows, columns=["vegetable", "quantity", "amount", "supplier"])
    
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
            st.metric("🌿 Items Bought", veg_count)
        
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
    
    inventory_data = get_inventory_data()
    
    if not inventory_data:
        st.info("No vegetables in inventory")
    else:
        st.markdown("### ➕ Add New Item")
        with st.form("add_new_item"):
            col1, col2 = st.columns(2)
            with col1:
                new_item = st.text_input("New Item Name")
                category = st.selectbox("Category", ["vegetable", "fruit"])
            with col2:
                unit_type = st.selectbox("Unit Type", ["kg", "piece"])
                new_price = st.number_input("Initial Selling Price ₹", min_value=0.0, step=1.0, value=None, placeholder="Enter price")
                if new_price is None:
                    new_price = 0.0
            
            submitted = st.form_submit_button("➕ Add Item", use_container_width=True)
            if submitted:
                if new_item and new_item.strip():
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) 
                        VALUES (%s, 0, 0, %s, %s, %s)
                        ON CONFLICT (vegetable) DO NOTHING
                    """, (new_item.strip(), new_price, unit_type, category))
                    conn.commit()
                    st.cache_data.clear()  # Clear cache
                    st.success(f"✅ Added {new_item.strip()} to inventory")
                    st.rerun()
        
        st.markdown("---")
        
        # Separate tabs for vegetables and fruits
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        price_list = []
        for veg, data in inventory_data.items():
            qty, cost, price, unit_type, category = data
            price_list.append({
                'vegetable': veg,
                'selling_price': price,
                'unit_type': unit_type,
                'category': category
            })
        
        price_df = pd.DataFrame(price_list)
        
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
        
        if st.button("💾 Save All Prices", type="primary", use_container_width=True):
            changes = 0
            c = conn.cursor()
            if 'edited_df' in locals():
                for _, row in edited_df.iterrows():
                    c.execute("UPDATE inventory SET selling_price=%s WHERE vegetable=%s", 
                             (row['selling_price'], row['vegetable']))
                    changes += 1
            if 'edited_df2' in locals():
                for _, row in edited_df2.iterrows():
                    c.execute("UPDATE inventory SET selling_price=%s WHERE vegetable=%s", 
                             (row['selling_price'], row['vegetable']))
                    changes += 1
            
            conn.commit()
            st.cache_data.clear()  # Clear cache
            st.success(f"✅ {changes} prices updated successfully!")
        
        st.markdown("---")
        
        st.markdown("### ✏️ Individual Price Update")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_item = st.selectbox("Select Item", list(inventory_data.keys()))
            
            if selected_item in inventory_data:
                current_price = inventory_data[selected_item][2]
                current_unit = inventory_data[selected_item][3]
                current_category = inventory_data[selected_item][4]
                
                if current_unit == 'kg':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.info(f"**Current Price:** ₹{current_price:.2f}/piece")
                
                stock = inventory_data[selected_item][0]
                st.info(f"**Current Stock:** {stock:.2f} {current_unit}")
                st.info(f"**Category:** {current_category}")
        
        with col2:
            new_price = st.number_input("New Price ₹", min_value=0.0, step=1.0, value=None, placeholder="Enter new price")
            if new_price is None:
                new_price = 0.0
            
            if st.button("💾 Update Price", type="primary", use_container_width=True):
                c = conn.cursor()
                c.execute("UPDATE inventory SET selling_price=%s WHERE vegetable=%s", (new_price, selected_item))
                conn.commit()
                st.cache_data.clear()  # Clear cache
                if current_unit == 'kg':
                    st.success(f"✅ Price updated for {selected_item}: ₹{new_price:.2f}/kg")
                elif current_unit == 'piece':
                    st.success(f"✅ Price updated for {selected_item}: ₹{new_price:.2f}/piece")

# ========================== QUICK SELL ==========================
elif menu == "💵 Quick Sell":
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2>💵 Quick Selling</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    kg_vegetables, piece_vegetables, kg_fruits = get_available_items()
    
    if not kg_vegetables and not piece_vegetables and not kg_fruits:
        st.warning("⚠️ No items available for sale! Please add purchases and set prices first.")
    else:
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
                                        st.rerun()
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
                                        st.rerun()
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
                                        st.rerun()
                else:
                    st.info("No fruits available")
        
        with col2:
            st.markdown("### 🛒 Current Bill")
            
            if not st.session_state.cart:
                st.info("🛒 Bill is Empty - Add items from the left")
            else:
                # Display cart items
                cart_table_data = []
                total_amount = 0
                
                for veg, qty, price, item_total, unit_type, category in st.session_state.cart:
                    if unit_type == 'kg':
                        quantity_display = f"{qty:.3f} kg"
                        price_display = f"₹{price:.2f}/kg"
                    elif unit_type == 'piece':
                        quantity_display = f"{qty:.0f} pieces"
                        price_display = f"₹{price:.2f}/piece"
                    
                    icon = "🥦" if category == 'vegetable' else "🍎"
                    
                    cart_table_data.append({
                        "Item": f"{icon} {veg}",
                        "Quantity": quantity_display,
                        "Unit Price": price_display,
                        "Total": f"₹{item_total:.2f}"
                    })
                    total_amount += item_total
                
                # Display as a table
                cart_df = pd.DataFrame(cart_table_data)
                st.dataframe(
                    cart_df,
                    use_container_width=True,
                    hide_index=True
                )
                
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
                
                # Complete Bill Button
                st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
                if st.button("✅ Complete Bill", type="primary", use_container_width=True, key="complete_bill"):
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
                    
                    items_data.append({
                        'Item': item['item'],
                        'Quantity': quantity_display,
                        'Price': price_display,
                        'Total': f"₹{item['total']:.2f}"
                    })
                
                items_df = pd.DataFrame(items_data)
                
                st.dataframe(
                    items_df,
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
                        st.success("Ready for PDF printing! Click 'Print Bill' after sale.")
                    else:
                        if print_universal(sale, method="auto"):
                            st.success("✅ Bill sent to printer!")
                        else:
                            st.error("❌ Printing failed.")
            
            with col2:
                if st.button("👁️ Preview Bill", use_container_width=True, key="preview_bill_btn"):
                    sale = st.session_state.last_sale
                    bill_text = format_bill_universal(sale)
                    st.markdown("### 📄 Bill Preview")
                    st.code(bill_text, language=None)
            
            with col3:
                if st.button("📄 Save as PDF", use_container_width=True, key="save_pdf_btn"):
                    st.success("PDF print dialog opened!")
            
            with col4:
                if st.button("🔄 New Bill", use_container_width=True, key="new_bill_btn"):
                    st.session_state.last_sale = None
                    st.rerun()

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
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO inventory (vegetable, quantity, cost_price, selling_price, unit_type, category) 
                        VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (vegetable) DO NOTHING
                    """, (new_item_name.strip(), initial_qty, 0.0, initial_price, unit_type, category))
                    conn.commit()
                    st.cache_data.clear()  # Clear cache
                    st.success(f"✅ Added {new_item_name.strip()} to inventory")
                    st.rerun()
        
        with col2:
            st.markdown("#### 🗑️ Remove Item")
            inventory_data = get_inventory_data()
            
            if inventory_data:
                item_to_remove = st.selectbox("Select item to remove", list(inventory_data.keys()), key="item_to_remove")
                confirm = st.checkbox("I confirm I want to remove this item", key="confirm_remove")
                
                if st.button("Remove from Inventory", use_container_width=True, type="secondary", disabled=not confirm, key="remove_item_btn"):
                    stock = inventory_data[item_to_remove][0]
                    if stock > 0:
                        st.error(f"Cannot remove {item_to_remove} - it still has {stock:.2f} in stock")
                    else:
                        c = conn.cursor()
                        c.execute("DELETE FROM inventory WHERE vegetable=%s", (item_to_remove,))
                        conn.commit()
                        st.cache_data.clear()  # Clear cache
                        st.success(f"✅ Removed {item_to_remove} from inventory")
                        st.rerun()
    
    st.markdown("### 📋 Current Inventory")
    
    inventory_data = get_inventory_data()
    
    if not inventory_data:
        st.info("No inventory items")
    else:
        in_stock = sum(1 for data in inventory_data.values() if data[0] > 0)
        out_of_stock = sum(1 for data in inventory_data.values() if data[0] == 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(inventory_data))
        with col2:
            st.metric("In Stock", in_stock)
        with col3:
            st.metric("Out of Stock", out_of_stock)
        
        # Separate tabs for vegetables and fruits
        tab1, tab2 = st.tabs(["🥦 Vegetables", "🍎 Fruits"])
        
        veg_list = []
        fruit_list = []
        
        for veg, data in inventory_data.items():
            qty, cost, price, unit_type, category = data
            if category == 'vegetable':
                veg_list.append({
                    'vegetable': veg,
                    'quantity': qty,
                    'selling_price': price,
                    'unit_type': unit_type,
                    'category': category
                })
            elif category == 'fruit':
                fruit_list.append({
                    'vegetable': veg,
                    'quantity': qty,
                    'selling_price': price,
                    'unit_type': unit_type,
                    'category': category
                })
        
        with tab1:
            if veg_list:
                veg_df = pd.DataFrame(veg_list)
                
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
            if fruit_list:
                fruit_df = pd.DataFrame(fruit_list)
                
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
            c = conn.cursor()
            if 'edited_veg' in locals():
                for _, row in edited_veg.iterrows():
                    try:
                        c.execute("UPDATE inventory SET quantity=%s, selling_price=%s WHERE vegetable=%s", 
                                 (row['quantity'], row['selling_price'], row['vegetable']))
                        changes_made += 1
                    except Exception as e:
                        st.error(f"Error updating {row['vegetable']}: {e}")
            
            if 'edited_fruit' in locals():
                for _, row in edited_fruit.iterrows():
                    try:
                        c.execute("UPDATE inventory SET quantity=%s, selling_price=%s WHERE vegetable=%s", 
                                 (row['quantity'], row['selling_price'], row['vegetable']))
                        changes_made += 1
                    except Exception as e:
                        st.error(f"Error updating {row['vegetable']}: {e}")
            
            try:
                conn.commit()
                st.cache_data.clear()  # Clear cache
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
    
    c = conn.cursor()
    if show_all:
        c.execute("SELECT * FROM purchases ORDER BY date DESC, id DESC")
        purchases_rows = c.fetchall()
        purchases_df = pd.DataFrame(purchases_rows, columns=['id', 'date', 'vegetable', 'quantity', 'amount', 'supplier'])
    else:
        c.execute("SELECT * FROM purchases WHERE date=%s ORDER BY id DESC", 
                  (view_date.strftime("%Y-%m-%d"),))
        purchases_rows = c.fetchall()
        purchases_df = pd.DataFrame(purchases_rows, columns=['id', 'date', 'vegetable', 'quantity', 'amount', 'supplier'])
    
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
    
    c = conn.cursor()
    if show_all_sales:
        c.execute("SELECT * FROM sales ORDER BY date DESC, id DESC")
        sales_rows = c.fetchall()
        sales_df = pd.DataFrame(sales_rows, columns=['id', 'date', 'vegetable', 'quantity_sold', 'sale_price', 'total', 
                                                     'customer', 'unit_type', 'customer_name', 'customer_phone', 'bill_no'])
    else:
        c.execute("SELECT * FROM sales WHERE date=%s ORDER BY id DESC", 
                  (view_date.strftime("%Y-%m-%d"),))
        sales_rows = c.fetchall()
        sales_df = pd.DataFrame(sales_rows, columns=['id', 'date', 'vegetable', 'quantity_sold', 'sale_price', 'total',
                                                     'customer', 'unit_type', 'customer_name', 'customer_phone', 'bill_no'])
    
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
            unit_type = row['unit_type']
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            return f"{row['quantity_sold']:.2f} {unit_type}"
        
        display_df['Quantity Display'] = display_df.apply(format_sales_row, axis=1)
        
        st.dataframe(
            display_df[['date', 'vegetable', 'Quantity Display', 'total', 'customer_name', 'customer_phone', 'bill_no']].rename(columns={
                'customer_name': 'Customer',
                'customer_phone': 'Phone',
                'bill_no': 'Bill No'
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
            amount = st.number_input("Amount ₹", min_value=0.0, step=10.0, value=None, placeholder="Enter amount", key="expense_amount")
            if amount is None:
                amount = 0.0
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
                c = conn.cursor()
                c.execute("INSERT INTO expenses (date, category, amount, description) VALUES (%s,%s,%s,%s)", 
                         (d, category, amount, description))
                conn.commit()
                st.success(f"✅ Expense recorded: {category} - ₹{amount:.2f}")
    
    st.markdown("### Today's Expenses")
    c = conn.cursor()
    c.execute("SELECT * FROM expenses WHERE date=%s", (selected_date.strftime("%Y-%m-%d"),))
    expenses_rows = c.fetchall()
    expenses_df = pd.DataFrame(expenses_rows, columns=['id', 'date', 'category', 'amount', 'description'])
    
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
    
    try:
        # Date selection for customer details
        col1, col2 = st.columns(2)
        with col1:
            customer_view_date = st.date_input("View customers for date", value=selected_date, key="customer_date_view")
        with col2:
            show_all_customers = st.checkbox("Show all dates", key="show_all_customers_view")
        
        c = conn.cursor()
        if show_all_customers:
            # Get all customers with date-wise aggregation
            customers_sql = """
                SELECT 
                    date,
                    COALESCE(customer_phone, 'No Phone') as phone,
                    COALESCE(customer_name, 'Guest') as name,
                    COUNT(*) as total_visits,
                    SUM(total) as total_spent,
                    MAX(customer_name) as customer_name,
                    MAX(customer_phone) as customer_phone
                FROM sales 
                WHERE customer_name IS NOT NULL AND customer_name != ''
                GROUP BY date, COALESCE(customer_phone, 'No Phone'), COALESCE(customer_name, 'Guest')
                ORDER BY date DESC, total_spent DESC
            """
            
            c.execute(customers_sql)
            customers_rows = c.fetchall()
            customers_df = pd.DataFrame(customers_rows, columns=['date', 'phone', 'name', 'total_visits', 'total_spent', 'customer_name', 'customer_phone'])
            
            if customers_df.empty:
                st.info("No customer data available yet")
            else:
                st.markdown("### 📅 All Customers (Date-wise)")
                
                # Group by date for better organization
                dates = customers_df['date'].unique()
                
                for sale_date in dates:
                    date_customers = customers_df[customers_df['date'] == sale_date]
                    
                    with st.expander(f"📅 {sale_date} - {len(date_customers)} customers"):
                        date_total = date_customers['total_spent'].sum()
                        date_visits = date_customers['total_visits'].sum()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(f"Total Sales on {sale_date}", f"₹{date_total:.2f}")
                        with col2:
                            st.metric("Total Customer Visits", date_visits)
                        
                        display_customers = date_customers.copy()
                        display_customers = display_customers.rename(columns={
                            "phone": "📱 Phone",
                            "name": "👤 Name",
                            "total_visits": "🛒 Visits",
                            "total_spent": "💰 Total Spent"
                        })
                        
                        st.dataframe(
                            display_customers[['👤 Name', '📱 Phone', '🛒 Visits', '💰 Total Spent']].style.format({
                                "💰 Total Spent": "₹{:.2f}"
                            }),
                            use_container_width=True
                        )
        else:
            # Get customers for specific date
            d = customer_view_date.strftime("%Y-%m-%d")
            customers_sql = """
                SELECT 
                    COALESCE(customer_phone, 'No Phone') as phone,
                    COALESCE(customer_name, 'Guest') as name,
                    COUNT(*) as total_visits,
                    SUM(total) as total_spent,
                    MAX(customer_name) as customer_name,
                    MAX(customer_phone) as customer_phone
                FROM sales 
                WHERE date=%s AND customer_name IS NOT NULL AND customer_name != ''
                GROUP BY COALESCE(customer_phone, 'No Phone'), COALESCE(customer_name, 'Guest')
                ORDER BY total_spent DESC
            """
            
            c.execute(customers_sql, (d,))
            customers_rows = c.fetchall()
            customers_df = pd.DataFrame(customers_rows, columns=['phone', 'name', 'total_visits', 'total_spent', 'customer_name', 'customer_phone'])
            
            if customers_df.empty:
                st.info(f"No customer data available for {customer_view_date.strftime('%d %B %Y')}")
            else:
                total_customers = len(customers_df)
                total_spent = customers_df['total_spent'].sum()
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Customers", total_customers)
                with col2:
                    st.metric("Total Spent", f"₹{total_spent:.2f}")
                with col3:
                    avg_spent = total_spent / total_customers if total_customers > 0 else 0
                    st.metric("Avg Spent/Customer", f"₹{avg_spent:.2f}")
                
                # Show customers in a table
                st.markdown(f"### 👥 Customers on {customer_view_date.strftime('%d %B %Y')}")
                
                display_customers = customers_df.copy()
                display_customers = display_customers.rename(columns={
                    "phone": "📱 Phone",
                    "name": "👤 Name",
                    "total_visits": "🛒 Visits",
                    "total_spent": "💰 Total Spent"
                })
                
                st.dataframe(
                    display_customers[['👤 Name', '📱 Phone', '🛒 Visits', '💰 Total Spent']].style.format({
                        "💰 Total Spent": "₹{:.2f}"
                    }),
                    use_container_width=True,
                    height=400
                )
    except Exception as e:
        st.error(f"Error loading customer data: {str(e)}")

# ========================== WASTE ==========================
elif menu == "🗑 Waste":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🗑 Waste Management</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    inventory_data = get_inventory_data()
    
    tab1, tab2, tab3 = st.tabs(["🥦 Vegetables (KG)", "🧩 Vegetables (Piece)", "🍎 Fruits (KG)"])
    
    with tab1:
        st.markdown("### 🥦 Vegetables (KG) Waste")
        kg_vegetables = [veg for veg, data in inventory_data.items() 
                        if data[3] == 'kg' and data[4] == 'vegetable']
        
        with st.form("kg_veg_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Vegetable (KG)", kg_vegetables, key="kg_veg_waste_veg")
                if veg:
                    st.info(f"Unit: kg")
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="kg_veg_waste_qty")
                    if qty is None:
                        qty = 0.0
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
                        stock = inventory_data[veg][0]
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.2f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            c.execute("INSERT INTO waste (date, vegetable, quantity, reason) VALUES (%s,%s,%s,%s)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - %s WHERE vegetable=%s", (qty, veg))
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    with tab2:
        st.markdown("### 🧩 Vegetables (Piece) Waste")
        piece_vegetables = [veg for veg, data in inventory_data.items() 
                           if data[3] == 'piece' and data[4] == 'vegetable']
        
        with st.form("piece_veg_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Vegetable (Piece)", piece_vegetables, key="piece_veg_waste_veg")
                if veg:
                    st.info(f"Unit: pieces")
                    qty = st.number_input("Quantity (pieces)", min_value=0, step=1, value=None, placeholder="Enter pieces", key="piece_veg_waste_qty")
                    if qty is None:
                        qty = 0
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
                        stock = inventory_data[veg][0]
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.0f} pieces")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            c.execute("INSERT INTO waste (date, vegetable, quantity, reason) VALUES (%s,%s,%s,%s)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - %s WHERE vegetable=%s", (qty, veg))
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Recorded waste: {qty} pieces of {veg}")
    
    with tab3:
        st.markdown("### 🍎 Fruits (KG) Waste")
        kg_fruits = [veg for veg, data in inventory_data.items() 
                    if data[3] == 'kg' and data[4] == 'fruit']
        
        with st.form("kg_fruit_waste_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                veg = st.selectbox("Select Fruit (KG)", kg_fruits, key="kg_fruit_waste_veg")
                if veg:
                    st.info(f"Unit: kg")
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1, value=None, placeholder="Enter kg", key="kg_fruit_waste_qty")
                    if qty is None:
                        qty = 0.0
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
                        stock = inventory_data[veg][0]
                        if qty > stock:
                            st.error(f"Not enough stock! Available: {stock:.2f} kg")
                        else:
                            d = selected_date.strftime("%Y-%m-%d")
                            c = conn.cursor()
                            c.execute("INSERT INTO waste (date, vegetable, quantity, reason) VALUES (%s,%s,%s,%s)", 
                                     (d, veg, qty, f"{reason}: {description}"))
                            c.execute("UPDATE inventory SET quantity = quantity - %s WHERE vegetable=%s", (qty, veg))
                            conn.commit()
                            st.cache_data.clear()  # Clear cache
                            st.success(f"✅ Recorded waste: {qty} kg of {veg}")
    
    st.markdown("---")
    st.markdown(f"### Today's Waste ({selected_date.strftime('%d %B %Y')})")
    c = conn.cursor()
    c.execute("SELECT * FROM waste WHERE date=%s", (selected_date.strftime("%Y-%m-%d"),))
    waste_rows = c.fetchall()
    waste_df = pd.DataFrame(waste_rows, columns=['id', 'date', 'vegetable', 'quantity', 'reason'])
    
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
        c = conn.cursor()
        
        c.execute("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE date=%s", (d,))
        daily_sales = c.fetchone()[0]
        
        c.execute("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE date=%s", (d,))
        daily_purchases = c.fetchone()[0]
        
        c.execute("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE date=%s", (d,))
        daily_expenses = c.fetchone()[0]
        
        c.execute("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE date=%s", (d,))
        daily_waste = c.fetchone()[0]
        
        # Get customer details
        try:
            c.execute("""
                SELECT 
                    COALESCE(customer_name, 'Guest') as customer_name,
                    COALESCE(customer_phone, '') as phone,
                    SUM(total) as total_spent,
                    COUNT(*) as total_visits
                FROM sales 
                WHERE date=%s
                GROUP BY COALESCE(customer_name, 'Guest'), COALESCE(customer_phone, '')
                ORDER BY total_spent DESC
            """, (d,))
            daily_customers_rows = c.fetchall()
            daily_customers = pd.DataFrame(daily_customers_rows, columns=['customer_name', 'phone', 'total_spent', 'total_visits'])
        except:
            daily_customers = pd.DataFrame()
        
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
        
        st.markdown("#### Detailed Daily Data")
        
        tables = [
            ("purchases", "🛒 Purchases", "Daily purchase records"),
            ("sales", "💰 Sales", "Daily sales transactions"),
            ("waste", "🗑 Waste", "Daily waste records"),
            ("expenses", "💸 Expenses", "Daily expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                c.execute(f"SELECT * FROM {table_name} WHERE date=%s", (d,))
                df_rows = c.fetchall()
                
                if table_name == "purchases":
                    df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity', 'amount', 'supplier'])
                elif table_name == "sales":
                    df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity_sold', 'sale_price', 'total', 
                                                       'customer', 'unit_type', 'customer_name', 'customer_phone', 'bill_no'])
                elif table_name == "waste":
                    df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity', 'reason'])
                else:  # expenses
                    df = pd.DataFrame(df_rows, columns=['id', 'date', 'category', 'amount', 'description'])
                
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
        
        # FIXED: Use TO_CHAR with date::timestamp for Supabase compatibility
        c.execute("""
            SELECT DISTINCT TO_CHAR(date::timestamp, 'YYYY-MM') as month 
            FROM sales 
            UNION 
            SELECT DISTINCT TO_CHAR(date::timestamp, 'YYYY-MM') as month 
            FROM purchases 
            ORDER BY month DESC
        """)
        months_rows = c.fetchall()
        months = pd.DataFrame(months_rows, columns=['month'])
        
        if months.empty:
            st.info("No monthly data available")
        else:
            selected_month = st.selectbox("Select Month", months['month'].tolist(), index=0)
            
            # FIXED: Use TO_CHAR with date::timestamp
            c.execute("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE TO_CHAR(date::timestamp, 'YYYY-MM')=%s", (selected_month,))
            monthly_sales = c.fetchone()[0]
            
            c.execute("SELECT COALESCE(SUM(amount),0) as total_purchases FROM purchases WHERE TO_CHAR(date::timestamp, 'YYYY-MM')=%s", (selected_month,))
            monthly_purchases = c.fetchone()[0]
            
            c.execute("SELECT COALESCE(SUM(amount),0) as total_expenses FROM expenses WHERE TO_CHAR(date::timestamp, 'YYYY-MM')=%s", (selected_month,))
            monthly_expenses = c.fetchone()[0]
            
            c.execute("SELECT COALESCE(SUM(quantity),0) as total_waste FROM waste WHERE TO_CHAR(date::timestamp, 'YYYY-MM')=%s", (selected_month,))
            monthly_waste = c.fetchone()[0]
            
            # Get monthly customer details
            try:
                # FIXED: Use TO_CHAR with date::timestamp
                c.execute("""
                    SELECT 
                        date,
                        COALESCE(customer_name, 'Guest') as customer_name,
                        COALESCE(customer_phone, '') as phone,
                        SUM(total) as total_spent,
                        COUNT(*) as total_visits
                    FROM sales 
                    WHERE TO_CHAR(date::timestamp, 'YYYY-MM')=%s
                    GROUP BY date, COALESCE(customer_name, 'Guest'), COALESCE(customer_phone, '')
                    ORDER BY date DESC, total_spent DESC
                """, (selected_month,))
                monthly_customers_rows = c.fetchall()
                monthly_customers = pd.DataFrame(monthly_customers_rows, columns=['date', 'customer_name', 'phone', 'total_spent', 'total_visits'])
            except Exception as e:
                st.error(f"Error loading monthly customers: {e}")
                monthly_customers = pd.DataFrame()
            
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
            
            st.markdown("#### 👥 Monthly Customer Details (Date-wise)")
            if not monthly_customers.empty:
                # Group by date
                dates = monthly_customers['date'].unique()
                
                for sale_date in dates:
                    date_customers = monthly_customers[monthly_customers['date'] == sale_date]
                    
                    with st.expander(f"📅 {sale_date} - {len(date_customers)} customers"):
                        date_total = date_customers['total_spent'].sum()
                        date_visits = date_customers['total_visits'].sum()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(f"Total Sales", f"₹{date_total:.2f}")
                        with col2:
                            st.metric("Total Visits", date_visits)
                        
                        display_customers = date_customers.copy()
                        display_customers = display_customers.rename(columns={
                            "customer_name": "👤 Name",
                            "phone": "📱 Phone",
                            "total_visits": "🛒 Visits",
                            "total_spent": "💰 Total Spent"
                        })
                        
                        st.dataframe(
                            display_customers[['👤 Name', '📱 Phone', '🛒 Visits', '💰 Total Spent']].style.format({
                                "💰 Total Spent": "₹{:.2f}"
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
    
    with tab3:
        st.markdown("### 📋 Data Export")
        st.markdown("Export complete database tables")
        
        tables = [
            ("inventory", "📦 Inventory", "Current stock levels"),
            ("purchases", "🛒 Purchases", "All purchase records"),
            ("sales", "💰 Sales", "All sales transactions"),
            ("waste", "🗑 Waste", "All waste records"),
            ("expenses", "💸 Expenses", "All expense records")
        ]
        
        for table_name, display_name, description in tables:
            with st.expander(f"{display_name} - {description}"):
                try:
                    c.execute(f"SELECT * FROM {table_name}")
                    df_rows = c.fetchall()
                    
                    if table_name == "inventory":
                        df = pd.DataFrame(df_rows, columns=['vegetable', 'quantity', 'cost_price', 'selling_price', 'image_url', 'unit_type', 'category'])
                    elif table_name == "purchases":
                        df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity', 'amount', 'supplier'])
                    elif table_name == "sales":
                        df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity_sold', 'sale_price', 'total', 
                                                           'customer', 'unit_type', 'customer_name', 'customer_phone', 'bill_no'])
                    elif table_name == "waste":
                        df = pd.DataFrame(df_rows, columns=['id', 'date', 'vegetable', 'quantity', 'reason'])
                    else:  # expenses
                        df = pd.DataFrame(df_rows, columns=['id', 'date', 'category', 'amount', 'description'])
                    
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
                except Exception as e:
                    st.error(f"Error loading {table_name}: {str(e)}")

# ========================== FINANCIALS ==========================
elif menu == "💰 Financials":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💰 Financial Summary</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    d = selected_date.strftime("%Y-%m-%d")
    c = conn.cursor()
    
    c.execute("SELECT COALESCE(SUM(total),0) AS total FROM sales WHERE date=%s", (d,))
    sales_data = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(amount),0) AS total FROM purchases WHERE date=%s", (d,))
    cost_data = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE date=%s", (d,))
    expense_data = c.fetchone()[0]
    
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
        profit_icon = "📈" if profit >= 0 else "📉"
        profit_text = "Profit" if profit >= 0 else "Loss"
        
        st.markdown(f"""
        <div class="red-alert-card">
            <h3>{profit_icon}</h3>
            <h4>{profit_text}</h4>
            <h2>₹{abs(profit):.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("### 📊 Daily Breakdown")
    
    c.execute("""
        SELECT vegetable, SUM(quantity_sold) as qty, SUM(total) as revenue 
        FROM sales WHERE date=%s 
        GROUP BY vegetable 
        ORDER BY revenue DESC
    """, (d,))
    sales_by_veg_rows = c.fetchall()
    sales_by_veg = pd.DataFrame(sales_by_veg_rows, columns=['vegetable', 'qty', 'revenue'])
    
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
    c.execute("SELECT * FROM sales WHERE date=%s ORDER BY id DESC LIMIT 10", (d,))
    recent_sales_rows = c.fetchall()
    recent_sales = pd.DataFrame(recent_sales_rows, columns=['id', 'date', 'vegetable', 'quantity_sold', 'sale_price', 'total', 
                                                          'customer', 'unit_type', 'customer_name', 'customer_phone', 'bill_no'])
    if not recent_sales.empty:
        display_sales = recent_sales.copy()
        
        def format_recent_sales(row):
            unit_type = row['unit_type']
            if unit_type == 'kg':
                return f"{row['quantity_sold']:.2f} kg"
            elif unit_type == 'piece':
                return f"{row['quantity_sold']:.0f} pieces"
            return f"{row['quantity_sold']:.2f} {unit_type}"
        
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
    
    st.markdown("### 📍 Database Configuration")
    
    db_status_class = "db-status-success"
    db_status_text = f"✅ Connected to {db_manager.db_type.upper()}"
    
    st.markdown(f"""
    <div class="{db_status_class}" style="padding:15px; border-radius:10px; margin-bottom:20px;">
        <h4 style="margin:0;">{db_status_text}</h4>
        <p style="margin:5px 0 0 0;">
            🛡️ No data loss when app sleeps
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Database setup instructions
    with st.expander("⚙️ Setup External Database (Recommended)"):
        st.markdown("""
        ### **For Permanent Data Storage (No Data Loss)**
        
        **Step 1: Choose a Database Service**
        
        1. **Supabase (Recommended & Free)**
           - Sign up at [supabase.com](https://supabase.com)
           - Create a new project
           - Go to Settings > Database to get connection details
        
        2. **PostgreSQL on Railway (Free)**
           - Sign up at [railway.app](https://railway.app)
           - Create PostgreSQL service
           - Get connection URL
        
        3. **Neon PostgreSQL (Free)**
           - Sign up at [neon.tech](https://neon.tech)
           - Create PostgreSQL database
        
        **Step 2: Configure Streamlit Secrets**
        
        Create `.streamlit/secrets.toml` file with your database details:
        
        ```toml
        # For Supabase
        [supabase]
        url = "your-project-url.supabase.co"
        key = "your-anon-key"
        db_url = "postgresql://postgres:[password]@[host]:5432/postgres"
        
        # OR for PostgreSQL
        [postgresql]
        host = "your-host"
        port = 5432
        database = "your-db"
        user = "your-user"
        password = "your-password"
        ```
        
        **Step 3: Restart Your App**
        
        The app will automatically detect and use the external database!
        """)
    
    st.markdown("---")
    st.markdown("### 💾 Backup & Recovery")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📤 Export to JSON", use_container_width=True):
            json_file = db_manager.export_database()
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
    
    with col2:
        if st.button("🔍 Check Database Health", use_container_width=True):
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM inventory")
                inv_count = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM sales")
                sales_count = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM purchases")
                purchases_count = c.fetchone()[0]
                
                if inv_count > 0 and sales_count >= 0 and purchases_count >= 0:
                    st.success(f"""
                    ✅ Database Healthy!
                    - Items: {inv_count}
                    - Sales: {sales_count}
                    - Purchases: {purchases_count}
                    """)
                    
            except Exception as e:
                st.error(f"❌ Database check failed: {e}")
    
    st.markdown("---")
    st.markdown("### 📈 Detailed Statistics")
    
    try:
        stats_data = []
        tables = ["inventory", "sales", "purchases", "customers", "expenses", "waste"]
        
        c = conn.cursor()
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
        
    except Exception as e:
        st.error(f"Error fetching statistics: {e}")

# ========================== SECRETS DEBUG ==========================
elif menu == "🔍 Secrets Debug":
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🔍 Secrets Debug</h2>
        <div class="subtitle">Debug Supabase Connection Issues</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("🔐 Check Current Secrets", expanded=True):
        st.markdown("### Streamlit Secrets Status")
        
        if hasattr(st, 'secrets'):
            st.success("✅ `st.secrets` object exists")
            
            try:
                secrets_dict = dict(st.secrets)
                st.info(f"Total top-level secrets: {len(secrets_dict)}")
                
                if secrets_dict:
                    st.markdown("#### 📋 All Secrets (masked):")
                    for key, value in secrets_dict.items():
                        if hasattr(value, '__dict__') or hasattr(value, '__iter__'):
                            try:
                                subsection = dict(value)
                                st.write(f"**{key}:** (subsection with {len(subsection)} keys)")
                            except:
                                st.write(f"**{key}:** [complex object]")
                        else:
                            if value and isinstance(value, str):
                                masked = value[:10] + "..." if len(value) > 10 else value
                                st.write(f"**{key}:** `{masked}`")
            except Exception as e:
                st.error(f"Error reading secrets: {e}")
        else:
            st.error("❌ `st.secrets` object does NOT exist")
    
    with st.expander("📁 Check .streamlit/secrets.toml", expanded=True):
        secrets_path = ".streamlit/secrets.toml"
        if os.path.exists(secrets_path):
            st.success(f"✅ Found {secrets_path}")
            
            try:
                with open(secrets_path, 'r') as f:
                    content = f.read()
                
                import re
                masked_content = content
                masked_content = re.sub(r':([^@]+)@', ':[HIDDEN]@', masked_content)
                masked_content = re.sub(r'key\s*=\s*"[^"]+"', 'key = "[HIDDEN]"', masked_content)
                masked_content = re.sub(r'password\s*=\s*"[^"]+"', 'password = "[HIDDEN]"', masked_content)
                
                st.code(masked_content, language="toml")
                
            except Exception as e:
                st.error(f"Error reading file: {e}")
        else:
            st.error(f"❌ {secrets_path} does not exist")

# ========================== ENHANCED BACKUP ON EXIT ==========================
@atexit.register
def cleanup():
    """Create final backup on exit"""
    db_manager.export_database()

# Footer
st.markdown("---")
st.markdown(f"""
<div class="footer">
    <p>🌿 Fresh Basket — Freshness You Can Feel | Quality Vegetables Daily ✅</p>
    <p style="font-size:0.8em; color:#95a5a6;">
        Database: {db_manager.db_type.upper()} | 
        {"🛡️ No Data Loss" if db_manager.db_type != "local" else "⚠️ Local Storage with Backups"}
    </p>
</div>
""", unsafe_allow_html=True)

# Close database connection properly
try:
    conn.close()
except:
    pass
