#!/bin/python3
import logging
from flask import render_template
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _

from . import app, appbuilder, db, PRODUCTION
from .inventory import Inventory
from .models import Company
from .order_status import OrderStatus
from .ppc import PPC
from .purchase_order import JsonPO
from .shipping_status import ShippingStatus
from .utilities import Utilities


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
except Exception as e:
    print(e)
    # pass fails if db connection is not set to bring in passwords from existing db


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
    PPC,
    "Product, Pricing, & Config",
    href='/ppc/index/',
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
    "POST to forms",
    href='/orderstatus/instructions/',
    icon="fa-info",
    category='Info',
    category_icon='fa-info-circle'
)

appbuilder.add_view(
    JsonPO,
    "POST a PO",
    href='/jsonpo/instructions/',
    icon="fa-info",
    category='Info',
    category_icon='fa-info-circle'
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
appbuilder.security_cleanup()
db.create_all()
