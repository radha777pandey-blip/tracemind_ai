class AppConfig:
    """Application configuration settings."""
    DATABASE_URL: str = 'sqlite:///ecommerce.db'
    JWT_SECRET: str = 'super-secret-key-12345'
    PAYMENT_GATEWAY_KEY: str = 'pk_live_987654321'
    DEBUG: bool = True

config = AppConfig()
