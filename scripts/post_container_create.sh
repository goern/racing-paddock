#!/usr/bin/env bash
pipenv install --dev
pipenv run ./manage.py migrate
pipenv run ./manage.py loaddata driver game fastlap fastlapsegment landmark lap session sessiontype track trackguide trackguidenote coach car copilot copilotinstance profile user
DJANGO_SUPERUSER_PASSWORD=admin pipenv run ./manage.py createsuperuser  --username admin --email admin@example.com --noinput || true
