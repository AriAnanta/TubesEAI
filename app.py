from flask import Flask, jsonify, request
from flask_graphql import GraphQLView
from flask_cors import CORS
import os
import sys
import pymysql

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_db_config

# Import schema and models
from schema import schema
from models import init_db

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure the app
service_name = "production_planning"
port = int(os.getenv(f"{service_name.upper()}_PORT", 5002))

@app.route('/')
def index():
    return jsonify({
        "service": "Production Planning Service",
        "status": "running",
        "endpoints": {
            "graphql": "/graphql",
            "health": "/health"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "Production Planning Service"
    })

# Add GraphQL endpoint
app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view(
        'graphql',
        schema=schema,
        graphiql=True  # Enable GraphiQL for easy testing
    )
)

def create_database():
    """Create the database if it doesn't exist"""
    db_config = get_db_config(service_name)
    
    # Connect to MySQL without specifying the database
    connection = pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        port=db_config['port']
    )
    
    try:
        with connection.cursor() as cursor:
            # Create the database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        connection.commit()
    finally:
        connection.close()

if __name__ == '__main__':
    # Create database if it doesn't exist
    try:
        create_database()
        # Initialize database tables
        init_db()
        print(f"Database '{get_db_config(service_name)['database']}' and tables initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=True)
