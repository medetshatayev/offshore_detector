"""
Main entrypoint for the Offshore Transaction Risk Detection System.
Runs the FastAPI web application.
"""
import os
import sys
import logging

# Ensure logger is configured before other imports
from logger import setup_logging
setup_logging()

from web_app import app


def check_environment():
    """
    Check that required environment variables are set.
    """
    required_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.warning(
            f"Missing environment variables: {', '.join(missing_vars)}. "
            "The application may not function correctly."
        )
        return False
    
    return True


def main():
    """
    Main entrypoint.
    """
    logging.info("=" * 80)
    logging.info("Offshore Transaction Risk Detection System")
    logging.info("=" * 80)
    
    # Check environment
    env_ok = check_environment()
    if not env_ok:
        logging.warning("Environment check failed. Some features may not work.")
    
    # Log configuration
    logging.info(f"OpenAI Model: {os.getenv('OPENAI_MODEL', 'gpt-4o')}")
    logging.info(f"Amount Threshold: {os.getenv('THRESHOLD_KZT', '5000000')} KZT")
    logging.info(f"Output Path: {os.getenv('DESKTOP_PATH', 'default')}")
    logging.info(f"Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logging.info("=" * 80)
    
    # Run the app
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logging.info(f"Starting web server on {host}:{port}")
    
    uvicorn.run(
        "web_app:app",
        host=host,
        port=port,
        reload=os.getenv('DEBUG', 'false').lower() == 'true',
        log_level=os.getenv('LOG_LEVEL', 'info').lower()
    )


if __name__ == "__main__":
    main()
