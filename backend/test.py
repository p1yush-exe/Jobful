from core.config import settings
from db.connection import create_connection

print('DB URL set:', bool(settings.database_url))
conn = create_connection()
print('DB connected OK')
conn.close()
