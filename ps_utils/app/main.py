import logging

from flask import Flask
from flask_appbuilder import AppBuilder, SQLA
from flask_wtf.csrf import CSRFProtect


SQLALCHEMY_TRACK_MODIFICATIONS = False

app = Flask(__name__)
app.config.from_object("config")
PRODUCTION = app.config.get('PRODUCTION')

# Logging configuration
logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
if not PRODUCTION:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.ERROR)

db = SQLA(app)
appbuilder = AppBuilder(app, db.session)
csrf = CSRFProtect(app)


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


from . import views
