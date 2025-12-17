import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timezone, timedelta
import re
import os
import sys
import atexit
import json
import hashlib
import secrets
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
from twilio.rest import Client
import plotly.graph_objects as go
import plotly.express as px
from cryptography.fernet import Fernet
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')
import uuid
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import threading
import csv
import math

# ========================== DATABASE PERSISTENCE SETUP ==========================
if sys.platform == "win32":
    PERSISTENT_DIR = os.path.join(os.environ.get("APPDATA", "."), "FreshBasket")
else:
    PERSISTENT_DIR = os.path.join(os.path.expanduser("~"), ".freshbasket")

os.makedirs(PERSISTENT_DIR, exist_ok=True)

DB_FILE = os.path.join(PERSISTENT_DIR, "shop.db")
BACKUP_FILE = os.path.join(PERSISTENT_DIR, "shop_backup.db")
OFFLINE_FILE = os.path.join(PERSISTENT_DIR, "offline_data.json")

# ========================== SECURITY SETUP ==========================
SECRETS_FILE = os.path.join(PERSISTENT_DIR, "secrets.json")

# Generate or load encryption key
def get_encryption_key():
    key_file = os.path.join(PERSISTENT_DIR, "encryption.key")
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
    return key

ENCRYPTION_KEY = get_encryption_key()
cipher = Fernet(ENCRYPTION_KEY)

# Load or create secrets
def load_secrets():
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_secrets(secrets_data):
    with open(SECRETS_FILE, 'w') as f:
        json.dump(secrets_data, f, indent=2)

secrets_data = load_secrets()

# ========================== DATABASE BACKUP & RECOVERY ==========================
def backup_database():
    try:
        if os.path.exists(DB_FILE):
            import shutil
            shutil.copy2(DB_FILE, BACKUP_FILE)
            return True
    except Exception as e:
        print(f"Backup failed: {e}")
    return False

def restore_database():
    try:
        if os.path.exists(BACKUP_FILE) and not os.path.exists(DB_FILE):
            import shutil
            shutil.copy2(BACKUP_FILE, DB_FILE)
            return True
        elif os.path.exists(BACKUP_FILE) and os.path.getsize(DB_FILE) == 0:
            import shutil
            shutil.copy2(BACKUP_FILE, DB_FILE)
            return True
    except Exception as e:
        print(f"Restore failed: {e}")
    return False

CURRENT_DIR_DB = "shop.db"
if os.path.exists(CURRENT_DIR_DB) and not os.path.exists(DB_FILE):
    import shutil
    shutil.copy2(CURRENT_DIR_DB, DB_FILE)

atexit.register(backup_database)

# ========================== DATABASE CONNECTION ==========================
def get_db_connection():
    try:
        if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
            restore_database()
        
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout = 3000")
        
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        try:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            return conn
        except Exception as e2:
            st.error(f"Could not create database: {e2}")
            return None

conn = get_db_connection()
if conn is None:
    st.error("❌ Critical: Could not initialize database. Please refresh the page.")
    st.stop()

c = conn.cursor()

# ========================== MULTI-USER SYSTEM ==========================
# Create users table
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    role TEXT DEFAULT 'cashier',
    permissions TEXT DEFAULT '[]',
    last_login TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    two_factor_enabled INTEGER DEFAULT 0
)
""")

# Create audit log table
c.execute("""
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT,
    table_name TEXT,
    record_id TEXT,
    old_values TEXT,
    new_values TEXT,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Create user sessions table
c.execute("""
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    login_time TEXT,
    last_activity TEXT,
    ip_address TEXT,
    user_agent TEXT,
    is_active INTEGER DEFAULT 1
)
""")

# Default admin user if not exists
def create_default_admin():
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        # Default password: admin123 (will be hashed)
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("""
            INSERT INTO users (username, password_hash, full_name, role, permissions) 
            VALUES (?, ?, ?, ?, ?)
        """, ('admin', password_hash, 'Administrator', 'admin', '["all"]'))
        conn.commit()

create_default_admin()

# ========================== CREDIT/DEBIT MANAGEMENT ==========================
c.execute("""
CREATE TABLE IF NOT EXISTS credit_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_phone TEXT,
    customer_name TEXT,
    credit_limit REAL DEFAULT 0,
    current_balance REAL DEFAULT 0,
    due_date TEXT,
    last_payment_date TEXT,
    last_payment_amount REAL DEFAULT 0,
    total_credit_given REAL DEFAULT 0,
    total_payments REAL DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS credit_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    transaction_type TEXT, -- 'credit', 'payment', 'adjustment'
    amount REAL,
    previous_balance REAL,
    new_balance REAL,
    reference TEXT, -- sale_id, payment_id, etc.
    description TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES credit_accounts(id)
)
""")

