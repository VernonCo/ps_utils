
import  json, os, logging
from suds.client import Client
# logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
# logging.getLogger('suds.client').setLevel(logging.DEBUG)
from flask import render_template, flash, request, jsonify, config
from flask_babel import lazy_gettext as _
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView, ModelRestApi
from .models import Company
from .utilities import Utilities
from .inventory import Inventory
from .order_status import OrderStatus
from .shipping_status import ShippingStatus
from .purchase_order import JsonPO
# from .purchasOrder import PurchaseOrder
from .soap_utils import  SoapClient, tryUrl
from . import appbuilder, db
from . import app

PRODUCTION = app.config.get('PRODUCTION')

"""
    Create your Model based REST API::

        class MyModelApi(ModelRestApi):
            datamodel = SQLAInterface(MyModel)

        appbuilder.add_api(MyModelApi)


    Create your Views::

        class MyModelView(ModelView):
            datamodel = SQLAInterface(MyModel)

        Next, register your Views::

        appbuilder.add_view(
            MyModelView,
            "My View",
            icon="fa-folder-open-o",
            category="My Category",
            category_icon='fa-envelope'
        )
"""

class Companies(ModelView):
    datamodel = SQLAInterface(Company)
    list_columns = ['company_name', 'erp_id']

appbuilder.add_view( Companies, "List Companies", icon="fa-list", category="Companies", category_icon='fa-database')

appbuilder.add_view( Utilities, "Update Company Urls", icon="fa-link",href='/utilities/updateCompanies/', category='Utilities',category_icon="fa-cubes")
try:
    if app.config['PS_USER']:
        logging.info('PS_USER: {}'.format(app.config['PS_USER']))
        appbuilder.add_link("Update Passwords", icon='fa-exclamation-triangle', href='/utilities/updatePasswords/', category='Utilities')
except:
    pass  #fails if db connection is not set to bring in passwords from existing db


appbuilder.add_view(
    Inventory,
    "INV Request",
    href='/inventory/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
) #  label=_("Inventory Request Form"),

appbuilder.add_view(
    OrderStatus,
    "Order Status Request",
    href='/orderstatus/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
)

appbuilder.add_view(
    ShippingStatus,
    "Shipment Status Request",
    href='/shippingstatus/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
)

appbuilder.add_view(
    JsonPO,
    "Send PO Post URL",
    href='/jsonPO/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
)

@appbuilder.app.errorhandler(404)
def page_not_found(e):
    """
        Application wide 404 error handler
    """
    return (
        render_template(
            "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
        ),
        404,
    )

db.create_all()
