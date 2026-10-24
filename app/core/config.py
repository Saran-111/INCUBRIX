import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Service Information
    APP_NAME: str = "IncuBrix Long-Tail Distribution Connector Service"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    CONNECTOR_V1_PREFIX: str = "/connector/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Server Binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Simulation & Mock Mode (Must-have 7)
    # When True, all platform API calls route to internal mock platform simulators
    SIMULATION_MODE: bool = True
    MOCK_LATENCY_MS: int = 50
    MOCK_FAILURE_RATE: float = 0.0
    
    # Secret protection & HMAC
    HMAC_SECRET: str = "incubrix-super-secret-hmac-key-for-testing-only"
    WEBHOOK_SIGNATURE_HEADER: str = "X-IncuBrix-Signature"
    
    # Storage (Integration Standard 7)
    STORAGE_TYPE: str = "local"  # "s3" or "local"
    LOCAL_STORAGE_DIR: str = "./storage_data"
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY: Optional[str] = "minioadmin"
    S3_SECRET_KEY: Optional[str] = "minioadmin"
    S3_BUCKET_NAME: str = "incubrix-artifacts"
    S3_REGION: str = "us-east-1"
    
    # External API Base URLs (Defaults point to local instances or mock routes)
    LEMMY_BASE_URL: str = "http://localhost:8536"
    GHOST_BASE_URL: str = "http://localhost:2368"
    DISCOURSE_BASE_URL: str = "http://localhost:4200"
    DEVTO_BASE_URL: str = "https://dev.to/api"
    HASHNODE_BASE_URL: str = "https://gql.hashnode.com"
    SLACK_BASE_URL: str = "https://slack.com/api"
    MAILCHIMP_BASE_URL: str = "https://us1.api.mailchimp.com/3.0"
    
    # Rules Engine Default Windows
    FREQUENCY_CAP_WINDOW_HOURS: int = 24
    MAX_POSTS_PER_WINDOW: int = 1
    AUTO_DELETE_MAX_MINUTES: int = 10
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
