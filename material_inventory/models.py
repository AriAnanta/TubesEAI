from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

class Supplier(Base):
    __tablename__ = 'suppliers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact_person = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    address = Column(String(255))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship
    materials = relationship("Material", back_populates="supplier")

class Material(Base):
    __tablename__ = 'materials'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    sku = Column(String(50), unique=True)
    unit = Column(String(20))  # e.g., kg, liter, piece
    quantity = Column(Float, default=0)
    min_stock_level = Column(Float, default=0)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'))
    cost_per_unit = Column(Float)
    location = Column(String(100))  # Storage location
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship
    supplier = relationship("Supplier", back_populates="materials")
    transactions = relationship("MaterialTransaction", back_populates="material")

class MaterialTransaction(Base):
    __tablename__ = 'material_transactions'
    
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id'))
    transaction_type = Column(String(20))  # 'in', 'out', 'adjustment'
    quantity = Column(Float, nullable=False)
    reference = Column(String(100))  # Reference to production batch, PO, etc.
    notes = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationship
    material = relationship("Material", back_populates="transactions")


def init_db():
    """Initialize the database with tables"""
    db_config = get_db_config("material_inventory")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Create a session factory
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Get a new database session"""
    db_config = get_db_config("material_inventory")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
