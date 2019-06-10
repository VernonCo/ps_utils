import json, logging
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from flask import request, flash
from suds.client import Client
from .models import Company
from . import appbuilder, db
from .forms import OrderStatusForm
from .soap_utils import sobject_to_dict, sobject_to_json, basic_sobject_to_dict, getDoctor
from . import app
from jinja2 import Markup
from sqlalchemy import or_, and_

PRODUCTION = app.config.get('PRODUCTION')

class OrderStatus(SimpleFormView):
    """
        get order status from submitted form or external post
            or external ajax request using content-type application/x-www-form-urlencoded

        params:
        companyID = PS companyID
        queryType = query search type: 1=PO#,2=SO#,3=from date,4=all open orders
        returnType = return type json or html
        [options depend on queryType]
        refNum for PO or SO#
        refDate for from Date

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
    """
    default_view = 'index'
    form = OrderStatusForm

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        companies = self.orderCompanies()
        form_title = 'Order Status Request Form'
        if request.method == 'GET':
            # TODO: add and_ to check for username and password
            id = request.values.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies=companies, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted", data=False
                    )
        # else deal with post
        c = db.session.query(Company).get(int(request.form['companyID']))
        data = self.orderCall(c, 'getOrderStatusDetails')

        # else if requesting json
        if  request.form['returnType'] == 'json':
            data = sobject_to_json(data)
            return data, 200,  {'Content-Type':'applicaion/json'}
        # if error return to request form
        if data == 'Unable to get Response' \
            or 'SoapFault' in data \
            or 'errorMessage' in data and data['errorMessage']:

            # setup flash message for error
            if 'SoapFault' in data:
                # safe html from exceptions
                flash(Markup('{}'.format(data['SoapFault'])), 'error')
            elif 'errorMessage' in data and data['errorMessage']:
                # unsafe html...errorMessage from suppliers
                flash('Error Message: {} from {}'.format(data['errorMessage'],c), 'error')
            else:
                flash('Error: {}'.format(data), 'error')

            id = request.values.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies=companies, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted"
                    )

        # else redirct to results page
        result = sobject_to_dict(data, json_serialize=True)
        result['vendorID'] = c.id
        result['vendorName'] = c.company_name
        result['returnType'] = request.form['returnType']
        result['refNum'] = request.form['refNum']
        result['refDate'] = request.form['refDate']
        if 'SoapFault' in result:
            result['errorMessage'] = result['SoapFault']
        if 'errorMessage' in result and result['errorMessage']:
            checkRow = None
        else:
            try:
                checkRow = result['OrderStatusArray']['OrderStatus'][0]
            except:
                checkRow = None
                result['errorMessage'] = "Response structure error"
                if not PRODUCTION:
                    result['errorMessage'] += ": " +str(sobject_to_dict(data, json_serialize=True))
        table = True if request.form['returnType'] == 'table' else False

        return self.render_template(
            'order/results.html', data=result, checkRow=checkRow, c=c,
            companies=companies, table=table
            )

    def orderCall(self,c, serviceType):
        """ call the order status service """
        data = 'Unable to get Response'
        # get the local wsdl and inject the endpoint
        # ...should almost always work if they follow the wsdl and give a valid endpoint to PS
        local_wsdl = getDoctor('ODRSTAT', c.order_version, url=True)
        # set schema doctor to fix missing schemas
        d = getDoctor('ODRSTAT', c.order_version)
        kw = dict(
                password=c.password,
                id=c.user_name,
                queryType=request.form['queryType'],
                wsVersion= c.order_version)
        if 'refDate' in request.form and request.form['refDate']:
            kw['statusTimeStamp']=request.form['refDate']
        if 'refNum' in request.form and request.form['refNum']:
            kw['referenceNumber']=request.form['refNum']
        try:
            client = Client(local_wsdl, location=c.order_url, doctor=d)
            # call the method
            func = getattr(client.service, serviceType)
            data = func(**kw)
        except Exception as e:
            logging.error('WSDL Error on local wsdl and location {}: {}'.format(c.order_url,str(e)))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault': 'Error(1): ' +str(e)}
            try:
                # use remote wsdl
                client = Client(c.order_wsdl, doctor=d)
                func = getattr(client.service, serviceType)
                data = func(**kw)
            except Exception as e:
                msg = 'Soap Fault Error(2) on remote wsdl location {}: {}'.format(c.order_wsdl,str(e))
                if not PRODUCTION:
                    error_msg['SoapFault'] += '<br>' + msg
                logging.error(msg)
                try:
                    # use remote wsdl but set location to endpoint
                    client = Client(c.order_wsdl, location='{}'.format(c.order_url), doctor=d)
                    func = getattr(client.service, serviceType)
                    data = func(**kw)
                except Exception as e:
                    msg = 'Soap Fault Error(3) on remote wsdl and location {}: {}'.format(c.order_url,str(e))
                    if not PRODUCTION:
                        error_msg['SoapFault'] += '<br>' + msg
                    logging.error(str(e))
                    data = error_msg

        return data

    def orderCompanies(self):
        """ return available inventory companies"""
        return db.session.query(Company).filter(
                and_(Company.order_url != None, Company.user_name != None)
            ).all()