# ========================== BARCODE/QR CODE SUPPORT ==========================
c.execute("""
CREATE TABLE IF NOT EXISTS barcode_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vegetable TEXT UNIQUE,
    barcode TEXT UNIQUE,
    qr_code_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# ========================== MULTIPLE PAYMENT METHODS ==========================
c.execute("""
CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    display_name TEXT,
    is_active INTEGER DEFAULT 1,
    processing_fee REAL DEFAULT 0,
    icon TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Initialize default payment methods
default_payment_methods = [
    ('cash', 'Cash', 1, 0, '💵'),
    ('card', 'Credit/Debit Card', 1, 2.0, '💳'),
    ('upi', 'UPI (PhonePe/GPay/Paytm)', 1, 1.5, '📱'),
    ('netbanking', 'Net Banking', 1, 2.5, '🏦'),
    ('wallet', 'Mobile Wallet', 1, 1.0, '👛'),
    ('credit', 'Store Credit', 1, 0, '📝')
]

for method in default_payment_methods:
    c.execute("""
        INSERT OR IGNORE INTO payment_methods (name, display_name, is_active, processing_fee, icon)
        VALUES (?, ?, ?, ?, ?)
    """, method)

# ========================== AUTOMATED REPORTS ==========================
c.execute("""
CREATE TABLE IF NOT EXISTS report_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT,
    frequency TEXT, -- 'daily', 'weekly', 'monthly'
    delivery_method TEXT, -- 'email', 'whatsapp', 'sms', 'print'
    recipients TEXT, -- JSON array of emails/phones
    next_run TEXT,
    last_run TEXT,
    last_status TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# ========================== ENHANCED SALES TABLE WITH PAYMENT INFO ==========================
# Check if sales table needs upgrade
c.execute("PRAGMA table_info(sales)")
sales_columns = [col[1] for col in c.fetchall()]

if 'payment_method' not in sales_columns:
    try:
        c.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'cash'")
        c.execute("ALTER TABLE sales ADD COLUMN transaction_id TEXT")
        c.execute("ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'completed'")
        c.execute("ALTER TABLE sales ADD COLUMN processed_by TEXT")
        conn.commit()
    except:
        pass

# ========================== NOTIFICATION SYSTEM ==========================
c.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT, -- 'sms', 'whatsapp', 'email', 'system'
    recipient TEXT,
    subject TEXT,
    message TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'sent', 'failed', 'delivered'
    sent_at TEXT,
    delivery_report TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# ========================== OFFLINE MODE DATA ==========================
def save_offline_data(data_type, data):
    """Save data for offline mode"""
    try:
        if os.path.exists(OFFLINE_FILE):
            with open(OFFLINE_FILE, 'r') as f:
                offline_data = json.load(f)
        else:
            offline_data = {}
        
        if data_type not in offline_data:
            offline_data[data_type] = []
        
        offline_data[data_type].append({
            'timestamp': datetime.now().isoformat(),
            'data': data
        })
        
        # Keep only last 1000 entries per type
        if len(offline_data[data_type]) > 1000:
            offline_data[data_type] = offline_data[data_type][-1000:]
        
        with open(OFFLINE_FILE, 'w') as f:
            json.dump(offline_data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving offline data: {e}")
        return False

def load_offline_data(data_type):
    """Load offline data"""
    try:
        if os.path.exists(OFFLINE_FILE):
            with open(OFFLINE_FILE, 'r') as f:
                offline_data = json.load(f)
            return offline_data.get(data_type, [])
        return []
    except:
        return []

def sync_offline_data():
    """Sync offline data with database"""
    try:
        if not os.path.exists(OFFLINE_FILE):
            return True
        
        with open(OFFLINE_FILE, 'r') as f:
            offline_data = json.load(f)
        
        # Sync sales data
        if 'sales' in offline_data:
            for sale in offline_data['sales']:
                try:
                    # Process each offline sale
                    sale_data = sale['data']
                    # Add to database
                    c.execute("""
                        INSERT INTO sales (date, vegetable, quantity_sold, sale_price, total, 
                                         customer, unit_type, payment_method, transaction_id, 
                                         payment_status, processed_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sale_data.get('date'),
                        sale_data.get('vegetable'),
                        sale_data.get('quantity_sold'),
                        sale_data.get('sale_price'),
                        sale_data.get('total'),
                        sale_data.get('customer'),
                        sale_data.get('unit_type', 'kg'),
                        sale_data.get('payment_method', 'cash'),
                        sale_data.get('transaction_id'),
                        sale_data.get('payment_status', 'completed'),
                        sale_data.get('processed_by')
                    ))
                    # Update inventory
                    c.execute("""
                        UPDATE inventory 
                        SET quantity = quantity - ? 
                        WHERE vegetable = ?
                    """, (sale_data.get('quantity_sold'), sale_data.get('vegetable')))
                except Exception as e:
                    print(f"Error syncing sale: {e}")
        
        # Clear synced data
        offline_data = {}
        with open(OFFLINE_FILE, 'w') as f:
            json.dump(offline_data, f, indent=2)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error syncing offline data: {e}")
        return False

# ========================== SMS/WHATSAPP NOTIFICATIONS ==========================
class NotificationManager:
    def __init__(self):
        self.twilio_account_sid = secrets_data.get('twilio_account_sid', '')
        self.twilio_auth_token = secrets_data.get('twilio_auth_token', '')
        self.twilio_phone_number = secrets_data.get('twilio_phone_number', '')
        self.twilio_whatsapp_number = secrets_data.get('twilio_whatsapp_number', '')
        
    def send_sms(self, to_phone, message):
        """Send SMS notification"""
        try:
            if not self.twilio_account_sid or not self.twilio_auth_token:
                return {"success": False, "message": "Twilio credentials not configured"}
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            message = client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=to_phone
            )
            
            # Log notification
            c.execute("""
                INSERT INTO notifications (notification_type, recipient, message, status, sent_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('sms', to_phone, message, 'sent', datetime.now().isoformat()))
            conn.commit()
            
            return {"success": True, "message_sid": message.sid}
        except Exception as e:
            c.execute("""
                INSERT INTO notifications (notification_type, recipient, message, status, delivery_report)
                VALUES (?, ?, ?, ?, ?)
            """, ('sms', to_phone, message, 'failed', str(e)))
            conn.commit()
            return {"success": False, "error": str(e)}
    
    def send_whatsapp(self, to_phone, message):
        """Send WhatsApp notification"""
        try:
            if not self.twilio_account_sid or not self.twilio_auth_token:
                return {"success": False, "message": "Twilio credentials not configured"}
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            message = client.messages.create(
                body=message,
                from_=f'whatsapp:{self.twilio_whatsapp_number}',
                to=f'whatsapp:{to_phone}'
            )
            
            # Log notification
            c.execute("""
                INSERT INTO notifications (notification_type, recipient, message, status, sent_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('whatsapp', to_phone, message, 'sent', datetime.now().isoformat()))
            conn.commit()
            
            return {"success": True, "message_sid": message.sid}
        except Exception as e:
            c.execute("""
                INSERT INTO notifications (notification_type, recipient, message, status, delivery_report)
                VALUES (?, ?, ?, ?, ?)
            """, ('whatsapp', to_phone, message, 'failed', str(e)))
            conn.commit()
            return {"success": False, "error": str(e)}
    
    def send_customer_notification(self, customer_phone, notification_type, data):
        """Send notification to customer"""
        if not customer_phone:
            return {"success": False, "message": "No phone number provided"}
        
        templates = {
            'order_confirmation': f"✅ Order confirmed! Bill No: {data.get('bill_no')}, Amount: ₹{data.get('amount')}. Thank you for shopping at Fresh Basket!",
            'payment_received': f"💰 Payment received! Amount: ₹{data.get('amount')}, Balance: ₹{data.get('balance')}. Thank you!",
            'credit_limit': f"⚠️ Credit limit alert! Your current balance: ₹{data.get('balance')}, Limit: ₹{data.get('limit')}. Please make payment.",
            'low_stock': f"📦 Low stock alert! {data.get('item')} is running low. Current stock: {data.get('stock')}",
            'special_offer': f"🎉 Special offer! {data.get('offer')}. Valid until {data.get('valid_until')}"
        }
        
        message = templates.get(notification_type, data.get('message', ''))
        
        # Try WhatsApp first, then SMS
        result = self.send_whatsapp(customer_phone, message)
        if not result['success']:
            result = self.send_sms(customer_phone, message)
        
        return result

notification_manager = NotificationManager()

# ========================== BARCODE/QR CODE GENERATOR ==========================
class BarcodeManager:
    @staticmethod
    def generate_barcode(item_name, item_id=None):
        """Generate barcode for an item"""
        try:
            if not item_id:
                item_id = str(uuid.uuid4().int)[:8]
            
            # Create barcode
            code128 = barcode.get_barcode_class('code128')
            barcode_obj = code128(item_id, writer=ImageWriter())
            
            # Save to file
            barcode_dir = os.path.join(PERSISTENT_DIR, 'barcodes')
            os.makedirs(barcode_dir, exist_ok=True)
            
            filename = f"{item_name.replace(' ', '_')}_{item_id}"
            filepath = os.path.join(barcode_dir, filename)
            barcode_obj.save(filepath)
            
            # Save to database
            c.execute("""
                INSERT OR REPLACE INTO barcode_mapping (vegetable, barcode, qr_code_path)
                VALUES (?, ?, ?)
            """, (item_name, item_id, f"{filepath}.png"))
            conn.commit()
            
            return {"success": True, "barcode": item_id, "filepath": f"{filepath}.png"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def generate_qr_code(data, item_name):
        """Generate QR code for an item"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to file
            qr_dir = os.path.join(PERSISTENT_DIR, 'qrcodes')
            os.makedirs(qr_dir, exist_ok=True)
            
            filename = f"{item_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath)
            
            return {"success": True, "filepath": filepath, "filename": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_barcode(item_name):
        """Get barcode for an item"""
        try:
            c.execute("SELECT barcode, qr_code_path FROM barcode_mapping WHERE vegetable = ?", (item_name,))
            result = c.fetchone()
            if result:
                return {"success": True, "barcode": result[0], "qr_code_path": result[1]}
            else:
                # Generate new barcode
                return BarcodeManager.generate_barcode(item_name)
        except Exception as e:
            return {"success": False, "error": str(e)}

barcode_manager = BarcodeManager()

# ========================== ADVANCED ANALYTICS ==========================
class AdvancedAnalytics:
    @staticmethod
    def calculate_profit_margin(selling_price, cost_price):
        """Calculate profit margin percentage"""
        if cost_price == 0:
            return 0
        profit = selling_price - cost_price
        margin = (profit / selling_price) * 100
        return round(margin, 2)
    
    @staticmethod
    def get_daily_profit_analysis(date_str=None):
        """Get detailed daily profit analysis"""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Get sales data
        sales_df = pd.read_sql("""
            SELECT s.*, i.cost_price 
            FROM sales s
            LEFT JOIN inventory i ON s.vegetable = i.vegetable
            WHERE s.date = ?
        """, conn, params=(date_str,))
        
        if sales_df.empty:
            return {"total_sales": 0, "total_cost": 0, "total_profit": 0, "margin_percentage": 0}
        
        # Calculate profit
        sales_df['cost'] = sales_df['quantity_sold'] * sales_df['cost_price']
        sales_df['profit'] = sales_df['total'] - sales_df['cost']
        
        total_sales = sales_df['total'].sum()
        total_cost = sales_df['cost'].sum()
        total_profit = total_sales - total_cost
        margin_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0
        
        # Get top profitable items
        top_items = sales_df.groupby('vegetable').agg({
            'total': 'sum',
            'profit': 'sum',
            'quantity_sold': 'sum'
        }).sort_values('profit', ascending=False).head(10)
        
        return {
            "date": date_str,
            "total_sales": round(total_sales, 2),
            "total_cost": round(total_cost, 2),
            "total_profit": round(total_profit, 2),
            "margin_percentage": round(margin_percentage, 2),
            "top_items": top_items.to_dict('records')
        }
    
    @staticmethod
    def get_sales_forecast():
        """Get sales forecast for next 7 days"""
        try:
            # Get historical sales data
            sales_df = pd.read_sql("""
                SELECT date, SUM(total) as daily_sales
                FROM sales
                WHERE date >= date('now', '-30 days')
                GROUP BY date
                ORDER BY date
            """, conn)
            
            if len(sales_df) < 7:
                return {"forecast": [], "accuracy": "Low (insufficient data)"}
            
            # Prepare data for forecasting
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            sales_df['day_num'] = (sales_df['date'] - sales_df['date'].min()).dt.days
            
            # Simple linear regression forecast
            X = sales_df['day_num'].values.reshape(-1, 1)
            y = sales_df['daily_sales'].values
            
            model = LinearRegression()
            model.fit(X, y)
            
            # Forecast next 7 days
            last_day = sales_df['day_num'].max()
            future_days = np.array(range(last_day + 1, last_day + 8)).reshape(-1, 1)
            forecast = model.predict(future_days)
            
            # Create forecast dates
            forecast_dates = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 8)]
            
            forecast_data = []
            for i in range(7):
                forecast_data.append({
                    "date": forecast_dates[i],
                    "forecast_sales": round(forecast[i], 2),
                    "confidence": "Medium"
                })
            
            return {
                "forecast": forecast_data,
                "accuracy": "Medium",
                "next_7_days_total": round(sum(forecast), 2)
            }
        except Exception as e:
            return {"forecast": [], "accuracy": "Error", "error": str(e)}
    
    @staticmethod
    def get_customer_analytics():
        """Get customer analytics and segmentation"""
        try:
            # Get customer data
            customers_df = pd.read_sql("""
                SELECT customer, SUM(total) as total_spent, COUNT(*) as transaction_count,
                       MAX(date) as last_purchase, MIN(date) as first_purchase
                FROM sales
                WHERE customer NOT LIKE 'Guest%'
                GROUP BY customer
                ORDER BY total_spent DESC
            """, conn)
            
            if customers_df.empty:
                return {"total_customers": 0, "segments": {}}
            
            # Customer segmentation
            segments = {
                "vip": customers_df[customers_df['total_spent'] > 10000],
                "regular": customers_df[(customers_df['total_spent'] > 1000) & (customers_df['total_spent'] <= 10000)],
                "occasional": customers_df[customers_df['total_spent'] <= 1000]
            }
            
            segment_stats = {}
            for segment_name, segment_df in segments.items():
                if not segment_df.empty:
                    segment_stats[segment_name] = {
                        "count": len(segment_df),
                        "avg_spent": round(segment_df['total_spent'].mean(), 2),
                        "total_spent": round(segment_df['total_spent'].sum(), 2)
                    }
            
            return {
                "total_customers": len(customers_df),
                "total_revenue_from_customers": round(customers_df['total_spent'].sum(), 2),
                "avg_customer_value": round(customers_df['total_spent'].mean(), 2),
                "segments": segment_stats,
                "top_customers": customers_df.head(10).to_dict('records')
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def get_inventory_analytics():
        """Get inventory analytics"""
        try:
            inventory_df = pd.read_sql("""
                SELECT i.*, 
                       COALESCE(SUM(s.quantity_sold), 0) as total_sold,
                       COALESCE(SUM(s.total), 0) as revenue_generated
                FROM inventory i
                LEFT JOIN sales s ON i.vegetable = s.vegetable AND s.date >= date('now', '-30 days')
                GROUP BY i.vegetable
                ORDER BY i.quantity DESC
            """, conn)
            
            if inventory_df.empty:
                return {"total_items": 0, "valuation": 0}
            
            # Calculate inventory valuation
            inventory_df['valuation'] = inventory_df['quantity'] * inventory_df['cost_price']
            total_valuation = inventory_df['valuation'].sum()
            
            # Calculate turnover
            inventory_df['turnover_rate'] = np.where(
                inventory_df['quantity'] > 0,
                inventory_df['total_sold'] / inventory_df['quantity'],
                0
            )
            
            # Identify slow moving items
            slow_moving = inventory_df[
                (inventory_df['quantity'] > 0) & 
                (inventory_df['turnover_rate'] < 0.1)
            ]
            
            # Identify dead stock (no sales in 30 days but has stock)
            dead_stock = inventory_df[
                (inventory_df['quantity'] > 0) & 
                (inventory_df['total_sold'] == 0)
            ]
            
            return {
                "total_items": len(inventory_df),
                "total_valuation": round(total_valuation, 2),
                "avg_margin": round(inventory_df.apply(
                    lambda row: AdvancedAnalytics.calculate_profit_margin(row['selling_price'], row['cost_price']), 
                    axis=1
                ).mean(), 2),
                "slow_moving_count": len(slow_moving),
                "dead_stock_count": len(dead_stock),
                "top_items_by_value": inventory_df.nlargest(10, 'valuation')[['vegetable', 'quantity', 'valuation']].to_dict('records'),
                "top_items_by_turnover": inventory_df.nlargest(10, 'turnover_rate')[['vegetable', 'turnover_rate', 'total_sold']].to_dict('records')
            }
        except Exception as e:
            return {"error": str(e)}

analytics = AdvancedAnalytics()

# ========================== AUTOMATED REPORTS SYSTEM ==========================
class ReportGenerator:
    @staticmethod
    def generate_daily_report(date_str=None):
        """Generate daily sales report"""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Get daily data
        daily_data = analytics.get_daily_profit_analysis(date_str)
        
        # Get sales details
        sales_df = pd.read_sql("""
            SELECT s.*, i.cost_price, 
                   (s.total - (s.quantity_sold * i.cost_price)) as profit
            FROM sales s
            LEFT JOIN inventory i ON s.vegetable = i.vegetable
            WHERE s.date = ?
            ORDER BY s.total DESC
        """, conn, params=(date_str,))
        
        # Get payment method breakdown
        payment_df = pd.read_sql("""
            SELECT payment_method, COUNT(*) as transactions, SUM(total) as amount
            FROM sales
            WHERE date = ?
            GROUP BY payment_method
            ORDER BY amount DESC
        """, conn, params=(date_str,))
        
        report = {
            "report_date": date_str,
            "generated_at": datetime.now().isoformat(),
            "summary": daily_data,
            "total_transactions": len(sales_df),
            "payment_breakdown": payment_df.to_dict('records'),
            "top_selling_items": sales_df.head(10).to_dict('records'),
            "customer_count": sales_df['customer'].nunique()
        }
        
        return report
    
    @staticmethod
    def generate_weekly_report(start_date=None):
        """Generate weekly report"""
        if not start_date:
            # Start from Monday of current week
            today = datetime.now()
            start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        
        end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
        
        # Get weekly sales data
        weekly_df = pd.read_sql("""
            SELECT date, SUM(total) as daily_sales, COUNT(*) as transactions
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, conn, params=(start_date, end_date))
        
        # Get weekly summary
        summary_df = pd.read_sql("""
            SELECT 
                SUM(total) as total_sales,
                COUNT(*) as total_transactions,
                COUNT(DISTINCT customer) as unique_customers,
                AVG(total) as avg_transaction_value
            FROM sales
            WHERE date BETWEEN ? AND ?
        """, conn, params=(start_date, end_date))
        
        # Get top items
        top_items_df = pd.read_sql("""
            SELECT vegetable, SUM(quantity_sold) as total_quantity, SUM(total) as total_revenue
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY vegetable
            ORDER BY total_revenue DESC
            LIMIT 10
        """, conn, params=(start_date, end_date))
        
        report = {
            "period": f"{start_date} to {end_date}",
            "generated_at": datetime.now().isoformat(),
            "daily_sales": weekly_df.to_dict('records'),
            "summary": summary_df.iloc[0].to_dict() if not summary_df.empty else {},
            "top_items": top_items_df.to_dict('records'),
            "week_number": datetime.strptime(start_date, "%Y-%m-%d").isocalendar()[1]
        }
        
        return report
    
    @staticmethod
    def generate_monthly_report(month=None, year=None):
        """Generate monthly report"""
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
        
        month_str = f"{year}-{month:02d}"
        
        # Get monthly data
        monthly_df = pd.read_sql("""
            SELECT 
                date,
                SUM(total) as daily_sales,
                COUNT(*) as transactions
            FROM sales
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY date
            ORDER BY date
        """, conn, params=(month_str,))
        
        # Get monthly summary
        summary_df = pd.read_sql("""
            SELECT 
                SUM(total) as total_sales,
                COUNT(*) as total_transactions,
                COUNT(DISTINCT customer) as unique_customers,
                AVG(total) as avg_transaction_value,
                MIN(total) as min_transaction,
                MAX(total) as max_transaction
            FROM sales
            WHERE strftime('%Y-%m', date) = ?
        """, conn, params=(month_str,))
        
        # Get category performance
        category_df = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN vegetable IN ('Tomato', 'Onion', 'Potato') THEN 'Staples'
                    WHEN vegetable LIKE '%Leaf%' OR vegetable LIKE '%Green%' THEN 'Leafy Vegetables'
                    WHEN vegetable LIKE '%Fruit%' OR vegetable IN ('Apple', 'Banana', 'Orange') THEN 'Fruits'
                    ELSE 'Others'
                END as category,
                SUM(total) as revenue,
                SUM(quantity_sold) as quantity
            FROM sales
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY category
            ORDER BY revenue DESC
        """, conn, params=(month_str,))
        
        report = {
            "month": month_str,
            "generated_at": datetime.now().isoformat(),
            "daily_performance": monthly_df.to_dict('records'),
            "summary": summary_df.iloc[0].to_dict() if not summary_df.empty else {},
            "category_performance": category_df.to_dict('records'),
            "days_with_sales": len(monthly_df),
            "best_day": monthly_df.loc[monthly_df['daily_sales'].idxmax()].to_dict() if not monthly_df.empty else {}
        }
        
        return report
    
    @staticmethod
    def export_report_to_csv(report_data, report_type):
        """Export report to CSV"""
        try:
            reports_dir = os.path.join(PERSISTENT_DIR, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(reports_dir, filename)
            
            # Convert report data to DataFrame and save as CSV
            if report_type == 'daily':
                df = pd.DataFrame(report_data.get('top_selling_items', []))
            elif report_type == 'weekly':
                df = pd.DataFrame(report_data.get('daily_sales', []))
            elif report_type == 'monthly':
                df = pd.DataFrame(report_data.get('daily_performance', []))
            else:
                df = pd.DataFrame([report_data.get('summary', {})])
            
            if not df.empty:
                df.to_csv(filepath, index=False)
                return {"success": True, "filepath": filepath, "filename": filename}
            else:
                return {"success": False, "error": "No data to export"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def schedule_report(report_type, frequency, delivery_method, recipients):
        """Schedule automated report generation"""
        try:
            # Calculate next run time
            now = datetime.now()
            if frequency == 'daily':
                next_run = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            elif frequency == 'weekly':
                # Next Monday at 8 AM
                days_ahead = 7 - now.weekday()
                next_run = (now + timedelta(days=days_ahead)).replace(hour=8, minute=0, second=0, microsecond=0)
            elif frequency == 'monthly':
                # First day of next month at 8 AM
                if now.month == 12:
                    next_month = now.replace(year=now.year+1, month=1, day=1)
                else:
                    next_month = now.replace(month=now.month+1, day=1)
                next_run = next_month.replace(hour=8, minute=0, second=0, microsecond=0)
            else:
                next_run = now + timedelta(days=1)
            
            c.execute("""
                INSERT INTO report_schedules 
                (report_type, frequency, delivery_method, recipients, next_run, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (report_type, frequency, delivery_method, json.dumps(recipients), next_run.isoformat()))
            conn.commit()
            
            return {"success": True, "next_run": next_run.isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e)}

