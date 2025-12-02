import time
from typing import Dict, Any, Optional, Tuple, Callable, ClassVar, TypeVar, Type

T = TypeVar('T')

class Cache:
    """A simple in-memory cache with expiration.
    
    This cache implementation provides a way to store key-value pairs with optional
    expiration times. It's useful for caching data that is expensive to compute or
    retrieve from a database, but should be refreshed periodically.
    
    Attributes:
        cache (Dict): The internal cache storage
        default_ttl (int): Default time-to-live in seconds for cache entries
    """
    
    @classmethod
    def __class_getitem__(cls, item):
        # This method enables the class to be used with subscripts in type annotations
        # For example: Cache[str] or Cache[User]
        return cls
    
    def __init__(self, default_ttl: int = 300):
        """Initialize a new Cache instance.
        
        Args:
            default_ttl: Default time-to-live in seconds for cache entries (default: 300s)
        """
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: The cache key to retrieve
            
        Returns:
            The cached value if present and not expired, otherwise None
        """
        if key not in self.cache:
            return None
            
        value, expiry = self.cache[key]
        if expiry < time.time():
            # Value has expired
            self.delete(key)
            return None
            
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional expiration.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self.cache[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Delete a value from the cache.
        
        Args:
            key: The cache key to delete
        """
        if key in self.cache:
            del self.cache[key]
    
    def flush(self) -> None:
        """Clear all entries from the cache."""
        self.cache.clear()
    
    def get_or_set(self, key: str, default_func: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """Get a value from cache or compute and store it if not present.
        
        Args:
            key: The cache key
            default_func: Function to compute the value if not in cache
            ttl: Time-to-live in seconds (uses default if not specified)
            
        Returns:
            The cached or computed value
        """
        value = self.get(key)
        if value is None:
            value = default_func()
            self.set(key, value, ttl)
        return value

class TimedCache(Cache):
    """A cache that automatically expires entries after a set time.
    
    This is a specialized version of Cache where all entries have the same TTL
    and cannot be overridden when setting values.
    
    Attributes:
        cache (Dict): The internal cache storage
        ttl (int): Time-to-live in seconds for all cache entries
    """
    
    def __init__(self, ttl: int = 300, max_age: Optional[int] = None):
        """Initialize a new TimedCache instance.
        
        Args:
            ttl: Time-to-live in seconds for all cache entries (default: 300s)
            max_age: Alias for ttl, for backward compatibility
        """
        # Use max_age if provided, otherwise use ttl
        actual_ttl = max_age if max_age is not None else ttl
        super().__init__(default_ttl=actual_ttl)
        self.ttl = actual_ttl
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with fixed expiration time.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Ignored parameter (included for API compatibility)
        """
        # Always use the cache's TTL, ignoring any provided TTL
        super().set(key, value, self.ttl)
