import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

db_pool = None
try:
    # Initialize the connection pool
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=10,
        pool_reset_session=True,
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "exam_system")
    )
except Exception as e:
    print(f"Warning: Could not initialize global DB pool: {e}")

def get_db():
    """Returns a connection from the global pool."""
    try:
        return db_pool.get_connection()
    except Exception as e:
        print(f"Error getting DB connection from pool: {e}")
        # Fallback to direct connection if pool fails
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "exam_system")
        )
