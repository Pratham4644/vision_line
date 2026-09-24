from database import engine, Base
from models import Camera

Base.metadata.create_all(bind=engine)

print("Database initialized successfully.")