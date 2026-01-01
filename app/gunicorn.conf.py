import os
import gunicorn
bind = os.getenv("BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Safer defaults
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
