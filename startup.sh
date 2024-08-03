#!/bin/sh

. /code/.env-app
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000