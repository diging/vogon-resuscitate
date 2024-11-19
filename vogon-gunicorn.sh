#!/bin/bash

NAME="vogon"                                  # Name of the application
DJANGODIR=/vogon                              # Django project directory
SOCKFILE=/usr/src/app/run/jars.sock           # Unix socket for communication
NUM_WORKERS=3                                 # Number of Gunicorn workers
DJANGO_SETTINGS_MODULE=jars.settings          # Django settings module
DJANGO_WSGI_MODULE=jars.wsgi                  # WSGI module name
LOGFILE=/var/log/$NAME/gunicorn.log           # Log file path

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source .env
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --bind=0.0.0.0:8000 \
  --log-level=info \
  --log-file=-