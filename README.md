# Brain Image Library - Django Site


## Installation and Setup

To set up the website locally for the first time, do the following:

    python3 -m venv bil_site_venv
    source bil_site_venv/bin/activate
    pip install -r requirements.txt
    python manage.py makemigrations
    python manage.py migrate --run-syncdb
    python manage.py createsuperuser

You also need to install rabbitMQ, which is pretty easy if you're using Ubuntu:

    sudo apt-get install rabbitmq-server

You'll also need to set up a a site.cfg file in the main directory, which will
store the secret key and various other secret or server specific settings. You
can see an example in example.cfg. You must generate a new secret key when
using this site in production, which you can do like this:

    python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())'')'

Copy the value generated here into site.cfg after `SECRET_KEY = `.

## Serving the Django Site

In one terminal, start Celery and leave it running while the server is up:

    celery -A bil_site worker -l info

In a separate terminal, start Django itself:

    python manage.py runserver

Make sure the python virtual environment is active in both terminals. You can
activate it by typing:

    source bil_site_venv/bin/activate

If the server is successfully running, navigate your browser to
[127.0.0.1:8000](127.0.0.1:8000).

Now that you've created your virtual environment, you should usually only have
to run these two commands in the future:

    source bil_site_venv/bin/activate
    python manage.py runserver

Note: you only have to run the `source` command again if you open a different
terminal or explicitly `deactivate`.

## Updating the Site

If you ever change the models, you'll likely have to re-run the migrate
commands:

    python manage.py makemigrations
    python manage.py migrate --run-syncdb
