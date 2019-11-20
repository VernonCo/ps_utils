from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_

from . import PRODUCTION, db, default_co
from .models import Company
from .soap_utils import SoapClient


class OrderStatus(SimpleFormView):
    """
        get order status from submitted form or external post
            or external ajax request using content-type application/x-www-form-urlencoded

        params:
            companyID = PS companyID
            queryType = query search type: 1 = PO#, 2 = SO#, 3 = from date, 4 = all open orders
            return_type = return type json or html
            [options depend on queryType]
                refNum for PO or SO#
                refDate for from Date

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
    """
    default_view = 'index'
    companies = db.session.query(Company).filter(
        and_(Company.order_url != None, Company.user_name != None)).order_by(Company.company_name).all()

    def get_order_status(self, c, **kw):
        return_type = kw.pop('return_type') if 'return_type' in kw else request.form['return_type']
        form_title = 'Order Status Request Form'
        error_flag = False
        html_code = 200
        client = SoapClient(service_method = 'getOrderStatusDetails',
                            service_url = c.order_url,
                            service_WSDL = c.order_wsdl,
                            service_code = 'ODRSTAT',
                            service_version = c.order_version,
                            filters = False,
                            values = False,
                            **kw)
        data = client.service_call()

        # if error return to request form
        if not data:
            #can return empty envelope with no errorMessage on this service
            flash('Error: Empty response', 'error')
            error_flag = True
        if data == 'Unable to get Response':
            flash('Error: {}'.format(data), 'error')
            error_flag = True
            html_code = 500
        elif 'SoapFault' in data:
            # safe html from exceptions
            flash(Markup('{}'.format(data['SoapFault'])), 'error')
            error_flag = True
            html_code = 500
        elif 'errorMessage' in data and data.errorMessage:
            # unsafe html...errorMessage from suppliers
            flash('Error Message: {} from {}'.format(data.errorMessage, c),
                  'error')
            error_flag = True

        # if requesting json
        if return_type == 'json':
            data = client.sobject_to_json()
            return data, html_code, {'Content-Type': 'applicaion/json'}

        # finally check if a status returned if checking for specific order.
        #    This service does not provide handling for order not found like code: 301 in OSN service
        result = client.sobject_to_dict(json_serialize = True)
        if  'errorMessage' not in result:
            try:
                status = result['OrderStatusArray']['OrderStatus'][0]\
                    ['OrderStatusDetailArray']['OrderStatusDetail'][0]['statusID']
                if not status.strip():
                    flash(
                        'Error Message: Order not found for Reference Number',
                        'error')
                    error_flag = True
            except:
                flash('Error Message: Order not found for Reference Number',
                      'error')
                result['errorMessage'] = 'Order not found for Reference Number'
                error_flag = True
        if return_type == 'internal':
            if not error_flag:
                return result['OrderStatusArray']['OrderStatus'][0]\
                    ['OrderStatusDetailArray']['OrderStatusDetail'][0]
            else:
                return result
        if error_flag:
            return self.render_template('order/requestForm.html',
                                        companies = self.companies,
                                        cid = c.id,
                                        form_title = form_title,
                                        form = self.form,
                                        message = "Form was submitted",
                                        service_path='order')
        # else redirct to results page
        result['vendorID'] = c.id
        result['vendorName'] = c.company_name
        result['return_type'] = return_type
        result['refNum'] = kw['refNum'] if 'refNum' in kw and  kw['refNum'] else ''
        result['refDate'] = kw['refDate'] if 'refDate' in kw and  kw['refDate'] else ''
        if 'SoapFault' in result:
            result['errorMessage'] = result['SoapFault']
        if 'errorMessage' in result and result['errorMessage']:
            check_row = None
        else:
            try:
                check_row = result['OrderStatusArray']['OrderStatus'][0]
            except Exception as e:
                check_row = None
                result['errorMessage'] = str(e)
                if not PRODUCTION:
                    # assert False
                    result['errorMessage'] += ": " + str(
                        client.sobject_to_dict(json_serialize = True))

        table = True if return_type == 'table' else False

        return self.render_template('order/results.html',
                                    data = result,
                                    check_row = check_row,
                                    cid = c.id,
                                    form_title = form_title,
                                    companies = self.companies,
                                    service_path='order',
                                    table = table)

    @expose('/index/', methods = ['GET', 'POST'])
    def index(self, **kw):
        if request.method == 'GET':
            form_title = 'Order Status Request Form'
            cid = request.values.get('companyID', default_co)
            return self.render_template('order/requestForm.html',
                                        companies = self.companies,
                                        cid = int(cid),
                                        form_title = form_title,
                                        form = self.form,
                                        message = "Form was submitted",
                                        service_path='order',
                                        data = False)
        # else deal with post
        c = db.session.query(Company).get(int(request.form['companyID']))
        kw = dict(wsVersion = c.order_version,
                  password = c.password,
                  id = c.user_name,
                  queryType = request.form['queryType'])
        values = {
            'namespaces': {
                'ns':
                "http://www.promostandards.org/WSDL/OrderStatusService/1.0.0/"
            },
            'method': {
                'ns': 'GetOrderStatusDetailsRequest'
            },
            'fields': [('ns', 'wsVersion', kw['wsVersion']),
                       ('ns', 'id', kw['id']),
                       ('ns', 'password', kw['password']),
                       ('ns', 'queryType', kw['queryType'])],
            'Filter':False
        }
        if 'refDate' in request.form and request.form['refDate']:
            kw['statusTimeStamp'] = request.form['refDate']
            values['fields'].append(
                ('ns', 'statusTimeStamp', request.form['refDate']))
        if 'refNum' in request.form and request.form['refNum']:
            kw['referenceNumber'] = request.form['refNum']
            values['fields'].append(
                ('ns', 'referenceNumber', request.form['refNum']))
        # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
        #     from .soap_utils import test_call
        #     test_call(service_url = c.order_url, service_method = 'getOrderStatusDetails',
        #                         serviceResponse = 'GetOrderStatusDetailsResponse', values = values)

        # new fix in suds/xsd/sxbase.py takes care of the wsdl parsing issue and values only needed if using test_call above
        # However, leaving following line commented until fix is pushed to pypi
        # values = False
        return self.get_order_status(c, **kw)

    @expose('/instructions/', methods = ['GET'])
    def instructions(self):
        """ diplay instructions for sending form_encoded POST to forms"""
        return self.render_template('order/instructions.html')
