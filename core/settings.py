from pathlib import Path
import os
import dj_database_url  # Import added

BASE_DIR = Path(__file__).resolve().parent.parent

# Render environment variables ke liye secure handling (quotes hatakar)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-z=d!p$77#6-e&y^%p1l_r#x^0#y#x1k6q78d@a7z_r8m1o(0=u')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,trekemail-python.onrender.com').split(',')

# --- TIME ZONE CONFIGURATION ---
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'core.wsgi.application'

# --- DATABASE CONFIGURATION (PostgreSQL via Render & fallback to SQLite) ---
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- EMAIL CONFIGURATION (Brevo SMTP) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))  # TLS ke liye port 587 best hai
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'ae9d6001asmtp-brevo.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')  # Render environment variable se aayega

# --- BREVO API & VERIFIED SENDER CONFIGURATION ---
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')

# Ab aapka verified custom domain sender yahan set hai
DEFAULT_FROM_EMAIL = 'Scriza <support@hvacpro.com.au>'

EMAIL_TIMEOUT = 120

# --- SESSION ENGINE CONFIGURATION (File Based) ---
SESSION_ENGINE = 'django.contrib.sessions.backends.file'