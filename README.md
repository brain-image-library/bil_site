# Brain Image Library - Submission Portal

## About

The Brain Image Library (BIL) is a national public resource enabling
researchers to deposit, analyze, mine, share and interact with large brain
image datasets. The BIL is supported by the National Institute of Mental Health
of the National Institutes of Health under award number R24MH114793.

To deposit data, a user needs to create a bundle and one or more associated
pieces of metadata. In a typical use-caseWhen a bundle is created, a landing zone will also be
created where the data can be uploaded.

The BIL submission portal is built upon
[Django](https://www.djangoproject.com/), a Python web framework. For basic
development, you'll only need Python 3. In production, you'll need to set up a
few other dependecies. NGINX is the web-server and reverse proxy. Gunicorn is
the interface between NGINX and the Django app itself. RabbitMQ and Celery are
used for asynchronous validation and submission. PostgreSQL is the database
used to store all the Django models (i.e. collections and image metadata)

## Installation and Setup for Production (CentOS 7)

You'll need to install Python3, RabbitMQ, NGINX, Gunicorn, and PostgreSQL.
There are other requirements, but they are handled via Python virtual
environments.

Run the following command to set up postgres:

    sudo postgresql-setup initdb

Create `gunicorn.service` in `/etc/systemd/system/gunicorn.service`:

    [Unit]
    Description=gunicorn daemon
    After=network.target

    [Service]
    User=<username>
    Group=<groupname>
    WorkingDirectory=<top_level_path>/bil_site
    ExecStart=<top_level_path>/bil_site/bil_site_venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:<top_level_path>/bil_site/bil_site.sock bil_site.wsgi

    [Install]
    WantedBy=multi-user.target

Be sure to change any of the values listed in angle brackets like `<username>`
and `<groupname>`.

In your NGINX conf file, add the following to the `server` section:

    server {
        listen <port number;
        server_name <host_name>;

        location = /favicon.ico { access_log off; log_not_found off; }
        location /static/ {
            root <top_level_dir>/bil_site;
        }

        location / {
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://unix:<top_level_dir>/bil_site/bil_site.sock;
        }
    }

Once again, you'll need to change the options in angle brackets.

Make sure the following packages are running and enabled at startup:

    sudo systemctl start postgresql
    sudo systemctl start nginx
    sudo systemctl start gunicorn
    sudo systemctl start rabbitmq-server
    sudo systemctl enable postgresql
    sudo systemctl enable nginx
    sudo systemctl enable gunicorn
    sudo systemctl enable rabbitmq-server

## Installation and Setup for Development (Ubuntu 16.04 and newer)

Unlike CentOS, Python 3 should already be installed on Ubuntu. In development,
you'll be using the built-in development server, so you won't need NGINX or
Gunicorn. Also, you'll be using SQLite, so you won't need Postgres. You only
need RabbitMQ if you'd like to test the submission and validation tools for the
website. 

## Installation and Setup for Development and Production

To set up the website locally for the first time, do the following:

    python3 -m venv bil_site_venv
    source bil_site_venv/bin/activate
    pip install -r requirements.txt

You need to create a file called `site.cfg` file in the top level directory,
which will store the secret key and various other secret or server specific
settings. You can see an example in `example.cfg`. You *must* generate a new
secret key when using this site in production, which you can do like this:

    cp example.cfg site.cfg
    python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())'

In site.cfg, replace the value associated `SECRET_KEY` with the value you
generated from the previous command. Note: certain characters will throw off
the config parser. The easiest thing to do is to just generate a different key.

In production, you'll want to set the following:

    DEBUG = no
    FAKE_STORAGE_AREA = no
    DATABASE = postgres

In development, if you set `DEBUG = yes`, you'll get tracebacks instead of 404
or 500 error pages. If you want to do development without worrying about the
asynchronous validation and submission, you can set `FAKE_STORAGE_AREA = yes`.

If using postgres, you'll need to set the `DATABASE_PASSWORD` too.

The `STAGING_AREA_ROOT` is the top level directory where users will upload
their data.

Next, we'll set up the database and create a super user:

    python manage.py makemigrations
    python manage.py migrate --run-syncdb
    python manage.py createsuperuser

## Serving the Django Site (in development)

For this next step, you'll set up Celery in one terminal and Django in another.
Make sure the Python virtual environment is running in both terminals before
you launch django or celery:

    source bil_site_venv/bin/activate

Note: you only have to run the `source` command again if you open a different
terminal or explicitly `deactivate`.

In one terminal, start Celery and leave it running while the server is up:

    celery -A bil_site worker -l info --config celeryconfig.py -E

In a separate terminal, start Django itself:

    python manage.py runserver

If the server is successfully running, navigate your browser to
[127.0.0.1:8000](127.0.0.1:8000).

## Serving the Django Site (in production)

In one terminal, start Celery and leave it running while the server is up:

    celery -A bil_site worker -l info --config celeryconfig.py -E

