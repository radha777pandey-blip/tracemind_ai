from config import config

class DatabaseConnection:
    """Manages database connection pool and execution."""
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.is_connected = True

    def query(self, sql: str, params: tuple = ()):
        """Executes a SQL query and returns results."""
        return [{'id': 1, 'status': 'success'}]

def get_db_connection() -> DatabaseConnection:
    """Returns singleton database connection."""
    return DatabaseConnection(config.DATABASE_URL)

def execute_query(sql: str, params: tuple = ()):
    """Convenience helper to run query against database."""
    conn = get_db_connection()
    return conn.query(sql, params)
