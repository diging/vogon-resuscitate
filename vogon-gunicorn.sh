#!/bin/bash

NAME="vogon"                                  # Name of the application
DJANGODIR=/vogon                              # Django project directory
NUM_WORKERS=3                                 # Number of Gunicorn workers
DJANGO_SETTINGS_MODULE=vogon.settings          # Django settings module
DJANGO_WSGI_MODULE=vogon.wsgi                  # WSGI module name

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source .env_app
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH
mkdir -p /vogon/logs
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --bind=0.0.0.0:8000 \
  --log-level=info \
  --log-file /vogon/logs/vogon_supervisor.log