from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import sys
import os

# Tambahkan direktori induk ke path untuk mengimpor modul umum
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

Base = declarative_base()

class ProductionBatch(Base):
    __tablename__ = 'production_batches'
    
    id = Column(Integer, primary_key=True)
    batch_number = Column(String(50), unique=True, nullable=False)
    order_id = Column(String(50))  # Referensi ke pesanan marketplace
    product_id = Column(Integer, nullable=False)  # Produk yang diproduksi
    quantity = Column(Integer, nullable=False)
    priority = Column(Integer, default=1)  # 1=rendah, 2=sedang, 3=tinggi
    status = Column(String(20), default='pending')  # pending, in_progress, completed, cancelled
    production_plan_id = Column(Integer)  # Referensi ke Layanan Perencanaan Produksi
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relasi
    production_steps = relationship("ProductionStep", back_populates="batch")

class ProductionStep(Base):
    __tablename__ = 'production_steps'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('production_batches.id'))
    step_number = Column(Integer)
    name = Column(String(100), nullable=False)
    machine_type = Column(String(50))  # Jenis mesin yang diperlukan untuk langkah ini
    status = Column(String(20), default='pending')  # pending, in_progress, completed, skipped
    duration_minutes = Column(Integer)  # Perkiraan durasi dalam menit
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    machine_queue_id = Column(Integer)  # Referensi ke Layanan Antrian Mesin
    notes = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relasi
    batch = relationship("ProductionBatch", back_populates="production_steps")
    materials = relationship("StepMaterial", back_populates="step")

class StepMaterial(Base):
    __tablename__ = 'step_materials'
    
    id = Column(Integer, primary_key=True)
    step_id = Column(Integer, ForeignKey('production_steps.id'))
    material_id = Column(Integer, nullable=False)  # Referensi ke Layanan Inventori Material
    quantity_required = Column(Float, nullable=False)
    is_consumed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relasi
    step = relationship("ProductionStep", back_populates="materials")

class ProductDefinition(Base):
    __tablename__ = 'product_definitions'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, unique=True, nullable=False)  # ID produk eksternal
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    production_workflow = Column(JSON)  # JSON yang mendefinisikan langkah dan material
    standard_batch_size = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    """Inisialisasi database dengan tabel"""
    db_config = get_db_config("production_management")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:3308/{db_config['database']}"
    
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    
    # Buat factory sesi
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

def get_session():
    """Dapatkan sesi database baru"""
    db_config = get_db_config("production_management")
    connection_string = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:3308/{db_config['database']}"
    
    engine = create_engine(connection_string)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
