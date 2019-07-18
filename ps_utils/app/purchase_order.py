import json, logging
import copy
from flask_appbuilder import SimpleFormView, expose, has_access
from flask import request, flash, redirect
from .models import Company
from . import app, appbuilder, db, csrf
from .soap_utils import SoapClient
from jinja2 import Markup
from sqlalchemy import or_, and_

PRODUCTION = app.config.get('PRODUCTION')
htmlCode = 200

class JsonPO(SimpleFormView):
    """
        Receives a json post with the PO info.
        Requires companyID to get url, username, password, and version
        {companyId: int, PO:{...}}
        Other requirements: check https://promostandards.org/service/view/15/
        Returns a status and json response after validating and submitting a sendPO.
    """
    default_view = 'index'

    # Make sure this is only accessible by apps you want as it is open
    # or add authentication protection
    # send POST header 'Content-Type: applicaion/json'
    @expose('/index/', methods=['POST'])
    @csrf.exempt
    def index(self, **kw):
        """process json request received"""
        req_json = request.get_json()
        companyID = req_json.pop('companyID', None)
        if not companyID or not isinstance(companyID, int):
            error = dict(ServiceMessageArray=[dict(Code=120, Description="The following field(s) are required: companyID")])
            data = json.dumps(error)
            return data, 500,  {'Content-Type':'applicaion/json'}
        c = db.session.query(Company).get(companyID)
        if not c:
            error = dict(ServiceMessageArray=[dict(Code=100, Description="ID (companyID) not found")])
            data = json.dumps(error)
            return data, 500,  {'Content-Type':'applicaion/json'}
        kw = {"wsVersion": c.po_version, "id": c.user_name, "password": c.password, "PO": req_json['PO']}
        data = self.sendPO(c, **kw)
        return data, htmlCode,  {'Content-Type':'applicaion/json'}

    @expose('/instructions/', methods=['GET'])
    def instructions(self):
        """ diplay instructions for sending jsonPO"""
        return self.render_template( 'purchaseOrder/instructions.html')

    def sendPO(self, company, **kw):
        """send the request.  Can be used by index or a plugin"""
        client = SoapClient(serviceMethod='sendPO', serviceUrl=company.po_url, serviceWSDL=company.po_wsdl, serviceCode='PO',
                serviceVersion=company.po_version, filters=False, values=False, **kw)
        client.serviceCall()
        if client.data == 'Unable to get Response' or 'SoapFault' in client.data:
            htmlCode = 500
        return client.sobject_to_json()

    def validatePO(self):
        """ validate required fields are present and validate types"""