Note: this eventually needs to be done using systemd, so it's running in the
background when the system starts up.

Make sure nginx, gunicorn, and postgres are running:

    sudo systemctl status postgresql
    sudo systemctl status nginx
    sudo systemctl status gunicorn

If not, they can be started like this:

    sudo systemctl start postgresql
    sudo systemctl start nginx
    sudo systemctl start gunicorn

## Updating the Site (development and production)

If you ever change the models, you'll likely have to re-run the migrate
commands:

    python manage.py makemigrations
    python manage.py migrate --run-syncdb

## Updating the Site (production)

You'll want to collect all the static files:

    python manage.py collectstatic

You'll also want to restart gunicorn:

    sudo systemctl restart gunicorn

# BIL Branching, Merging, and Publishing Procedures

## Branching
_`Dev` will act as the major merge point for all feature and bug branches, leaving `master` for publishing to production exclusively._
### Creating a Feature branch
  - This can all be done from within the terminal
    - `git checkout dev`
    - `git pull` to update your local instance of `dev`
    - When naming a branch, it's good practice to use dashes `-` and not underscores `_` as the general naming for files contains underscores
      - `git checkout -b <feature/name>` <---this simultaneously creates a new branch off of `dev` and checks it out
      - e.g. `git checkout -b feature/metadata-validation`
    - When you are ready to add a commit to the branch: `git status` to see all changed files
      - files can be added all at once with a simple `git add .` or individually with `git add <filename>`
    - To commit what has just been added: `git commit -m "this is your commit message, make it helpful and descriptive"`
      - e.g. `git commit -m "added validation checking metadata spreadsheet headers for missing values"`
    - To push those commits: 
      - For your first push of this branch, you will need: `git push -u origin <feature/name>` <-- this sets your pushes upstream
      - For all pushes after the first, as simple `git push` will do  
### Creating a Bug branch
  - This can all be done from within the terminal
    - `git checkout dev`
    - `git pull` to update your local instance of `dev`
    - When naming a bug branch, it's good practice to associate it with the issue it is fixing
      - `git checkout -b <i/#>` <---where the `i` is for `issue` and the # represents the issue number being fixed
      - e.g. `git checkout -b i/128`
    - When you are ready to add a commit to the branch: `git status` to see all changed files
      - files can be added all at once with a simple `git add .` or individually with `git add <filename>`
    - To commit what has just been added: `git commit -m "this is your commit message, make it helpful and descriptive"`
      - e.g. `git commit -m "fixing issue #128"`
    - To push those commits: 
      - For your first push of this branch, you will need: `git push -u origin <i/#>` <-- this sets your pushes upstream
      - For all pushes after the first, as simple `git push` will do  

## Creating a Pull Request
_PRs are great for seeing what's changed and doing code reviews/discussions_
  - This is all done from the github gui
  - Visit https://github.com/brain-image-library/bil_site/compare
  - Keep the base as `dev` and choose the feature or bug branch you created for the `compare`, click `Create Pull Request`
  - From there, you can add checklists and descriptions within the PR. This is especially helpful to stay organized and give the code reviewer an idea of what to look for
  - PRs should be concise and focus on targeted code changes


## Cutting a Release of BIL
_This is assuming that all feature branches have been merged to `dev`, `dev` has been tested, and any bug fixes have been merged_

## Tagging Dev
- This can all be done within the terminal. We'll also be tagging `master`. For more general info on tagging, check this out. We want the **annotated** tagging method.
  https://git-scm.com/book/en/v2/Git-Basics-Tagging For more information on what makes a version number, checkout more about Semantic Versioning http://semver.org/
  - `git checkout dev`
  - `git pull` to check that your local instance of `dev` is up to date
  - `git tag -a vX.X.X -m "BIL release version X.X.X"`
  - `git push origin vX.X`

## Creating a Release
- This step will be completed from the git gui. You will also need the notes compiled from the BIL Publishes sheet https://docs.google.com/spreadsheets/d/1kozFEBV2jUr0K7EM_rNKNEiikAzoULgZ11tcS_KYl_A/edit#gid=0.
  - Each branch that has been merged to `dev` will be recorded on the BIL Publishes sheet. Their branch names and descriptions will be listed, merge to `dev` will be contained within the same row, which will result in each release version occupying its own row.
  - Add the date to the row with accumulated branches and descriptions currently in `dev`
  - change `dev` in the Version column to the vX.X.X tag you created in the previous step
  - Within the git gui, go to https://github.com/brain-image-library/bil_site/releases/new
  - Add the tag version you previously created with the `Target: dev`
  - Release title can match the tag version `vX.X.X`
  - Within `Describe this release` paste in the Branch Name / Bug Fixes and Description values from the BIL Publishes sheet

## Merging to Master
- You'll merge `dev` into `master`:
  - `git checkout master`
  - `git pull`
  - `git merge dev` <-- this will merge `dev` into `master`
  - `git push`
