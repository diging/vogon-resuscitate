#!/bin/sh

BASH_ENV=.env_app
mkdir -p /vogon/logs
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf