import os
from sqlalchemy import create_engine

# Get the directory where the files are located
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'events.db')

# Add connection pooling for better performance
engine = create_engine(
    f'sqlite:///{db_path}', 
    connect_args={"check_same_thread": False},
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Additional connections that can be created
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600  # Recycle connections after 1 hour
) 