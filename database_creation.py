import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Database setup
Base = declarative_base()
DATABASE_URL = 'sqlite:///refunds_agent.db'
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Customer(Base):
    __tablename__ = "customers"
    
    customer_id = Column(String, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    phone = Column(String)
    address_line1 = Column(String)
    address_line2 = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    country = Column(String)
    date_joined = Column(DateTime)
    customer_tier = Column(String)

class Product(Base):
    __tablename__ = "products"
    
    product_id = Column(String, primary_key=True)
    product_name = Column(String)
    category = Column(String)
    subcategory = Column(String)
    price = Column(Float)
    return_window_days = Column(Integer)
    weight_lbs = Column(Float)
    fragile = Column(Boolean)
    restockable = Column(Boolean)

class Order(Base):
    __tablename__ = "orders"
    
    order_id = Column(String, primary_key=True)
    customer_id = Column(String)
    product_id = Column(String)
    order_date = Column(DateTime)
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_amount = Column(Float)
    status = Column(String)
    delivery_date = Column(DateTime)
    shipping_address = Column(Text)

class ProcessedRequest(Base):
    __tablename__ = "processed_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String)
    customer_id = Column(String)
    order_id = Column(String)
    product_id = Column(String)
    request_type = Column(String)  # Refund, Return, Exchange
    reason = Column(String)
    description = Column(Text)
    request_date = Column(DateTime)
    status = Column(String)  # Approved, Rejected, In Progress
    decision_reason = Column(Text)
    refund_amount = Column(Float)
    processing_date = Column(DateTime)
    agent_notes = Column(Text)
    requires_followup = Column(Boolean, default=False)
    followup_reason = Column(Text)

class SyntheticDataRun(Base):
    """Tracks daily synthetic order generation runs so the job stays idempotent per day."""
    __tablename__ = "synthetic_data_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(String, unique=True)  # ISO date (YYYY-MM-DD), one row per day
    orders_created = Column(Integer)
    run_timestamp = Column(DateTime)

def create_database():
    """Create all database tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")

def load_csv_data():
    """Load data from CSV files into SQLite database"""
    print("Loading CSV data into database...")
    session = SessionLocal()
    
    try:
        # Load customers
        print("Loading customers...")
        customers_df = pd.read_csv('data/customers.csv')
        customers_df['date_joined'] = pd.to_datetime(customers_df['date_joined'])
        
        for _, row in customers_df.iterrows():
            customer = Customer(**row.to_dict())
            session.merge(customer)
        
        print(f"Loaded {len(customers_df)} customers")
        
        # Load products
        print("Loading products...")
        products_df = pd.read_csv('data/products.csv')
        for _, row in products_df.iterrows():
            product = Product(**row.to_dict())
            session.merge(product)
        
        print(f"Loaded {len(products_df)} products")
        
        # Load orders
        print("Loading orders...")
        orders_df = pd.read_csv('data/orders.csv')
        orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])
        orders_df['delivery_date'] = pd.to_datetime(orders_df['delivery_date'], errors='coerce')
        
        for _, row in orders_df.iterrows():
            order_dict = row.to_dict()
            # Handle NaN delivery dates
            if pd.isna(order_dict['delivery_date']):
                order_dict['delivery_date'] = None
            order = Order(**order_dict)
            session.merge(order)
        
        print(f"Loaded {len(orders_df)} orders")
        
        session.commit()
        print("All data loaded successfully into database")
        
        # Display summary statistics
        print("\nDatabase Summary:")
        print(f"   - Customers: {len(customers_df)}")
        print(f"   - Products: {len(products_df)}")
        print(f"   - Orders: {len(orders_df)}")
        
        # Customer tier distribution
        tier_dist = customers_df['customer_tier'].value_counts()
        print(f"\nCustomer Tier Distribution:")
        for tier, count in tier_dist.items():
            print(f"   - {tier}: {count}")
        
        # Product category distribution
        cat_dist = products_df['category'].value_counts()
        print(f"\nProduct Category Distribution:")
        for category, count in cat_dist.items():
            print(f"   - {category}: {count}")
        
        # Order status distribution
        status_dist = orders_df['status'].value_counts()
        print(f"\nOrder Status Distribution:")
        for status, count in status_dist.items():
            print(f"   - {status}: {count}")
        
    except Exception as e:
        print(f"Error loading data: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def verify_data_integrity():
    """Verify data integrity and relationships"""
    print("\nVerifying data integrity...")
    session = SessionLocal()
    
    try:
        # Check customer count
        customer_count = session.query(Customer).count()
        print(f"   Customers in database: {customer_count}")
        
        # Check product count
        product_count = session.query(Product).count()
        print(f"   Products in database: {product_count}")
        
        # Check order count
        order_count = session.query(Order).count()
        print(f"   Orders in database: {order_count}")
        
        # Verify foreign key relationships
        orders_with_invalid_customers = session.query(Order).filter(
            ~Order.customer_id.in_(
                session.query(Customer.customer_id)
            )
        ).count()
        
        orders_with_invalid_products = session.query(Order).filter(
            ~Order.product_id.in_(
                session.query(Product.product_id)
            )
        ).count()
        
        if orders_with_invalid_customers == 0 and orders_with_invalid_products == 0:
            print("   All foreign key relationships are valid")
        else:
            print(f"   Found {orders_with_invalid_customers} orders with invalid customer IDs")
            print(f"   Found {orders_with_invalid_products} orders with invalid product IDs")
        
        # Check for delivered orders (important for refund processing)
        delivered_orders = session.query(Order).filter(Order.status == 'Delivered').count()
        print(f"   Delivered orders available for returns: {delivered_orders}")
        
    except Exception as e:
        print(f"   Error during verification: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    print("Setting up Refunds Agent Database")
    print("=" * 50)
    
    # Create database and tables
    create_database()
    
    # Load data from CSV files
    load_csv_data()
    
    # Verify data integrity
    verify_data_integrity()
    
    print("\nDatabase setup completed successfully!")
    print("The database is ready for the refund processing agents.")