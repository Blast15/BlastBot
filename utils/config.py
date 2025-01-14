import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Quản lý cấu hình của bot"""
    
    # Token bot Discord
    TOKEN = os.getenv("TOKEN")
    
    # Prefix mặc định
    DEFAULT_PREFIX = "?"