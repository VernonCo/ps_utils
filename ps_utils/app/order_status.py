from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_

from . import PRODUCTION, db
from .models import Company
from .soap_utils import SoapClient


def orderCompanies():
    """ return available inventory companies"""
    return db.session.query(Company).filter(
            and_(Company.order_url != None, Company.user_name != None)
        ).all()


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

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        companies = orderCompanies()
        form_title = 'Order Status Request Form'
        if request.method == 'GET':
            cid = request.values.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies=companies, id=int(cid),
                    form_title=form_title, form=self.form, message = "Form was submitted", data=False
                    )
        # else deal with post
        errorFlag = False
        htmlCode = 200
        c = db.session.query(Company).get(int(request.form['companyID']))
        kw = dict(
                wsVersion=c.order_version,
                password=c.password,
                id=c.user_name,
                queryType=request.form['queryType'])
        values = {
            'namespaces': {'ns':"http://www.promostandards.org/WSDL/OrderStatusService/1.0.0/"},
            'method': {'ns':'GetOrderStatusDetailsRequest'},
            'fields': [('ns','wsVersion', kw['wsVersion']),('ns','id', kw['id']),('ns','password', kw['password']),
                ('ns','queryType', kw['queryType'])
            ],
        'Filter': False
        }
        if 'refDate' in request.form and request.form['refDate']:
            kw['statusTimeStamp']=request.form['refDate']
            values['fields'].append(('ns','statusTimeStamp',request.form['refDate']))
        if 'refNum' in request.form and request.form['refNum']:
            kw['referenceNumber']=request.form['refNum']
            values['fields'].append(('ns','referenceNumber',request.form['refNum']))
        # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
        #     from .soap_utils import testCall
        #     testCall(serviceUrl=c.order_url, serviceMethod='getOrderStatusDetails',
        #                         serviceResponse='GetOrderStatusDetailsResponse', values=values)

        # new fix in suds/xsd/sxbase.py takes care of the wsdl parsing issue and values only needed if using testCall above
        # However, leaving following line commented until fix is pushed to pypi
        # values = False
        client = SoapClient(serviceMethod='getOrderStatusDetails', serviceUrl=c.order_url, serviceWSDL=c.order_wsdl, serviceCode='ORDSTAT',
                serviceVersion=c.order_version, filters=False, values=False, **kw)
        data = client.serviceCall()

        # if error return to request form
        if not data:
            #can return empty envelope with no errorMessage on this service
            flash('Error: Empty response', 'error')
            errorFlag = True
        if data == 'Unable to get Response':
            flash('Error: {}'.format(data), 'error')
            errorFlag = True
            htmlCode = 500
        elif 'SoapFault' in data:
            # safe html from exceptions
            flash(Markup('{}'.format(data['SoapFault'])), 'error')
            errorFlag = True
            htmlCode = 500
        elif 'errorMessage' in data and data.errorMessage:
            # unsafe html...errorMessage from suppliers
            flash('Error Message: {} from {}'.format(data.errorMessage, c), 'error')
            errorFlag = True

        # if requesting json
        if  request.form['returnType'] == 'json':
            data = client.sobject_to_json()
            return data, htmlCode,  {'Content-Type':'applicaion/json'}

        # finally check if a status returned if checking for specific order.
        #    This service does not provide handling for order not found like code: 301 in OSN service
        result = client.sobject_to_dict(json_serialize=True)
        if request.form['refNum'] and 'errorMessage' not in result:
            try:
                status = result['OrderStatusArray']['OrderStatus'][0]['OrderStatusDetailArray']['OrderStatusDetail'][0]['statusID']
                if not status.strip():
                    flash('Error Message: Order not found for Reference Number', 'error')
                    errorFlag = True
            except:
                flash('Error Message: Order not found for Reference Number', 'error')
                result['errorMessage'] = 'Order not found for Reference Number'
                errorFlag = True

        if errorFlag:
            cid = request.values.get('companyID', 126)
            return self.render_template( 'order/requestForm.html', companies=companies, id=int(cid),
                    form_title=form_title, form=self.form, message = "Form was submitted"
                    )

        # else redirct to results page
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
            except Exception as e:
                checkRow = None
                result['errorMessage'] = str(e)
                if not PRODUCTION:
                    # assert False
                    result['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))

        table = True if request.form['returnType'] == 'table' else False

        return self.render_template(
            'order/results.html', data=result, checkRow=checkRow, c=c,
            form_title=form_title, companies=companies, table=table
            )

    @expose('/instructions/', methods=['GET'])
    def instructions(self):
        """ diplay instructions for sending form_encoded POST to forms"""
        return self.render_template( 'order/instructions.html')
