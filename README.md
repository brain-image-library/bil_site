# Brain Image Library - Django Site


## Installation and Setup

To set up the website locally for the first time, do the following:

    python3 -m venv bil_site_venv
    source bil_site_venv/bin/activate
    pip install -r requirements.txt

You need to create a file called `site.cfg` file in the main directory, which
will store the secret key and various other secret or server specific settings.
You can see an example in `example.cfg`. You *must* generate a new secret key
when using this site in production, which you can do like this:

    cp example.cfg site.cfg
    python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())'

In site.cfg, replace the value associated `SECRET_KEY` with the value you
generated from the previous command. Note: certain characters will throw off
the config parser. The easiest thing to do is to just generate a different key.

You'll also want to change IMG_DATA_USER to whatever PSC username you have on
DXC. You could also change the IMG_DATA_HOST to say your local machine for
offline testing. This assumes a passwordless authentication like using [ssh
keys](https://linuxconfig.org/passwordless-ssh). The way remote directory
creation/destruction/management will work in production is still being
determined. It likely will be handled by one account that manages the
appropriate permissions.

Next, we'lll set up the database and create a super user:

    python manage.py makemigrations
    python manage.py migrate --run-syncdb
    python manage.py createsuperuser

You also need to install rabbitMQ, which is pretty easy if you're using Ubuntu:

    sudo apt-get install rabbitmq-server

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
