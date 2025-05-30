from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

# Association table for many-to-many relationship between ProductionPlan and Materials
plan_materials = Table(
    'plan_materials',
    Base.metadata,
    Column('plan_id', Integer, ForeignKey('production_plans.id'), primary_key=True),
    Column('material_id', Integer, primary_key=True),
    Column('quantity_required', Float, nullable=False)
)

class Machine(Base):
    __tablename__ = 'machines'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    machine_type = Column(String(50))
    status = Column(String(20), default='available')  # available, busy, maintenance, offline
    capacity_per_hour = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    slots = relationship("MachineSlot", back_populates="machine")

class MachineSlot(Base):
    __tablename__ = 'machine_slots'
    
    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey('machines.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default='available')  # available, reserved, in_use
    production_plan_id = Column(Integer, ForeignKey('production_plans.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    machine = relationship("Machine", back_populates="slots")
    production_plan = relationship("ProductionPlan", back_populates="machine_slots")

class ProductionPlan(Base):
    __tablename__ = 'production_plans'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    product_id = Column(Integer)  # External reference to product
    quantity = Column(Integer, nullable=False)
    priority = Column(Integer, default=1)  # 1=low, 2=medium, 3=high
    status = Column(String(20), default='draft')  # draft, planned, in_progress, completed, cancelled
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    machine_slots = relationship("MachineSlot", back_populates="production_plan")
    
    # Virtual attribute for required materials (not stored in this database)
    # This will be fetched from Material Inventory Service

class CapacityPlan(Base):
    __tablename__ = 'capacity_plans'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_capacity_hours = Column(Float)
    allocated_capacity_hours = Column(Float, default=0)
    notes = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    """Initialize the database with tables"""
    db_config = get_db_config("production_planning")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Create a session factory
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Get a new database session"""
    db_config = get_db_config("production_planning")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
