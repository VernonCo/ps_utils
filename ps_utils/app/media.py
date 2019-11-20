import copy,json, logging

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_

from . import PRODUCTION, db, default_co, default_part
from .models import Company
from .soap_utils import SoapClient
from .table_utils import Table


def media_companies():
    """ return available media companies"""
    return db.session.query(Company).filter(
            and_(Company.media_url != None, Company.user_name != None)
        ).all()


class Media(SimpleFormView):
    default_view = 'index'

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for media data requests

        params:
            companyID = int
            productID = 'SKU'

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """
        form_title = "Product Info Request Form"
        cid = request.values.get('companyID', default_co)
        prodID = request.values.get('productID', default_part)
        if request.method == 'GET':
            return self.render_template(
                    'underconstruction.html', companies=media_companies(), form_title=form_title, cid=int(cid),
                    prodID=prodID, form=self.form, message = "Form to submit for Media", data=False,
                    service_path='media'
                    )
