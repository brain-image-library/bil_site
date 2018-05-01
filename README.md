# Brain Image Library - Django Site

## Instructions

To run the website locally, do the following:

    python3 -m venv bil_site_venv
    source bil_site_venv/bin/activate
    pip install -r requirements.txt
    python manage.py makemigrations
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

If the server is successfully running, navigate your browser to
127.0.0.1:8000/ingest/index
