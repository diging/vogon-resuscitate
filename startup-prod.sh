#!/bin/sh

source .env_app
mkdir -p /vogon/logs
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
service supervisor start