import os
from flask_appbuilder.security.manager import (
    AUTH_OID,
    AUTH_REMOTE_USER,
    AUTH_DB,
    AUTH_LDAP,
    AUTH_OAUTH,
)

basedir = os.path.abspath(os.path.dirname(__file__))

#set static folder used to populate requests to static resources
if os.getenv('FAB_STATIC_FOLDER'):
    FAB_STATIC_FOLDER = os.getenv('FAB_STATIC_FOLDER')
if os.getenv('FAB_STATIC_URL_PATH'):
    FAB_STATIC_URL_PATH = os.getenv('FAB_STATIC_URL_PATH')

# Your App secret key
SECRET_KEY = os.getenv('SECRET_KEY', "\2\1thisismyscretkey\1\2/e/y/y/h")

# pass these through the environment variables or set default
PRODUCTION = os.getenv('ENVIRONMENT', False)

DB_AUTH = os.getenv('DB_AUTH', 'admin')
DB_PASS = os.getenv('DB_PASS', 'password')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '3306')
DATABASE = os.getenv('DATABASE', 'ps_utils')
# The SQLAlchemy connection string.
# SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "app.db")
SQLALCHEMY_DATABASE_URI = 'mysql://{}:{}@{}:{}/{}'.format(DB_AUTH, DB_PASS, DB_HOST, DB_PORT, DATABASE)
# SQLALCHEMY_DATABASE_URI = 'postgresql://root:password@localhost/myapp'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# used for transfering password from previous db.
# Change driver and connection string as needed in view.py updatePasswords
# pass these through the environment variables or set default
OLD_DB_AUTH = os.getenv('OLD_DB_AUTH', 'admin')
OLD_DB_PASS = os.getenv('OLD_DB_PASS', 'password')
OLD_DB_HOST = os.getenv('OLD_DB_HOST', '127.0.0.1')
OLD_DB_PORT = os.getenv('OLD_DB_PORT', '3306')
OLD_DATABASE = os.getenv('OLD_DATABASE', 'invreq')
ERP_ID = os.getenv('ERP_ID', 'entity')  # field name
PS_USER = os.getenv('PS_USER', 'userName')  # field name
PS_PSSWD = os.getenv('PS_PSSWD', 'password')  # field name
PS_CODE = os.getenv('PS_CODE', 'companyID')  # field name
PS_TABLE = os.getenv('PS_TABLE', 'companies')  # table name

# Flask-WTF flag for CSRF
CSRF_ENABLED = True

# ------------------------------
# GLOBALS FOR APP Builder
# ------------------------------
# Uncomment to setup Your App name
# APP_NAME = "My App Name"

# Uncomment to setup Setup an App icon
# APP_ICON = "static/img/logo.jpg"

# ----------------------------------------------------
# AUTHENTICATION CONFIG
# ----------------------------------------------------

# use on production once db created to prevent race condition of creating permissions
# on gunicorn multiple works.  You will need to run '- FLASK_ENV=development' in the docker-compose.yml
# once to create the permissions on the database, after which you can run gunicorn
update_permissions = os.getenv('FAB_UPDATE_PERMS', True)
if update_permissions == 'False':
    FAB_UPDATE_PERMS = False

# The authentication type
# AUTH_OID : Is for OpenID
# AUTH_DB : Is for database (username/password()
# AUTH_LDAP : Is for LDAP
# AUTH_REMOTE_USER : Is for using REMOTE_USER from web server
AUTH_TYPE = AUTH_DB

# Uncomment to setup Full admin role name
AUTH_ROLE_ADMIN = 'Admin'

# Uncomment to setup Public role name, no authentication needed
AUTH_ROLE_PUBLIC = 'Public'

