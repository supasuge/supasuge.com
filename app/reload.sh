#!/bin/bash
python ./scripts/sync.py || echo "failed"; exit 1
gunicorn --config gunicorn.conf.py "wsgi:app" || echo "gunicorn goofed" exit 1
