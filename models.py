from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

class ProductionBatch(Base):
    __tablename__ = 'production_batches'
    
    id = Column(Integer, primary_key=True)
    batch_number = Column(String(50), unique=True, nullable=False)
    order_id = Column(String(50))  # Reference to marketplace order
    product_id = Column(Integer, nullable=False)  # Product being manufactured
    quantity = Column(Integer, nullable=False)
    priority = Column(Integer, default=1)  # 1=low, 2=medium, 3=high
    status = Column(String(20), default='pending')  # pending, in_progress, completed, cancelled
    production_plan_id = Column(Integer)  # Reference to Production Planning Service
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    production_steps = relationship("ProductionStep", back_populates="batch")

class ProductionStep(Base):
    __tablename__ = 'production_steps'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('production_batches.id'))
    step_number = Column(Integer)
    name = Column(String(100), nullable=False)
    machine_type = Column(String(50))  # Type of machine required for this step
    status = Column(String(20), default='pending')  # pending, in_progress, completed, skipped
    duration_minutes = Column(Integer)  # Estimated duration in minutes
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    machine_queue_id = Column(Integer)  # Reference to Machine Queue Service
    notes = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    batch = relationship("ProductionBatch", back_populates="production_steps")
    materials = relationship("StepMaterial", back_populates="step")

class StepMaterial(Base):
    __tablename__ = 'step_materials'
    
    id = Column(Integer, primary_key=True)
    step_id = Column(Integer, ForeignKey('production_steps.id'))
    material_id = Column(Integer, nullable=False)  # Reference to Material Inventory Service
    quantity_required = Column(Float, nullable=False)
    is_consumed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    step = relationship("ProductionStep", back_populates="materials")

class ProductDefinition(Base):
    __tablename__ = 'product_definitions'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, unique=True, nullable=False)  # External product ID
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    production_workflow = Column(JSON)  # JSON defining steps and materials
    standard_batch_size = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    """Initialize the database with tables"""
    db_config = get_db_config("production_management")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:3308/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Create a session factory
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Get a new database session"""
    db_config = get_db_config("production_management")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:3308/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