# Config for Flask-WTF Recaptcha necessary for user registration
RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY', 'GOOGLE PUBLIC KEY FOR RECAPTCHA')
RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY', 'GOOGLE PRIVATE KEY FOR RECAPTCHA')
# Config for Flask-Mail necessary for user registration
# and smtp settings for sendMail() in utilities.py
MAIL_SERVER = SMTP_SERVER = os.getenv('SMTP_SERVER', '')
MAIL_USE_TLS = True
SMTP_TLS_OR_SSL = int(os.getenv('SMTP_TLS_OR_SSL', 0)) # tls=0 ssl=1
MAIL_PORT = SMTP_PORT = os.getenv('SMTP_PORT', '587')
SMTP_AUTH_REQUIRED = int(os.getenv('SMTP_AUTH_REQUIRED', '0'))
MAIL_USERNAME = SMTP_FROM = os.getenv('SMTP_FROM', '')
MAIL_PASSWORD = SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
MAIL_DEFAULT_SENDER = SMTP_FROM = os.getenv('SMTP_FROM', '')
SMTP_FQDN = os.getenv('SMTP_FQDN', '')
SMTP_DEV_TO = os.getenv('SMTP_DEV_TO', '')  # used in development to send emails to

# comment out to prevent Forms menu and endpoint access from being public or if making any changes in the DB after startup
# ***commented out as it was not working as expected
# FAB_ROLES = {
#     "Public": [
#         ["Inventory.*", "can_get"],
#         ["Inventory.*", "can_post"],
#         ["INV Request", "menu_access"],
#         ["OrderStatus.*", "can_get"],
#         ["OrderStatus.*", "can_post"],
#         ["OrderStatus.*", "menu_access"],
#         ["ShippingStatus.*", "can_get"],
#         ["ShippingStatus.*", "can_post"],
#         ["Shipment Status Request", "menu_access"],
#         ["JsonPO.*", "can_get"],
#         ["JsonPO.*", "can_post"]
#     ]
# }

# Will allow user self registration
AUTH_USER_REGISTRATION = True

# The default user self registration role
# AUTH_USER_REGISTRATION_ROLE = "Public"

# When using LDAP Auth, setup the ldap server
# AUTH_LDAP_SERVER = "ldap://ldapserver.new"

# Uncomment to setup OpenID providers example for OpenID authentication
# OPENID_PROVIDERS = [
#    { 'name': 'Yahoo', 'url': 'https://me.yahoo.com' },
#    { 'name': 'AOL', 'url': 'http://openid.aol.com/<username>' },
#    { 'name': 'Flickr', 'url': 'http://www.flickr.com/<username>' },
#    { 'name': 'MyOpenID', 'url': 'https://www.myopenid.com' }]
# ---------------------------------------------------
# Babel config for translations
# ---------------------------------------------------
# Setup default language
BABEL_DEFAULT_LOCALE = "en"
# Your application default translation path
BABEL_DEFAULT_FOLDER = "translations"
# The allowed translation for you app
LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
    "pt": {"flag": "pt", "name": "Portuguese"},
    "pt_BR": {"flag": "br", "name": "Pt Brazil"},
    "es": {"flag": "es", "name": "Spanish"},
    "de": {"flag": "de", "name": "German"},
    "zh": {"flag": "cn", "name": "Chinese"},
    "ru": {"flag": "ru", "name": "Russian"},
    "pl": {"flag": "pl", "name": "Polish"},
}
# ---------------------------------------------------
# Image and file configuration
# ---------------------------------------------------
# The file upload folder, when using models with files
UPLOAD_FOLDER = basedir + "/app/static/uploads/"

# The image upload folder, when using models with images
IMG_UPLOAD_FOLDER = basedir + "/app/static/uploads/"

# The image upload url, when using models with images
IMG_UPLOAD_URL = "/static/uploads/"
# Setup image size default is (300, 200, True)
# IMG_SIZE = (300, 200, True)

# Theme configuration
# these are located on static/appbuilder/css/themes
# you can create your own and easily use them placing them on the same dir structure to override
# APP_THEME = "bootstrap-theme.css"  # default bootstrap
APP_THEME = "cerulean.css"
# APP_THEME = "amelia.css"
# APP_THEME = "cosmo.css"
# APP_THEME = "cyborg.css"
# APP_THEME = "flatly.css"
# APP_THEME = "journal.css"
# APP_THEME = "readable.css"
# APP_THEME = "simplex.css"
# APP_THEME = "slate.css"
# APP_THEME = "spacelab.css"
# APP_THEME = "united.css"
# APP_THEME = "yeti.css"
