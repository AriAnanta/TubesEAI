from flask import Flask, jsonify, request
from flask_graphql import GraphQLView
from flask_cors import CORS
import os
import sys
import pymysql

# Tambahkan direktori induk ke path untuk mengimpor modul umum
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

# Impor skema dan model
from schema import schema
from models import init_db

# Inisialisasi aplikasi Flask
app = Flask(__name__)
CORS(app)

# Konfigurasi aplikasi
service_name = "production_management"
port = int(os.getenv(f"{service_name.upper()}_PORT", 5001))

@app.route('/')
def index():
    return jsonify({
        "service": "Layanan Manajemen Produksi",
        "status": "berjalan",
        "endpoints": {
            "graphql": "/graphql",
            "health": "/health"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "sehat",
        "service": "Layanan Manajemen Produksi"
    })

# Tambahkan endpoint GraphQL
app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view(
        'graphql',
        schema=schema,
        graphiql=True  # Aktifkan GraphiQL untuk pengujian yang mudah
    )
)

def create_database():
    """Buat database jika belum ada"""
    db_config = get_db_config(service_name)
    
    # Koneksi ke MySQL tanpa menentukan database
    connection = pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        port=db_config['port']
    )
    
    try:
        with connection.cursor() as cursor:
            # Buat database jika belum ada
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        connection.commit()
    finally:
        connection.close()

if __name__ == '__main__':
    # Buat database jika belum ada
    try:
        create_database()
        # Inisialisasi tabel database
        init_db()
        print(f"Database '{get_db_config(service_name)['database']}' dan tabel berhasil diinisialisasi")
    except Exception as e:
        print(f"Error saat menginisialisasi database: {e}")
    
    # Jalankan aplikasi Flask
    app.run(host='0.0.0.0', port=port, debug=True)
