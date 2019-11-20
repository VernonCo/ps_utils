import logging, os

from flask import Flask
from flask_appbuilder import SQLA, AppBuilder
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import DDL, inspect
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
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLA(app)
from . import models
db.create_all()
# changed some mispelled columns and added 2.  Check to verify changes passed through before using updated code
inspector = inspect(db.engine)
check = str(inspector.get_columns('company'))
found = False
if 'produc_url' in check:
    try:
        sql = DDL("ALTER TABLE company CHANGE produc_url product_url VARCHAR(255)")
        db.engine.execute(sql)
        sql = DDL("ALTER TABLE company CHANGE produc_vVersion product_version VARCHAR(255)")
        db.engine.execute(sql)
    except:
        logging.error('Database not updated. See app.__init__')
        exit(1)
if 'product_urlV2' not in check:
    try:
        sql = DDL('ALTER TABLE company ADD COLUMN product_urlV2 VARCHAR(255) AFTER product_url')
        db.engine.execute(sql)
        sql = DDL('ALTER TABLE company ADD COLUMN product_versionV2 VARCHAR(255) AFTER product_version')
        db.engine.execute(sql)
    except:
        logging.error('Database not updated. See app.__init__')
        exit(1)

appbuilder = AppBuilder(app, db.session)
csrf = CSRFProtect(app)

# set up the default company and part for selection in the form
default_co = 1
co = os.getenv("DEFAULT_CO", "Starline")
check = db.session.query(models.Company).filter(models.Company.company_name==co).first()
if check:
    default_co = check.id
default_part = os.getenv("DEFAULT_PART", "BG344")

from . import views

@app.teardown_appcontext
def shutdown_session(exception=None):
    """prevents sqlalchemy pool exceeding 10 by leaving connections hanging"""
    db.session.remove()