report_generator = ReportGenerator()

# ========================== REAL-TIME NOTIFICATIONS ==========================
def send_real_time_notification(user_id, message, notification_type='system'):
    """Send real-time notification to user"""
    try:
        # Store notification in database
        c.execute("""
            INSERT INTO notifications (notification_type, recipient, message, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (notification_type, f"user:{user_id}", message, 'pending', datetime.now().isoformat()))
        conn.commit()
        
        # Here you would integrate with WebSocket or polling mechanism
        # For now, we'll just store it and show in UI
        
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

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
    .subtitle {text-align:center; color:#27ae60; font-size:1.2em; margin-bottom:30px; font-weight:500;}
    
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
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.25em 0.6em;
        font-size: 75%;
        font-weight: 700;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 10px;
        margin: 2px;
    }
    
    .badge-success {
        background-color: #28a745;
        color: white;
    }
    
    .badge-warning {
        background-color: #ffc107;
        color: #212529;
    }
    
    .badge-danger {
        background-color: #dc3545;
        color: white;
    }
    
    .badge-info {
        background-color: #17a2b8;
        color: white;
    }
    
    /* Notification badge */
    .notification-badge {
        position: absolute;
        top: -5px;
        right: -5px;
        background: #e74c3c;
        color: white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        font-size: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# ========================== SESSION STATE INITIALIZATION ==========================
if 'user' not in st.session_state:
    st.session_state.user = None
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'shortage_threshold' not in st.session_state:
    st.session_state.shortage_threshold = 5.0
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = date.today()
if 'last_sale' not in st.session_state:
    st.session_state.last_sale = None
if 'guest_counter' not in st.session_state:
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
if 'offline_mode' not in st.session_state:
    st.session_state.offline_mode = False
if 'notifications' not in st.session_state:
    st.session_state.notifications = []
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Login"

# ========================== AUTHENTICATION FUNCTIONS ==========================
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed

def login_user(username, password):
    """Authenticate user"""
    try:
        c.execute("SELECT id, username, password_hash, full_name, role FROM users WHERE username = ? AND is_active = 1", (username,))
        user = c.fetchone()
        
        if user and verify_password(password, user[2]):
            # Update last login
            c.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user[0]))
            conn.commit()
            
            # Create session
            session_id = str(uuid.uuid4())
            
            st.session_state.user = {
                'id': user[0],
                'username': user[1],
                'full_name': user[3],
                'role': user[4],
                'session_id': session_id
            }
            
            # Log audit
            log_audit(user[0], user[1], 'login', 'users', str(user[0]), '', 'User logged in')
            
            return True
        return False
    except Exception as e:
        st.error(f"Login error: {e}")
        return False

def logout_user():
    """Logout current user"""
    if st.session_state.user:
        log_audit(
            st.session_state.user['id'],
            st.session_state.user['username'],
            'logout',
            'users',
            str(st.session_state.user['id']),
            '',
            'User logged out'
        )
    st.session_state.user = None
    st.session_state.current_page = "Login"

def check_permission(required_permission):
    """Check if current user has required permission"""
    if not st.session_state.user:
        return False
    
    # Admin has all permissions
    if st.session_state.user['role'] == 'admin':
        return True
    
    # For now, allow all authenticated users
    # TODO: Implement granular permissions
    return True

def log_audit(user_id, username, action, table_name, record_id, old_values, new_values):
    """Log audit trail"""
    try:
        c.execute("""
            INSERT INTO audit_log 
            (user_id, username, action, table_name, record_id, old_values, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, action, table_name, record_id, old_values, new_values, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        print(f"Audit log error: {e}")

# ========================== HELPER FUNCTIONS ==========================
def get_stock(veg):
    """Return (quantity, cost_price, selling_price, unit_type) for veg (or zeros)."""
    try:
        c.execute("SELECT quantity, cost_price, selling_price, unit_type FROM inventory WHERE vegetable=?", (veg,))
        row = c.fetchone()
        if row:
            qty = row[0] if row[0] is not None else 0.0
            cost = row[1] if row[1] is not None else 0.0
            sell = row[2] if row[2] is not None else 0.0
            unit_type = row[3] if row[3] is not None else 'kg'
            return qty, cost, sell, unit_type
    except Exception as e:
        pass
    return 0.0, 0.0, 0.0, 'kg'

def get_ist_time():
    """Get current IST time"""
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime("%H:%M:%S")

# ========================== CREDIT/DEBIT MANAGEMENT FUNCTIONS ==========================
def create_credit_account(customer_phone, customer_name, credit_limit=0):
    """Create or update credit account for customer"""
    try:
        c.execute("""
            INSERT OR REPLACE INTO credit_accounts 
            (customer_phone, customer_name, credit_limit, current_balance, status)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_phone, customer_name, credit_limit, 0, 'active'))
        conn.commit()
        
        account_id = c.lastrowid
        log_audit(
            st.session_state.user['id'] if st.session_state.user else 0,
            st.session_state.user['username'] if st.session_state.user else 'system',
            'create_credit_account',
            'credit_accounts',
            str(account_id),
            '',
            json.dumps({'customer_phone': customer_phone, 'credit_limit': credit_limit})
        )
        
        return {"success": True, "account_id": account_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_credit_transaction(account_id, transaction_type, amount, description, reference=None):
    """Add credit transaction"""
    try:
        # Get current balance
        c.execute("SELECT current_balance FROM credit_accounts WHERE id = ?", (account_id,))
        result = c.fetchone()
        if not result:
            return {"success": False, "error": "Account not found"}
        
        previous_balance = result[0]
        
        if transaction_type == 'credit':
            new_balance = previous_balance + amount
        elif transaction_type == 'payment':
            new_balance = previous_balance - amount
        elif transaction_type == 'adjustment':
            new_balance = previous_balance + amount
        else:
            return {"success": False, "error": "Invalid transaction type"}
        
        # Update account balance
        c.execute("""
            UPDATE credit_accounts 
            SET current_balance = ?,
                last_payment_date = CASE WHEN ? = 'payment' THEN ? ELSE last_payment_date END,
                last_payment_amount = CASE WHEN ? = 'payment' THEN ? ELSE last_payment_amount END,
                total_credit_given = total_credit_given + CASE WHEN ? = 'credit' THEN ? ELSE 0 END,
                total_payments = total_payments + CASE WHEN ? = 'payment' THEN ? ELSE 0 END
            WHERE id = ?
        """, (
            new_balance,
            transaction_type, datetime.now().isoformat(),
            transaction_type, amount,
            transaction_type, amount,
            transaction_type, amount,
            account_id
        ))
        
        # Add transaction record
        c.execute("""
            INSERT INTO credit_transactions 
            (account_id, transaction_type, amount, previous_balance, new_balance, reference, description, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            transaction_type,
            amount,
            previous_balance,
            new_balance,
            reference,
            description,
            st.session_state.user['username'] if st.session_state.user else 'system'
        ))
        
        conn.commit()
        
        # Log audit
        log_audit(
            st.session_state.user['id'] if st.session_state.user else 0,
            st.session_state.user['username'] if st.session_state.user else 'system',
            f'credit_{transaction_type}',
            'credit_transactions',
            str(c.lastrowid),
            json.dumps({'previous_balance': previous_balance}),
            json.dumps({'new_balance': new_balance, 'amount': amount})
        )
        
        return {"success": True, "new_balance": new_balance}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_credit_account(customer_phone):
    """Get credit account for customer"""
    try:
        c.execute("""
            SELECT * FROM credit_accounts 
            WHERE customer_phone = ? AND status = 'active'
        """, (customer_phone,))
        account = c.fetchone()
        
        if account:
            # Get recent transactions
            c.execute("""
                SELECT * FROM credit_transactions 
                WHERE account_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (account[0],))
            transactions = c.fetchall()
            
            return {
                "success": True,
                "account": {
                    "id": account[0],
                    "customer_phone": account[1],
                    "customer_name": account[2],
                    "credit_limit": account[3],
                    "current_balance": account[4],
                    "due_date": account[5],
                    "last_payment_date": account[6],
                    "last_payment_amount": account[7],
                    "total_credit_given": account[8],
                    "total_payments": account[9],
                    "status": account[10]
                },
                "transactions": [
                    {
                        "id": t[0],
                        "transaction_type": t[2],
                        "amount": t[3],
                        "previous_balance": t[4],
                        "new_balance": t[5],
                        "description": t[7],
                        "created_at": t[9]
                    } for t in transactions
                ]
            }
        else:
            return {"success": False, "error": "No active credit account found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ========================== PAYMENT PROCESSING ==========================
def process_payment(total_amount, payment_method, customer_phone=None, credit_account_id=None):
    """Process payment with multiple methods"""
    try:
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        if payment_method == 'credit' and credit_account_id:
            # Check credit account
            account_info = get_credit_account(customer_phone)
            if not account_info['success']:
                return {"success": False, "error": "No valid credit account"}
            
            account = account_info['account']
            if account['current_balance'] + total_amount > account['credit_limit']:
                return {"success": False, "error": "Credit limit exceeded"}
            
            # Add credit transaction
            result = add_credit_transaction(
                credit_account_id,
                'credit',
                total_amount,
                f'Sale transaction {transaction_id}',
                transaction_id
            )
            
            if not result['success']:
                return result
            
            payment_status = 'completed'
            
        elif payment_method in ['cash', 'card', 'upi', 'netbanking', 'wallet']:
            # Process regular payment
            # In a real app, integrate with payment gateway here
            payment_status = 'completed'
            
            # Simulate payment processing
            time.sleep(0.5)  # Simulate processing delay
            
        else:
            return {"success": False, "error": "Invalid payment method"}
        
        # Get processing fee
        c.execute("SELECT processing_fee FROM payment_methods WHERE name = ?", (payment_method,))
        fee_result = c.fetchone()
        processing_fee = fee_result[0] if fee_result else 0
        
        # Calculate net amount
        net_amount = total_amount - (total_amount * processing_fee / 100)
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "payment_status": payment_status,
            "processing_fee": processing_fee,
            "net_amount": round(net_amount, 2),
            "payment_method": payment_method
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ========================== LOGIN PAGE ==========================
def show_login_page():
    """Display login page"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:50px;">
        <h1>🌿 Fresh Basket</h1>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.markdown("### 🔐 Login")
            
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col_a, col_b = st.columns(2)
            with col_a:
                login_button = st.form_submit_button("Login", type="primary", use_container_width=True)
            with col_b:
                offline_button = st.form_submit_button("Offline Mode", use_container_width=True)
            
            if login_button:
                if username and password:
                    with st.spinner("Authenticating..."):
                        if login_user(username, password):
                            st.success("Login successful! Redirecting...")
                            time.sleep(1)
                            st.session_state.current_page = "Dashboard"
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                else:
                    st.error("Please enter username and password")
            
            if offline_button:
                st.session_state.offline_mode = True
                st.session_state.current_page = "Dashboard"
                st.info("Entering offline mode. Data will be synced when online.")
                time.sleep(1)
                st.rerun()
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align:center; color:#7f8c8d; font-size:0.9em;">
            <p>Default admin credentials:</p>
            <p><strong>Username:</strong> admin</p>
            <p><strong>Password:</strong> admin123</p>
        </div>
        """, unsafe_allow_html=True)

# ========================== MAIN APPLICATION ==========================
def main_app():
    """Main application after login"""
    
    # ========================== SIDEBAR ==========================
    with st.sidebar:
        if st.session_state.user:
            user_display = st.session_state.user['full_name'] or st.session_state.user['username']
            role_display = st.session_state.user['role'].title()
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); 
                        padding:20px; border-radius:15px; margin-bottom:20px;">
                <div style="text-align:center; color:white;">
                    <h3 style="margin:0;">👤 {user_display}</h3>
                    <p style="margin:5px 0 0 0; font-size:0.9em; color:#ecf0f1;">{role_display}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.offline_mode:
                st.warning("⚠️ Offline Mode Active")
                if st.button("🔗 Sync Now", use_container_width=True):
                    with st.spinner("Syncing data..."):
                        if sync_offline_data():
                            st.success("Data synced successfully!")
                            st.session_state.offline_mode = False
                        else:
                            st.error("Sync failed. Still in offline mode.")
        
        st.markdown("### 📋 Navigation")
        
        menu_options = ["📊 Dashboard", "🛒 Add Purchase", "🏷 Set Prices", "💵 Quick Sell", 
                       "📦 Inventory", "📋 Purchases", "🧾 Sales", "💸 Expenses", 
                       "👥 Customers", "🗑 Waste", "⬇ Download", "💰 Financials"]
        
        # Add admin options
        if st.session_state.user and st.session_state.user['role'] == 'admin':
            menu_options.extend(["👥 User Management", "📈 Advanced Analytics", "🔔 Notifications", 
                               "💳 Credit Accounts", "⚙️ Settings"])
        
        menu = st.selectbox(
            "",
            menu_options,
            label_visibility="collapsed",
            key="main_menu_select"
        )
        
        st.markdown("---")
        
        # Date selector
        st.markdown("### 📅 Select Date")
        selected_date = st.date_input("", value=st.session_state.selected_date, key="date_selector")
        st.session_state.selected_date = selected_date
        
        st.markdown(f"""
        <div class="card" style="margin-top:15px; padding:15px; text-align:center;">
            <h4 style="color:#27ae60;">Selected Date</h4>
            <h3 style="color:#2c3e50;">{selected_date.strftime('%d %B %Y')}</h3>
        </div>
        """, unsafe_allow_html=True)
        
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
        
        # Notification center
        if st.session_state.user:
            st.markdown("---")
            st.markdown("### 🔔 Notifications")
            
            # Get unread notifications
            c.execute("""
                SELECT COUNT(*) FROM notifications 
                WHERE recipient LIKE ? AND status = 'pending'
            """, (f"user:{st.session_state.user['id']}%",))
            unread_count = c.fetchone()[0]
            
            if unread_count > 0:
                st.markdown(f"""
                <div style="background: #e74c3c; color: white; padding: 10px; 
                            border-radius: 10px; text-align: center; margin-bottom: 10px;">
                    <strong>{unread_count} unread notifications</strong>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("View All Notifications", use_container_width=True):
                st.session_state.current_page = "Notifications"
                st.rerun()
        
        # Logout button
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()
    
    # ========================== DASHBOARD ==========================
    if menu == "📊 Dashboard":
        show_dashboard()
    
    # ========================== USER MANAGEMENT (Admin only) ==========================
    elif menu == "👥 User Management" and st.session_state.user and st.session_state.user['role'] == 'admin':
        show_user_management()
    
    # ========================== ADVANCED ANALYTICS ==========================
    elif menu == "📈 Advanced Analytics":
        show_advanced_analytics()
    
    # ========================== NOTIFICATIONS ==========================
    elif menu == "🔔 Notifications":
        show_notifications()
    
    # ========================== CREDIT ACCOUNTS ==========================
    elif menu == "💳 Credit Accounts":
        show_credit_accounts()
    
    # ========================== SETTINGS ==========================
    elif menu == "⚙️ Settings":
        show_settings()
    
    # ========================== EXISTING PAGES ==========================
    else:
        # Redirect to existing pages (simplified for this example)
        # In a full implementation, you would call the existing functions
        show_existing_page(menu)

# ========================== NEW FEATURE PAGES ==========================
def show_dashboard():
    """Enhanced dashboard with new features"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📊 Dashboard Overview</h2>
        <div class="subtitle">Freshness You Can Feel</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Today's Sales
        today_sales = pd.read_sql("""
            SELECT COALESCE(SUM(total),0) as total 
            FROM sales 
            WHERE date=?
        """, conn, params=(st.session_state.selected_date.strftime("%Y-%m-%d"),)).iloc[0]['total']
        
        st.markdown(f"""
        <div class="sales-card">
            <h3>💰</h3>
            <h4>Today's Sales</h4>
            <h2>₹{today_sales:.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Today's Customers
        today_customers = pd.read_sql("""
            SELECT COUNT(DISTINCT customer) as count 
            FROM sales 
            WHERE date=?
        """, conn, params=(st.session_state.selected_date.strftime("%Y-%m-%d"),)).iloc[0]['count']
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h4>Today's Customers</h4>
            <h2>{today_customers}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Low Stock Items
        low_stock = pd.read_sql("""
            SELECT COUNT(*) as count 
            FROM inventory 
            WHERE quantity > 0 AND quantity < ?
        """, conn, params=(st.session_state.shortage_threshold,)).iloc[0]['count']
        
        st.markdown(f"""
        <div class="alert-warning" style="padding:20px; border-radius:15px; text-align:center;">
            <h3>⚠️</h3>
            <h4>Low Stock Items</h4>
            <h2>{low_stock}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Pending Credit Payments
        pending_credit = pd.read_sql("""
            SELECT COUNT(*) as count 
            FROM credit_accounts 
            WHERE current_balance > 0 AND status = 'active'
        """, conn).iloc[0]['count']
        
        st.markdown(f"""
        <div class="purchase-card">
            <h3>💳</h3>
            <h4>Pending Credit</h4>
            <h2>{pending_credit}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Quick Actions Row
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🛒 New Sale", use_container_width=True):
            st.session_state.current_page = "Quick Sell"
            st.rerun()
    
    with col2:
        if st.button("📦 Add Stock", use_container_width=True):
            st.session_state.current_page = "Add Purchase"
            st.rerun()
    
    with col3:
        if st.button("📊 View Reports", use_container_width=True):
            st.session_state.current_page = "Advanced Analytics"
            st.rerun()
    
    with col4:
        if st.button("🔔 Send Notification", use_container_width=True):
            st.session_state.current_page = "Notifications"
            st.rerun()
    
    # Recent Activity
    st.markdown("---")
    st.markdown("### 📈 Recent Activity")
    
    # Today's sales chart
    sales_today = pd.read_sql("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as transactions, SUM(total) as amount
        FROM sales 
        WHERE date = ?
        GROUP BY hour
        ORDER BY hour
    """, conn, params=(st.session_state.selected_date.strftime("%Y-%m-%d"),))
    
    if not sales_today.empty:
        fig = px.bar(sales_today, x='hour', y='amount', 
                     title='Sales by Hour Today',
                     labels={'hour': 'Hour', 'amount': 'Sales Amount (₹)'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent transactions
    st.markdown("#### Recent Transactions")
    recent_sales = pd.read_sql("""
        SELECT customer, vegetable, quantity_sold, total, payment_method, timestamp
        FROM sales 
        ORDER BY timestamp DESC 
        LIMIT 10
    """, conn)
    
    if not recent_sales.empty:
        st.dataframe(recent_sales, use_container_width=True)
    else:
        st.info("No recent transactions")

def show_user_management():
    """User management page for admins"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>👥 User Management</h2>
        <div class="subtitle">Manage system users and permissions</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["👥 Users", "➕ Add User", "📊 Audit Log"])
    
    with tab1:
        st.markdown("### System Users")
        
        users_df = pd.read_sql("""
            SELECT id, username, full_name, email, phone, role, 
                   last_login, created_at, is_active
            FROM users
            ORDER BY created_at DESC
        """, conn)
        
        if not users_df.empty:
            # Display users
            for _, user in users_df.iterrows():
                status_color = "🟢" if user['is_active'] else "🔴"
                status_text = "Active" if user['is_active'] else "Inactive"
                
                with st.expander(f"{status_color} {user['full_name']} ({user['username']}) - {user['role'].title()}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Email:** {user['email'] or 'Not set'}")
                        st.write(f"**Phone:** {user['phone'] or 'Not set'}")
                        st.write(f"**Status:** {status_text}")
                    
                    with col2:
                        st.write(f"**Last Login:** {user['last_login'] or 'Never'}")
                        st.write(f"**Created:** {user['created_at']}")
                        
                        if st.button(f"Edit {user['username']}", key=f"edit_{user['id']}"):
                            st.session_state.editing_user = user['id']
                            st.rerun()
                    
                    if st.button(f"{'Deactivate' if user['is_active'] else 'Activate'} User", 
                                key=f"toggle_{user['id']}"):
                        new_status = 0 if user['is_active'] else 1
                        c.execute("UPDATE users SET is_active = ? WHERE id = ?", 
                                 (new_status, user['id']))
                        conn.commit()
                        st.success(f"User {user['username']} {'deactivated' if new_status == 0 else 'activated'}")
                        st.rerun()
        else:
            st.info("No users found")
    
    with tab2:
        st.markdown("### Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Username*", placeholder="Enter username")
                password = st.text_input("Password*", type="password", placeholder="Enter password")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm password")
                full_name = st.text_input("Full Name", placeholder="Enter full name")
            
            with col2:
                email = st.text_input("Email", placeholder="Enter email")
                phone = st.text_input("Phone", placeholder="Enter phone number")
                role = st.selectbox("Role", ["admin", "manager", "cashier", "viewer"])
                is_active = st.checkbox("Active", value=True)
            
            if st.form_submit_button("Add User", type="primary"):
                if not username or not password:
                    st.error("Username and password are required")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    try:
                        password_hash = hash_password(password)
                        
                        c.execute("""
                            INSERT INTO users 
                            (username, password_hash, full_name, email, phone, role, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (username, password_hash, full_name, email, phone, role, 1 if is_active else 0))
                        
                        conn.commit()
                        
                        log_audit(
                            st.session_state.user['id'],
                            st.session_state.user['username'],
                            'create_user',
                            'users',
                            str(c.lastrowid),
                            '',
                            json.dumps({'username': username, 'role': role})
                        )
                        
                        st.success(f"User {username} created successfully!")
                        st.rerun()
                    except Exception as e:
                        if "UNIQUE constraint failed" in str(e):
                            st.error("Username already exists")
                        else:
                            st.error(f"Error creating user: {e}")
    
    with tab3:
        st.markdown("### Audit Log")
        
        audit_df = pd.read_sql("""
            SELECT timestamp, username, action, table_name, record_id
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT 100
        """, conn)
        
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True)
            
            # Download audit log
            csv = audit_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download Audit Log",
                data=csv,
                file_name="audit_log.csv",
                mime="text/csv"
            )
        else:
            st.info("No audit logs found")

def show_advanced_analytics():
    """Advanced analytics dashboard"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>📈 Advanced Analytics</h2>
        <div class="subtitle">Deep insights and business intelligence</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Profit Analysis", 
        "📈 Sales Forecast", 
        "👥 Customer Analytics",
        "📦 Inventory Analytics",
        "📋 Automated Reports"
    ])
    
    with tab1:
        st.markdown("### Profit Margin Analysis")
        
        date_range = st.date_input(
            "Select Date Range",
            value=(st.session_state.selected_date, st.session_state.selected_date),
            key="profit_date_range"
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            
            # Get profit analysis
            profit_data = analytics.get_daily_profit_analysis(start_date.strftime("%Y-%m-%d"))
            
            if profit_data.get('total_sales', 0) > 0:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Sales", f"₹{profit_data['total_sales']:.2f}")
                with col2:
                    st.metric("Total Cost", f"₹{profit_data['total_cost']:.2f}")
                with col3:
                    st.metric("Total Profit", f"₹{profit_data['total_profit']:.2f}")
                with col4:
                    st.metric("Profit Margin", f"{profit_data['margin_percentage']:.1f}%")
                
                # Top profitable items
                st.markdown("#### Top Profitable Items")
                if profit_data.get('top_items'):
                    top_items_df = pd.DataFrame(profit_data['top_items'])
                    st.dataframe(top_items_df, use_container_width=True)
                
                # Profit trend chart
                st.markdown("#### Profit Trend (Last 7 Days)")
                
                trend_df = pd.read_sql("""
                    SELECT s.date, 
                           SUM(s.total) as sales,
                           SUM(s.quantity_sold * i.cost_price) as cost,
                           SUM(s.total - (s.quantity_sold * i.cost_price)) as profit
                    FROM sales s
                    LEFT JOIN inventory i ON s.vegetable = i.vegetable
                    WHERE s.date >= date('now', '-7 days')
                    GROUP BY s.date
                    ORDER BY s.date
                """, conn)
                
                if not trend_df.empty:
                    fig = px.line(trend_df, x='date', y=['sales', 'profit'], 
                                 title='Sales vs Profit Trend',
                                 labels={'value': 'Amount (₹)', 'date': 'Date'})
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sales data for selected date")
    
    with tab2:
        st.markdown("### Sales Forecast")
        
        forecast_data = analytics.get_sales_forecast()
        
        if forecast_data.get('forecast'):
            st.metric("Next 7 Days Forecast", f"₹{forecast_data['next_7_days_total']:.2f}")
            st.write(f"**Forecast Accuracy:** {forecast_data['accuracy']}")
            
            forecast_df = pd.DataFrame(forecast_data['forecast'])
            
            fig = px.bar(forecast_df, x='date', y='forecast_sales',
                        title='Sales Forecast (Next 7 Days)',
                        labels={'forecast_sales': 'Forecast Sales (₹)', 'date': 'Date'})
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(forecast_df, use_container_width=True)
        else:
            st.info("Insufficient data for sales forecast")
    
    with tab3:
        st.markdown("### Customer Analytics")
        
        customer_data = analytics.get_customer_analytics()
        
        if not customer_data.get('error'):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Customers", customer_data['total_customers'])
            with col2:
                st.metric("Total Revenue", f"₹{customer_data['total_revenue_from_customers']:.2f}")
            with col3:
                st.metric("Avg Customer Value", f"₹{customer_data['avg_customer_value']:.2f}")
            
            # Customer segments
            st.markdown("#### Customer Segments")
            if customer_data.get('segments'):
                segments_df = pd.DataFrame(customer_data['segments']).T.reset_index()
                segments_df.columns = ['Segment', 'Count', 'Avg Spent', 'Total Spent']
                
                fig = px.pie(segments_df, values='Total Spent', names='Segment',
                            title='Revenue by Customer Segment')
                st.plotly_chart(fig, use_container_width=True)
            
            # Top customers
            st.markdown("#### Top 10 Customers")
            if customer_data.get('top_customers'):
                top_customers_df = pd.DataFrame(customer_data['top_customers'])
                st.dataframe(top_customers_df, use_container_width=True)
        else:
            st.error(f"Error: {customer_data.get('error')}")
    
    with tab4:
        st.markdown("### Inventory Analytics")
        
        inventory_data = analytics.get_inventory_analytics()
        
        if not inventory_data.get('error'):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Items", inventory_data['total_items'])
            with col2:
                st.metric("Total Valuation", f"₹{inventory_data['total_valuation']:.2f}")
            with col3:
                st.metric("Avg Margin", f"{inventory_data['avg_margin']:.1f}%")
            with col4:
                st.metric("Slow Moving", inventory_data['slow_moving_count'])
            
            # Inventory valuation chart
            st.markdown("#### Top Items by Inventory Value")
            if inventory_data.get('top_items_by_value'):
                value_df = pd.DataFrame(inventory_data['top_items_by_value'])
                
                fig = px.bar(value_df.head(10), x='vegetable', y='valuation',
                            title='Top 10 Items by Inventory Value',
                            labels={'valuation': 'Value (₹)', 'vegetable': 'Item'})
                st.plotly_chart(fig, use_container_width=True)
            
            # Turnover rate
            st.markdown("#### Top Items by Turnover Rate")
            if inventory_data.get('top_items_by_turnover'):
                turnover_df = pd.DataFrame(inventory_data['top_items_by_turnover'])
                st.dataframe(turnover_df, use_container_width=True)
        else:
            st.error(f"Error: {inventory_data.get('error')}")
    
    with tab5:
        st.markdown("### Automated Reports")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Generate Report")
            
            report_type = st.selectbox("Report Type", ["daily", "weekly", "monthly"])
            
            if st.button("Generate Report", use_container_width=True):
                with st.spinner("Generating report..."):
                    if report_type == "daily":
                        report = report_generator.generate_daily_report()
                    elif report_type == "weekly":
                        report = report_generator.generate_weekly_report()
                    else:  # monthly
                        report = report_generator.generate_monthly_report()
                    
                    st.success("Report generated successfully!")
                    
                    # Display report summary
                    st.json(report)
                    
                    # Export option
                    export_result = report_generator.export_report_to_csv(report, report_type)
                    if export_result['success']:
                        st.download_button(
                            "📥 Download CSV",
                            data=open(export_result['filepath'], 'rb').read(),
                            file_name=export_result['filename'],
                            mime="text/csv"
                        )
        
        with col2:
            st.markdown("#### Schedule Reports")
            
            with st.form("schedule_report_form"):
                schedule_type = st.selectbox("Schedule Type", ["daily", "weekly", "monthly"])
                delivery_method = st.selectbox("Delivery Method", ["email", "whatsapp", "sms"])
                recipients = st.text_area("Recipients (comma-separated)", 
                                         placeholder="email1@example.com, email2@example.com")
                
                if st.form_submit_button("Schedule Report", type="primary"):
                    if recipients:
                        recipients_list = [r.strip() for r in recipients.split(',')]
                        result = report_generator.schedule_report(
                            "daily",  # For simplicity, always daily
                            schedule_type,
                            delivery_method,
                            recipients_list
                        )
                        
                        if result['success']:
                            st.success(f"Report scheduled! Next run: {result['next_run']}")
                        else:
                            st.error(f"Error: {result.get('error')}")
                    else:
                        st.error("Please enter at least one recipient")

def show_notifications():
    """Notifications management page"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>🔔 Notifications</h2>
        <div class="subtitle">Manage customer notifications</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📨 Send Notification", "📋 Notification History", "⚙️ Settings"])
    
    with tab1:
        st.markdown("### Send Customer Notification")
        
        with st.form("send_notification_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                notification_type = st.selectbox(
                    "Notification Type",
                    ["order_confirmation", "payment_received", "credit_limit", 
                     "low_stock", "special_offer", "custom"]
                )
                
                customer_phone = st.text_input("Customer Phone*", 
                                               placeholder="+919876543210")
                
                if notification_type == "custom":
                    message = st.text_area("Custom Message*", 
                                          placeholder="Enter your message here...",
                                          height=100)
                else:
                    message = ""
            
            with col2:
                if notification_type == "order_confirmation":
                    bill_no = st.text_input("Bill Number", placeholder="BIL20240101001")
                    amount = st.number_input("Amount", min_value=0.0, value=0.0)
                elif notification_type == "payment_received":
                    amount = st.number_input("Amount", min_value=0.0, value=0.0)
                    balance = st.number_input("Balance", min_value=0.0, value=0.0)
                elif notification_type == "credit_limit":
                    balance = st.number_input("Current Balance", min_value=0.0, value=0.0)
                    limit = st.number_input("Credit Limit", min_value=0.0, value=0.0)
                elif notification_type == "low_stock":
                    item = st.text_input("Item Name", placeholder="Tomato")
                    stock = st.number_input("Current Stock", min_value=0.0, value=0.0)
                elif notification_type == "special_offer":
                    offer = st.text_input("Offer Details", placeholder="20% off on Vegetables")
                    valid_until = st.date_input("Valid Until", value=st.session_state.selected_date)
            
            delivery_method = st.radio("Delivery Method", ["SMS", "WhatsApp"], horizontal=True)
            
            if st.form_submit_button("Send Notification", type="primary"):
                if not customer_phone:
                    st.error("Customer phone is required")
                elif notification_type == "custom" and not message:
                    st.error("Message is required for custom notifications")
                else:
                    # Prepare data
                    data = {}
                    if notification_type == "order_confirmation":
                        data = {"bill_no": bill_no, "amount": amount}
                    elif notification_type == "payment_received":
                        data = {"amount": amount, "balance": balance}
                    elif notification_type == "credit_limit":
                        data = {"balance": balance, "limit": limit}
                    elif notification_type == "low_stock":
                        data = {"item": item, "stock": stock}
                    elif notification_type == "special_offer":
                        data = {"offer": offer, "valid_until": valid_until.strftime("%Y-%m-%d")}
                    elif notification_type == "custom":
                        data = {"message": message}
                    
                    with st.spinner("Sending notification..."):
                        result = notification_manager.send_customer_notification(
                            customer_phone,
                            notification_type,
                            data
                        )
                        
                        if result['success']:
                            st.success("Notification sent successfully!")
                        else:
                            st.error(f"Failed to send notification: {result.get('error', 'Unknown error')}")
    
    with tab2:
        st.markdown("### Notification History")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            days_filter = st.selectbox("Time Period", ["Last 7 days", "Last 30 days", "All time"])
        
        with col2:
            status_filter = st.selectbox("Status", ["All", "sent", "failed", "pending"])
        
        with col3:
            type_filter = st.selectbox("Type", ["All", "sms", "whatsapp", "email", "system"])
        
        # Build query
        query = "SELECT * FROM notifications WHERE 1=1"
        params = []
        
        if days_filter == "Last 7 days":
            query += " AND created_at >= date('now', '-7 days')"
        elif days_filter == "Last 30 days":
            query += " AND created_at >= date('now', '-30 days')"
        
        if status_filter != "All":
            query += " AND status = ?"
            params.append(status_filter)
        
        if type_filter != "All":
            query += " AND notification_type = ?"
            params.append(type_filter)
        
        query += " ORDER BY created_at DESC LIMIT 100"
        
        notifications_df = pd.read_sql(query, conn, params=params)
        
        if not notifications_df.empty:
            st.dataframe(notifications_df, use_container_width=True)
            
            # Statistics
            sent_count = len(notifications_df[notifications_df['status'] == 'sent'])
            failed_count = len(notifications_df[notifications_df['status'] == 'failed'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Sent", sent_count)
            with col2:
                st.metric("Failed", failed_count)
        else:
            st.info("No notifications found")
    
    with tab3:
        st.markdown("### Notification Settings")
        
        with st.form("notification_settings_form"):
            st.markdown("#### Twilio Configuration (for SMS/WhatsApp)")
            
            twilio_account_sid = st.text_input("Twilio Account SID", 
                                               value=secrets_data.get('twilio_account_sid', ''),
                                               type="password")
            twilio_auth_token = st.text_input("Twilio Auth Token", 
                                              value=secrets_data.get('twilio_auth_token', ''),
                                              type="password")
            twilio_phone_number = st.text_input("Twilio Phone Number", 
                                                value=secrets_data.get('twilio_phone_number', ''))
            twilio_whatsapp_number = st.text_input("Twilio WhatsApp Number", 
                                                   value=secrets_data.get('twilio_whatsapp_number', ''))
            
            st.markdown("#### Email Configuration")
            smtp_server = st.text_input("SMTP Server", 
                                        value=secrets_data.get('smtp_server', ''))
            smtp_port = st.number_input("SMTP Port", 
                                        value=secrets_data.get('smtp_port', 587),
                                        min_value=1, max_value=65535)
            smtp_username = st.text_input("SMTP Username", 
                                          value=secrets_data.get('smtp_username', ''))
            smtp_password = st.text_input("SMTP Password", 
                                          value=secrets_data.get('smtp_password', ''),
                                          type="password")
            
            if st.form_submit_button("Save Settings", type="primary"):
                # Save to secrets
                secrets_data.update({
                    'twilio_account_sid': twilio_account_sid,
                    'twilio_auth_token': twilio_auth_token,
                    'twilio_phone_number': twilio_phone_number,
                    'twilio_whatsapp_number': twilio_whatsapp_number,
                    'smtp_server': smtp_server,
                    'smtp_port': int(smtp_port),
                    'smtp_username': smtp_username,
                    'smtp_password': smtp_password
                })
                
                save_secrets(secrets_data)
                st.success("Settings saved successfully!")

def show_credit_accounts():
    """Credit accounts management"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>💳 Credit Accounts</h2>
        <div class="subtitle">Manage customer credit and debit accounts</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["👥 Accounts", "➕ New Account", "📊 Reports"])
    
    with tab1:
        st.markdown("### Credit Accounts")
        
        # Search and filter
        col1, col2 = st.columns(2)
        
        with col1:
            search_phone = st.text_input("Search by Phone", placeholder="Enter phone number")
        
        with col2:
            status_filter = st.selectbox("Status", ["All", "active", "suspended", "closed"])
        
        # Build query
        query = "SELECT * FROM credit_accounts WHERE 1=1"
        params = []
        
        if search_phone:
            query += " AND customer_phone LIKE ?"
            params.append(f"%{search_phone}%")
        
        if status_filter != "All":
            query += " AND status = ?"
            params.append(status_filter)
        
        query += " ORDER BY current_balance DESC"
        
        accounts_df = pd.read_sql(query, conn, params=params)
        
        if not accounts_df.empty:
            for _, account in accounts_df.iterrows():
                with st.expander(f"{account['customer_name']} ({account['customer_phone']}) - Balance: ₹{account['current_balance']:.2f}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Credit Limit:** ₹{account['credit_limit']:.2f}")
                        st.write(f"**Total Credit Given:** ₹{account['total_credit_given']:.2f}")
                        st.write(f"**Total Payments:** ₹{account['total_payments']:.2f}")
                    
                    with col2:
                        st.write(f"**Due Date:** {account['due_date'] or 'Not set'}")
                        st.write(f"**Last Payment:** {account['last_payment_date'] or 'Never'}")
                        st.write(f"**Last Payment Amount:** ₹{account['last_payment_amount']:.2f}")
                    
                    with col3:
                        st.write(f"**Status:** {account['status']}")
                        st.write(f"**Created:** {account['created_at']}")
                        
                        # Quick actions
                        if st.button("Add Credit", key=f"add_credit_{account['id']}"):
                            st.session_state.editing_account = account['id']
                            st.session_state.action = "add_credit"
                            st.rerun()
                        
                        if st.button("Receive Payment", key=f"payment_{account['id']}"):
                            st.session_state.editing_account = account['id']
                            st.session_state.action = "receive_payment"
                            st.rerun()
            
            # Summary statistics
            total_balance = accounts_df['current_balance'].sum()
            total_limit = accounts_df['credit_limit'].sum()
            active_accounts = len(accounts_df[accounts_df['status'] == 'active'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Balance", f"₹{total_balance:.2f}")
            with col2:
                st.metric("Total Limit", f"₹{total_limit:.2f}")
            with col3:
                st.metric("Active Accounts", active_accounts)
        else:
            st.info("No credit accounts found")
    
    with tab2:
        st.markdown("### Create New Credit Account")
        
        with st.form("new_credit_account_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                customer_phone = st.text_input("Customer Phone*", 
                                               placeholder="+919876543210")
                customer_name = st.text_input("Customer Name*", 
                                              placeholder="Enter customer name")
                credit_limit = st.number_input("Credit Limit (₹)", 
                                               min_value=0.0, value=1000.0)
            
            with col2:
                due_date = st.date_input("Due Date", 
                                         value=st.session_state.selected_date + timedelta(days=30))
                notes = st.text_area("Notes", placeholder="Additional notes...")
            
            if st.form_submit_button("Create Account", type="primary"):
                if not customer_phone or not customer_name:
                    st.error("Customer phone and name are required")
                else:
                    result = create_credit_account(
                        customer_phone,
                        customer_name,
                        credit_limit
                    )
                    
                    if result['success']:
                        st.success(f"Credit account created! Account ID: {result['account_id']}")
                        
                        # Send welcome notification
                        notification_manager.send_customer_notification(
                            customer_phone,
                            'credit_limit',
                            {'balance': 0, 'limit': credit_limit}
                        )
                    else:
                        st.error(f"Error: {result.get('error')}")
    
    with tab3:
        st.markdown("### Credit Reports")
        
        # Generate report
        if st.button("Generate Credit Report", use_container_width=True):
            with st.spinner("Generating report..."):
                # Get all accounts with transactions
                report_df = pd.read_sql("""
                    SELECT 
                        ca.customer_name,
                        ca.customer_phone,
                        ca.credit_limit,
                        ca.current_balance,
                        ca.total_credit_given,
                        ca.total_payments,
                        ca.status,
                        COUNT(ct.id) as transaction_count
                    FROM credit_accounts ca
                    LEFT JOIN credit_transactions ct ON ca.id = ct.account_id
                    GROUP BY ca.id
                    ORDER BY ca.current_balance DESC
                """, conn)
                
                if not report_df.empty:
                    st.dataframe(report_df, use_container_width=True)
                    
                    # Export option
                    csv = report_df.to_csv(index=False).encode()
                    st.download_button(
                        "📥 Download Report",
                        data=csv,
                        file_name=f"credit_report_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No credit data available")

def show_settings():
    """System settings page"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <h2>⚙️ System Settings</h2>
        <div class="subtitle">Configure system preferences</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔧 General", "💳 Payment", "📊 Barcode", "🔐 Security"])
    
    with tab1:
        st.markdown("### General Settings")
        
        with st.form("general_settings_form"):
            # Business information
            st.markdown("#### Business Information")
            business_name = st.text_input("Business Name", value="Fresh Basket")
            business_address = st.text_area("Business Address", 
                                           value="123 Green Street, Fresh City")
            business_phone = st.text_input("Business Phone", value="+919876543210")
            business_email = st.text_input("Business Email", value="info@freshbasket.com")
            
            # Receipt settings
            st.markdown("#### Receipt Settings")
            receipt_header = st.text_area("Receipt Header", 
                                         value="🌿 Fresh Basket\nFreshness You Can Feel")
            receipt_footer = st.text_area("Receipt Footer", 
                                         value="Thank you for your purchase!\nVisit again!")
            print_automatically = st.checkbox("Print receipt automatically", value=True)
            
            if st.form_submit_button("Save General Settings", type="primary"):
                # Save settings
                secrets_data.update({
                    'business_name': business_name,
                    'business_address': business_address,
                    'business_phone': business_phone,
                    'business_email': business_email,
                    'receipt_header': receipt_header,
                    'receipt_footer': receipt_footer,
                    'print_automatically': print_automatically
                })
                save_secrets(secrets_data)
                st.success("General settings saved!")
    
    with tab2:
        st.markdown("### Payment Settings")
        
        with st.form("payment_settings_form"):
            # Payment methods
            st.markdown("#### Payment Methods")
            
            payment_methods_df = pd.read_sql("SELECT * FROM payment_methods", conn)
            
            edited_df = st.data_editor(
                payment_methods_df[['name', 'display_name', 'is_active', 'processing_fee']],
                column_config={
                    "name": st.column_config.TextColumn("Code", disabled=True),
                    "display_name": st.column_config.TextColumn("Display Name"),
                    "is_active": st.column_config.CheckboxColumn("Active"),
                    "processing_fee": st.column_config.NumberColumn(
                        "Processing Fee %",
                        min_value=0.0,
                        max_value=10.0,
                        step=0.1,
                        format="%.1f%%"
                    )
                },
                use_container_width=True,
                num_rows="dynamic"
            )
            
            # Add new payment method
            st.markdown("#### Add New Payment Method")
            col1, col2 = st.columns(2)
            
            with col1:
                new_name = st.text_input("Method Code", placeholder="e.g., crypto")
                new_display = st.text_input("Display Name", placeholder="e.g., Cryptocurrency")
            
            with col2:
                new_fee = st.number_input("Processing Fee %", min_value=0.0, max_value=10.0, value=0.0, step=0.1)
                new_active = st.checkbox("Active", value=True)
            
            if st.form_submit_button("Save Payment Settings", type="primary"):
                # Update existing methods
                for _, row in edited_df.iterrows():
                    c.execute("""
                        UPDATE payment_methods 
                        SET display_name = ?, is_active = ?, processing_fee = ?
                        WHERE name = ?
                    """, (row['display_name'], 1 if row['is_active'] else 0, row['processing_fee'], row['name']))
                
                # Add new method if provided
                if new_name and new_display:
                    c.execute("""
                        INSERT OR IGNORE INTO payment_methods 
                        (name, display_name, is_active, processing_fee)
                        VALUES (?, ?, ?, ?)
                    """, (new_name, new_display, 1 if new_active else 0, new_fee))
                
                conn.commit()
                st.success("Payment settings updated!")
    
    with tab3:
        st.markdown("### Barcode Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Generate Barcodes")
            
            # Get items without barcodes
            items_df = pd.read_sql("""
                SELECT i.vegetable 
                FROM inventory i
                LEFT JOIN barcode_mapping b ON i.vegetable = b.vegetable
                WHERE b.vegetable IS NULL
                ORDER BY i.vegetable
            """, conn)
            
            if not items_df.empty:
                selected_item = st.selectbox("Select item to generate barcode", 
                                            items_df['vegetable'].tolist())
                
                if st.button("Generate Barcode", use_container_width=True):
                    with st.spinner("Generating barcode..."):
                        result = barcode_manager.generate_barcode(selected_item)
                        
                        if result['success']:
                            st.success(f"Barcode generated: {result['barcode']}")
                            
                            # Display barcode
                            st.image(result['filepath'], caption=f"Barcode for {selected_item}")
                        else:
                            st.error(f"Error: {result.get('error')}")
            else:
                st.info("All items have barcodes")
        
        with col2:
            st.markdown("#### Barcode Scanner")
            
            uploaded_file = st.file_uploader("Upload barcode image", type=['png', 'jpg', 'jpeg'])
            
            if uploaded_file:
                st.image(uploaded_file, caption="Uploaded barcode")
                
                if st.button("Scan Barcode", use_container_width=True):
                    st.info("Barcode scanning would be implemented with a barcode scanning library")
                    # In a real implementation, use pyzbar or similar library
    
    with tab4:
        st.markdown("### Security Settings")
        
        if st.session_state.user and st.session_state.user['role'] == 'admin':
            with st.form("security_settings_form"):
                # Password policy
                st.markdown("#### Password Policy")
                min_password_length = st.number_input("Minimum Password Length", 
                                                     min_value=6, max_value=20, value=8)
                require_special_chars = st.checkbox("Require special characters", value=True)
                password_expiry_days = st.number_input("Password Expiry (days)", 
                                                      min_value=0, max_value=365, value=90)
                
                # Session settings
                st.markdown("#### Session Settings")
                session_timeout = st.number_input("Session Timeout (minutes)", 
                                                 min_value=5, max_value=240, value=30)
                max_login_attempts = st.number_input("Max Login Attempts", 
                                                     min_value=1, max_value=10, value=3)
                
                # Audit log settings
                st.markdown("#### Audit Log")
                retain_audit_days = st.number_input("Retain Audit Log (days)", 
                                                   min_value=7, max_value=365, value=90)
                
                if st.form_submit_button("Save Security Settings", type="primary"):
                    secrets_data.update({
                        'min_password_length': min_password_length,
                        'require_special_chars': require_special_chars,
                        'password_expiry_days': password_expiry_days,
                        'session_timeout': session_timeout,
                        'max_login_attempts': max_login_attempts,
                        'retain_audit_days': retain_audit_days
                    })
                    save_secrets(secrets_data)
                    st.success("Security settings saved!")
        else:
            st.warning("Only administrators can access security settings")

def show_existing_page(menu):
    """Show existing pages (simplified for this example)"""
    st.markdown(f"# {menu}")
    st.info("This page would show the existing functionality from your original code.")
    
    # Quick Sell with enhanced features
    if menu == "💵 Quick Sell":
        show_enhanced_quick_sell()
    else:
        st.write(f"Page: {menu} - Existing functionality would be here")

def show_enhanced_quick_sell():
    """Enhanced Quick Sell with new features"""
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2>💵 Quick Selling</h2>
        <div class="subtitle">Enhanced with multiple payment methods and barcode support</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get available vegetables
    available_veg = pd.read_sql("""
        SELECT vegetable, quantity, selling_price, unit_type 
        FROM inventory 
        WHERE quantity > 0 AND selling_price > 0 
        ORDER BY vegetable
    """, conn)
    
    if available_veg.empty:
        st.warning("⚠️ No items available for sale!")
        return
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Item selection
        st.markdown("### 🌿 Select Items")
        
        # Barcode scanner input
        barcode_input = st.text_input("📷 Scan Barcode", placeholder="Scan or enter barcode")
        if barcode_input:
            # Look up item by barcode
            c.execute("SELECT vegetable FROM barcode_mapping WHERE barcode = ?", (barcode_input,))
            result = c.fetchone()
            if result:
                st.success(f"Found: {result[0]}")
                # Auto-select this item
        
        # Customer info
        with st.expander("👤 Customer Information", expanded=True):
            cust_col1, cust_col2 = st.columns(2)
            with cust_col1:
                cust_name = st.text_input("Customer Name", placeholder="Leave empty for Guest")
            with cust_col2:
                cust_phone = st.text_input("Phone Number", placeholder="Optional")
                
                # Check for credit account
                if cust_phone:
                    account_info = get_credit_account(cust_phone)
                    if account_info['success']:
                        account = account_info['account']
                        st.info(f"Credit Available: ₹{account['credit_limit'] - account['current_balance']:.2f}")
        
        # Item selection tabs
        tab1, tab2 = st.tabs(["📋 List View", "🏷️ Barcode View"])
        
        with tab1:
            # Existing item selection logic
            selected_veg = st.selectbox("Select Item", available_veg['vegetable'].tolist())
            
            if selected_veg:
                stock, _, price, unit_type = get_stock(selected_veg)
                st.info(f"Price: ₹{price:.2f}/{unit_type} | Stock: {stock:.2f} {unit_type}")
                
                # Quantity input
                if unit_type == 'kg':
                    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.001, 
                                         format="%.3f", key="qty_input")
                else:
                    qty = st.number_input(f"Quantity ({unit_type})", min_value=0, step=1, 
                                         key="qty_input_pieces")
                
                if qty > 0:
                    total = qty * price
                    st.info(f"Total: ₹{total:.2f}")
                    
                    if st.button("➕ Add to Cart", use_container_width=True):
                        # Add to cart logic
                        st.success(f"Added {qty} {unit_type} of {selected_veg}")
        
        with tab2:
            # Barcode-based selection
            st.info("Scan barcodes to add items quickly")
            # This would integrate with a barcode scanner
    
    with col2:
        # Cart and checkout
        st.markdown("### 🛒 Current Bill")
        
        if not st.session_state.cart:
            st.info("🛒 Cart is empty")
        else:
            # Display cart
            total_amount = sum(item[3] for item in st.session_state.cart)
            
            st.markdown(f"""
            <div class="card" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); 
                                    color:white; text-align:center; padding:20px;">
                <h3 style="margin:0;">Bill Total</h3>
                <h1 style="margin:10px 0;">₹{total_amount:.2f}</h1>
                <p style="margin:0; font-size:0.9em;">{len(st.session_state.cart)} items</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Payment method selection
            st.markdown("#### 💳 Payment Method")
            payment_methods_df = pd.read_sql("""
                SELECT name, display_name, icon 
                FROM payment_methods 
                WHERE is_active = 1
            """, conn)
            
            payment_options = {row['name']: f"{row['icon']} {row['display_name']}" 
                              for _, row in payment_methods_df.iterrows()}
            
            payment_method = st.selectbox("Select payment method", 
                                         list(payment_options.keys()),
                                         format_func=lambda x: payment_options[x])
            
            # Credit account option
            credit_account_id = None
            if payment_method == 'credit' and cust_phone:
                account_info = get_credit_account(cust_phone)
                if account_info['success']:
                    credit_account_id = account_info['account']['id']
                    available_credit = account_info['account']['credit_limit'] - account_info['account']['current_balance']
                    
                    if total_amount > available_credit:
                        st.error(f"Credit limit exceeded! Available: ₹{available_credit:.2f}")
                        payment_method = 'cash'  # Fallback to cash
                else:
                    st.error("No active credit account found")
                    payment_method = 'cash'  # Fallback to cash
            
            # Checkout button
            if st.button("✅ Checkout", type="primary", use_container_width=True):
                with st.spinner("Processing payment..."):
                    # Process payment
                    payment_result = process_payment(
                        total_amount,
                        payment_method,
                        cust_phone,
                        credit_account_id
                    )
                    
                    if payment_result['success']:
                        st.success("Payment successful!")
                        
                        # Record sale
                        d = st.session_state.selected_date.strftime("%Y-%m-%d")
                        current_time = get_ist_time()
                        
                        for item in st.session_state.cart:
                            veg, qty, price, item_total, unit_type = item
                            
                            # Save sale with payment info
                            c.execute("""
                                INSERT INTO sales 
                                (date, vegetable, quantity_sold, sale_price, total, 
                                 customer, unit_type, payment_method, transaction_id, 
                                 payment_status, processed_by)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                d, veg, qty, price, item_total,
                                f"{cust_name or 'Guest'} ({cust_phone})" if cust_phone else cust_name or 'Guest',
                                unit_type,
                                payment_method,
                                payment_result['transaction_id'],
                                'completed',
                                st.session_state.user['username'] if st.session_state.user else 'system'
                            ))
                            
                            # Update inventory
                            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE vegetable = ?", 
                                     (qty, veg))
                        
                        conn.commit()
                        
                        # Send notification
                        if cust_phone:
                            notification_manager.send_customer_notification(
                                cust_phone,
                                'order_confirmation',
                                {
                                    'bill_no': payment_result['transaction_id'],
                                    'amount': total_amount
                                }
                            )
                        
                        st.balloons()
                        st.session_state.cart = []
                        st.session_state.last_sale = {
                            'transaction_id': payment_result['transaction_id'],
                            'amount': total_amount,
                            'payment_method': payment_method
                        }
                    else:
                        st.error(f"Payment failed: {payment_result.get('error')}")

# ========================== MAIN EXECUTION ==========================
def main():
    """Main application entry point"""
    
    # Check for offline data sync
    if os.path.exists(OFFLINE_FILE):
        with st.spinner("Checking for offline data..."):
            if sync_offline_data():
                st.success("Offline data synced successfully!")
            else:
                st.warning("Could not sync offline data. Some features may be limited.")
    
    # Show login page if not authenticated
    if not st.session_state.user and not st.session_state.offline_mode:
        show_login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
