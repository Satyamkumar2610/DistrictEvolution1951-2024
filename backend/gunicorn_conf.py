import os

# Gunicorn configuration for Render deployment

# Bind to the port defined in environment or default to 8000
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Worker configuration
# For CPU-bound tasks, use (2 * cpu) + 1 workers
# For I/O-bound (like this API), we can use more, or use Uvicorn workers
workers = 2  # Start conservative for free tier
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 120  # 2 minutes
keepalive = 5

# Logging
loglevel = "info"
accesslog = "-"  # Stdout
errorlog = "-"   # Stderr

# Process naming
proc_name = "i-ascap-api"
