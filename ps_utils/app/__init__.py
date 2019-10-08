import logging, os

from flask import Flask
from flask_appbuilder import SQLA, AppBuilder
from flask_wtf.csrf import CSRFProtect
from werkzeug.contrib.fixers import ProxyFix

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.config.from_object(os.getenv("CONFIG_FILE"))

PRODUCTION = app.config.get('PRODUCTION')

# Logging configuration
logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
if not PRODUCTION:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.ERROR)
AppBuilder.app_name = 'PS Utils'
db = SQLA(app)
appbuilder = AppBuilder(app, db.session)
csrf = CSRFProtect(app)

@app.teardown_appcontext
def shutdown_session(exception=None):
    """prevents sqlalchemy pool exceeding 10 by leaving connections hanging"""
    db.session.remove()


from . import views
