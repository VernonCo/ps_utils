import json, logging
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from flask import request, flash
from suds.client import Client
from .models import Company
from . import appbuilder, db
from .forms import OrderStatusForm
from .soap_utils import sobject_to_dict, sobject_to_json, basic_sobject_to_dict, getDoctor
from . import app

PRODUCTION = app.config.get('PRODUCTION')

class OrderStatus(SimpleFormView):
    default_view = 'index'
    form = OrderStatusForm

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        if request.method == 'GET':
            form_title = 'Order Status Request Form'
            c = db.session.query(Company).filter(Company.order_version != None).all()
            id = request.args.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies = c, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted", data=False
                    )
        # else deal with post
        c = db.session.query(Company).get(int(request.form['companyID']))
        if c.order_version[:1] != '1':
            contentType = {'Content-Type':'text/html'}
            if  request.form['returnType'] == 'json':
                contentType = {'Content-Type':'applicaion/json'}
            return 'Version > 1 is unavailable', 500,  contentType
        data = self.orderCall(c, 'getOrderStatusDetails')
        if data == 'Unable to get Response':
            if  request.form['returnType'] == 'json':
                data = json.dumps(data)
                return data, 200,  {'Content-Type':'applicaion/json'}
            flash('{} from {}'.format(data,c), 'error')
            id = request.args.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies = c, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted"
                    )
        # else if requesting json
        if  request.form['returnType'] == 'json':
            data = sobject_to_json(data)
            return data, 200,  {'Content-Type':'applicaion/json'}
        # else redirct to results page
        data=sobject_to_dict(data, json_serialize=True)
        data['vendorID'] = c.id
        data['vendorName'] = c.company_name
        data['returnType'] = request.form['returnType']
        data['refNum'] = request.form['refNum']
        data['refDate'] = request.form['refDate']
        assert False
        if 'SoapFault' in data:
            data['errorMessage'] = data['SoapFault']
        if 'errorMessage' in data and data['errorMessage']:
            checkRow = None
        else:
            checkRow = data['OrderStatusArray']['OrderStatus'][0]
        table = False
        template = 'order/results.html'
        companies=db.session.query(Company).all(),
        if request.form['returnType'] == 'table': # return html for table only
            table=True
            template = 'order/resultsTable.html'
        return self.render_template(
            template, data=data, checkRow=checkRow,
            companies=companies, table=table
            )


    def orderCall(self,c, serviceType):
        """ call the order status service """
        data = 'Unable to get Response'
        # get the local wsdl and inject the endpoint
        # ...should almost always work if they follow the wsdl and give a valid endpoint to PS
        local_wsdl = getDoctor('ODRSTAT', c.order_version, url=True)
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
            client = Client(local_wsdl, location='{}'.format(c.order_url))
            # call the method
            func = getattr(client.service, serviceType)
            data = func(**kw)
        except Exception as e:
            if not PRODUCTION:
                logging.error('Error on local wsdl and location: {}'.format(c.order_url))
            logging.error(str(e))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault':str(e)}
            try:
                # use remote wsdl
                # set schema doctor to fix missing schemas
                d = getDoctor('ODRSTAT', c.order_version)
                client = Client(c.inventory_wsdl, doctor=d)
                func = getattr(client.service, serviceType)
                data = func(**kw)
            except Exception as e:
                if not PRODUCTION:
                    logging.error('Error on remote wsdl ')
                logging.error(str(e))
                try:
                    # use remote wsdl but set location to endpoint
                    # doctor to fix missing schemas
                    d = getDoctor('ODRSTAT', c.order_version)
                    client = Client(c.inventory_wsdl, location='{}'.format(c.order_url), doctor=d)
                    func = getattr(client.service, serviceType)
                    data = func(**kw)
                except Exception as e:
                    if not PRODUCTION:
                        logging.error('Error on remote wsdl and location: {}'.format(c.order_version))
                    logging.error(str(e))
                    data = error_msg
        return data

    def orderCallv2(self,c):
        """ used with version 2.0.0 """
        # TODO: finish code for version 2.0.0
        return {"SoapFault": 'Version 2.0.0 is not available yet.'}
