"""
Django settings for bil_site project.

Generated by 'django-admin startproject' using Django 2.2.17.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os
import configparser
import sys
import mimetypes
from django.contrib import messages

mimetypes.add_type("text/javascript", ".js", True)

site_cfg_misconfigured = (
    "The site.cfg file exists but is not properly configured. The key '{}' is "
    "missing. See example.cfg as a reference.")

if not os.path.isfile('site.cfg'):
    print('The site.cfg file is missing. Please generate one and put it '
          'relative to where the manage.py Python process is starting '
          '(typically it goes in ./bil_site). See example.cfg '
          'as a reference.')
    sys.exit(1)

essential_site_cfg_keys = [
    'SECRET_KEY', 'DEBUG', 'IMG_DATA_HOST', 'DB_HOST',
    'FAKE_STORAGE_AREA', 'DATABASE', 'STAGING_AREA_ROOT'
]

config = configparser.ConfigParser()
config.read('site.cfg')

# just test if they exist. still need to assign them later
for k in essential_site_cfg_keys:
    try:
        _ = config['Security'][k]
    except KeyError as e:
        print(site_cfg_misconfigured.format(k))
        sys.exit(1)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# See example.cfg for reference. You can generate a new secret key like this:
# python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())'')'
SECRET_KEY = config['Security']['SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config['Security'].getboolean('DEBUG')

# This will look like it is creating remote storage areas, but really does
# nothing. It's just for testing purposes.
FAKE_STORAGE_AREA = config['Security'].getboolean('FAKE_STORAGE_AREA')

IMG_DATA_HOST = config['Security']['IMG_DATA_HOST']
STAGING_AREA_ROOT = config['Security']['STAGING_AREA_ROOT']

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# JWT for Specimen Portal

SPECIMEN_PORTAL_JWT = config['Security']['SPECIMEN_PORTAL_JWT']

LOGIN_REDIRECT_URL = '/'

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'ingest.apps.IngestConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_tables2',
    'django_celery_results',
    'django_filters',
    'bootstrap4',
    'django_pam',
    'hijack',
    'hijack.contrib.admin',
    'django.contrib.humanize',
    #'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'hijack.middleware.HijackUserMiddleware',
]

ROOT_URLCONF = 'bil_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['./templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bil_site.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
DATABASE = config['Security']['DATABASE']

if DATABASE == "postgres":
    k = 'DATABASE_PASSWORD'
    try:
        DATABASE_PASSWORD = config['Security'][k]
    except KeyError as e:
        print(site_cfg_misconfigured.format(k))
        sys.exit(1)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': config['Security']['DATABASE_NAME'],
            'USER': config['Security']['DATABASE_USER'],
            'PASSWORD': DATABASE_PASSWORD,
            'HOST': config['Security']['DB_HOST'],
            'PORT': '',
        }
    }
elif DATABASE == "sqlite":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
else:
    print("Unknown DATABASE option used in site.cfg. Please set 'DATABASE = "
          "postgres' or 'DATABASE = sqlite'.")
    sys.exit(1)


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    'django_pam.auth.backends.PAMBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

CELERY_RESULT_BACKEND = 'django-db'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

MESSAGE_TAGS = {
    messages.ERROR: 'danger'
}

#Email Settings
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = '587'
EMAIL_HOST_USER = config['Security']['EMAIL_USER']
EMAIL_HOST_PASSWORD = config['Security']['EMAIL_PASSWORD']
EMAIL_USE_TLS = True
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#EMAIL_USE_SSL = False
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
