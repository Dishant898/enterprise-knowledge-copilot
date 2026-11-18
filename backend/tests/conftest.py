import os

os.environ.setdefault("DATABASE_URL", "postgresql://app:secret@localhost:5432/app")
os.environ.setdefault("REDIS_URL", "redis://:secret@localhost:6379/0")
