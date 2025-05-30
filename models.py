from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

class ProductionFeedback(Base):
    __tablename__ = 'production_feedbacks'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    step_id = Column(Integer)  # Reference to Production Management Service (can be null for batch-level feedback)
    status = Column(String(20), nullable=False)  # pending, in_progress, completed, cancelled, failed
    completion_percentage = Column(Float, default=0)
    quality_score = Column(Float)  # 0-100 score representing quality
    quality_data = Column(JSON)  # Detailed quality measurements
    issues = Column(Text)  # Description of any issues encountered
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ProductionHistory(Base):
    __tablename__ = 'production_histories'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    batch_number = Column(String(50))  # Denormalized for easier querying
    product_id = Column(Integer, nullable=False)  # Product being manufactured
    quantity = Column(Integer, nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_minutes = Column(Integer)  # Duration in minutes
    status = Column(String(20), nullable=False)  # completed, cancelled, failed
    marketplace_order_id = Column(String(50))  # Reference to marketplace order
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class QualityCheck(Base):
    __tablename__ = 'quality_checks'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    step_id = Column(Integer)  # Reference to Production Management Service (can be null for batch-level checks)
    check_type = Column(String(50), nullable=False)  # visual, measurement, function_test, etc.
    parameter_name = Column(String(100), nullable=False)  # What was checked
    expected_value = Column(String(100))
    actual_value = Column(String(100))
    passed = Column(Boolean, nullable=False)
    severity = Column(Integer)  # 1=low, 2=medium, 3=high
    notes = Column(Text)
    checked_by = Column(String(100))  # Person or system that performed the check
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class MarketplaceNotification(Base):
    __tablename__ = 'marketplace_notifications'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, nullable=False)  # Reference to Production Management Service
    marketplace_order_id = Column(String(50), nullable=False)
    notification_type = Column(String(50), nullable=False)  # status_update, delay, quality_issue, etc.
    message = Column(Text, nullable=False)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    success = Column(Boolean)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def init_db():
    """Initialize the database with tables"""
    db_config = get_db_config("production_feedback")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Create a session factory
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Get a new database session"""
    db_config = get_db_config("production_feedback")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
