import copy,json, logging

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_

from . import PRODUCTION, db, default_co, default_part
from .models import Company
from .soap_utils import SoapClient
from .table_utils import Table


def invoice_companies():
    """ return available invoice companies"""
    return db.session.query(Company).filter(
            and_(Company.invoice_url != None, Company.user_name != None)
        ).all()


class Invoice(SimpleFormView):
    default_view = 'index'

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for invoice data requests

        params:
            companyID = int

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """
        form_title = "Product Info Request Form"
        cid = request.values.get('companyID', default_co)
        if request.method == 'GET':
            return self.render_template(
                    'underconstruction.html',
                    companies = invoice_companies(),
                    cid = int(cid),
                    form_title = form_title,
                    form = self.form,
                    message = "Form was submitted",
                    service_path='invoice',
                    data = False)
