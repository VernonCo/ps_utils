import logging, os

from flask import Flask
from flask_appbuilder import SQLA, AppBuilder
from flask_wtf.csrf import CSRFProtect

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
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

"""
from sqlalchemy.engine import Engine
from sqlalchemy import event

#Only include this for SQLLite constraints
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Will force sqllite contraint foreign keys
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
"""
