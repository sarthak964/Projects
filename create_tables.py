from app.core.database import Base, engine
from app import models  # noqa: F401 -- import so all models register with Base

Base.metadata.create_all(bind=engine)
print("Tables created successfully.")
