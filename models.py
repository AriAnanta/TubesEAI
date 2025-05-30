from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

class Machine(Base):
    __tablename__ = 'machines'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    machine_type = Column(String(50), nullable=False)  # Type/category of machine
    status = Column(String(20), default='available')  # available, busy, maintenance, offline
    current_queue_item_id = Column(Integer)  # Currently processing queue item
    last_maintenance = Column(DateTime)
    next_maintenance = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    queue_items = relationship("MachineQueueItem", back_populates="machine")

class MachineQueueItem(Base):
    __tablename__ = 'machine_queue_items'
    
    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey('machines.id'))
    production_step_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    batch_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    position = Column(Integer, nullable=False)  # Position in the queue
    priority = Column(Integer, default=1)  # 1=low, 2=medium, 3=high
    status = Column(String(20), default='queued')  # queued, in_progress, completed, cancelled
    estimated_start_time = Column(DateTime)
    estimated_end_time = Column(DateTime)
    actual_start_time = Column(DateTime)
    actual_end_time = Column(DateTime)
    setup_time_minutes = Column(Integer, default=0)  # Time needed to set up the machine
    processing_time_minutes = Column(Integer, nullable=False)  # Time needed to process the item
    materials_ready = Column(Boolean, default=False)  # Flag indicating if materials are ready
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    machine = relationship("Machine", back_populates="queue_items")
    materials = relationship("QueueItemMaterial", back_populates="queue_item")

class QueueItemMaterial(Base):
    __tablename__ = 'queue_item_materials'
    
    id = Column(Integer, primary_key=True)
    queue_item_id = Column(Integer, ForeignKey('machine_queue_items.id'))
    material_id = Column(Integer, nullable=False)  # Reference to Material Inventory Service
    quantity_required = Column(Float, nullable=False)
    is_available = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    queue_item = relationship("MachineQueueItem", back_populates="materials")

class OperationLog(Base):
    __tablename__ = 'operation_logs'
    
    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey('machines.id'))
    queue_item_id = Column(Integer, ForeignKey('machine_queue_items.id'))
    operation_type = Column(String(50))  # setup, start, pause, resume, complete, error
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    operator = Column(String(100))  # Person or system that performed the operation
    notes = Column(String(255))
    error_details = Column(String(255))
    
    # Relationships
    machine = relationship("Machine")
    queue_item = relationship("MachineQueueItem")

def init_db():
    """Initialize the database with tables"""
    db_config = get_db_config("machine_queue")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Create a session factory
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Get a new database session"""
    db_config = get_db_config("machine_queue")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
