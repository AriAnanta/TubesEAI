import subprocess
import sys
import os
import time
import threading
import signal
import mysql.connector
from mysql.connector import Error

# Define services
services = [
    {"name": "Material Inventory Service", "path": "material_inventory", "port": 5004},
    {"name": "Production Planning Service", "path": "production_planning", "port": 5002},
    {"name": "Machine Queue Service", "path": "machine_queue", "port": 5003},
    {"name": "Production Management Service", "path": "production_management", "port": 5001},
    {"name": "Production Feedback Service", "path": "production_feedback", "port": 5005}
]

processes = []

def setup_database():
    """Create MySQL databases for each service if they don't exist"""
    try:
        # Connect to MySQL
        connection = mysql.connector.connect(
            host="localhost",
            user="root",  # Update with your MySQL username
            password="",   # Update with your MySQL password
            port=3308
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create databases for each service
            for service in services:
                db_name = f"manufacturing_{service['path']}"
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"Database '{db_name}' created or already exists")
            
            cursor.close()
            connection.close()
            print("Database setup complete")
            return True
    except Error as e:
        print(f"Error setting up databases: {e}")
        return False

def start_service(service):
    """Start a microservice in a separate process"""
    service_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), service["path"])
    
    try:
        process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=service_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        processes.append(process)
        
        print(f"Started {service['name']} on port {service['port']}")
        
        # Print output from the process
        for line in process.stdout:
            print(f"[{service['name']}] {line.strip()}")
    except Exception as e:
        print(f"Error starting {service['name']}: {e}")

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully terminate all processes"""
    print("\nShutting down all services...")
    
    for process in processes:
        if process.poll() is None:  # If process is still running
            process.terminate()
    
    # Wait for processes to terminate
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    
    print("All services stopped")
    sys.exit(0)

def main():
    """Main function to start all services"""
    print("=== On-Demand Manufacturing Microservices ===")
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Setup databases
    if not setup_database():
        print("Failed to setup databases. Please check your MySQL configuration.")
        return
    
    # Start each service in a separate thread
    threads = []
    for service in services:
        thread = threading.Thread(target=start_service, args=(service,))
        thread.daemon = True
        threads.append(thread)
        thread.start()
        # Small delay to avoid race conditions
        time.sleep(1)
    
    print("\nAll services started. Press Ctrl+C to stop all services.\n")
    
    # Keep the main thread running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
