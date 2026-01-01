#!/bin/bash
python ./scripts/sync.py || echo "failed"
gunicorn --config gunicorn.conf.py "wsgi:app" || echo "gunicorn goofed"
