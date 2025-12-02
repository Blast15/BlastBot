import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """A configuration class that stores discord bot settings.
    This class is responsible for managing configuration settings used throughout the bot,
    including the Discord bot token and default command prefix.
    Attributes:
        TOKEN (str): The Discord bot authentication token retrieved from environment variables.
        DEFAULT_PREFIX (str): The default command prefix used for bot commands (set to "?").
    """
    
    # Token bot Discord
    TOKEN = os.getenv("TOKEN")
    
    # Prefix mặc định
    DEFAULT_PREFIX = "?"