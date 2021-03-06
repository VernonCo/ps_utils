import json

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_

from . import app, db, default_co, PRODUCTION
from .models import Company
from .soap_utils import SoapClient
from .tracking_util import Tracking_No


def create_table_set(result):
    """ creates a table set from result for datatable to display with nested package child row """
    data = []
    for order in result['OrderShipmentNotificationArray']['OrderShipmentNotification']:
        temp = {}
        temp['PO'] = order['purchaseOrderNumber']
        temp['complete'] = order['complete']
        temp['tracking'] = []
        temp['salesOrder'] = ''
        # create html table for salesOrder
        for row in order['SalesOrderArray']['SalesOrder']:
            temp['salesOrder'] += '<table class="table-bordered striped style="width: 100%"><thead><tr> \
                <th>Sales Order#</th><th>Complete?</th><th>Location Details</th></tr></thead><tbody><tr> \
                <td>{}</td><td>{}</td><td>'.format(row['salesOrderNumber'], row['complete'])
            temp['salesOrder'] += '<div id="accordion">'
            trackingCounter = 0
            if 'ShipmentLocation' in row['ShipmentLocationArray']:
                for location in row['ShipmentLocationArray']['ShipmentLocation']:
                    temp['salesOrder'] += '<h3>{}</h3><div><table class="table-bordered striped"><thead><tr> \
                        <th>Ship From</th><th>Ship To</th><th>Dest. Type</th> \
                        <th>Package Details</th></tr></thead><tbody><tr><td><table cellpadding="5" class="table-striped">'\
                        .format(location['ShipFromAddress']['address1'])
                    for k,v in location['ShipFromAddress'].items():
                        if v and v !='.':
                            temp['salesOrder'] += '<tr><td class="right bold">' + k + '</td><td class="left">' + str(v) + "</td></tr>"
                    temp['salesOrder'] += '</table></td><td><table class="table-striped">'
                    for k,v in location['ShipToAddress'].items():
                        if v and v !='.':
                            temp['salesOrder'] += '<tr><td class="right bold">' + k + '</td><td class="left">' + str(v) + "</td></tr>"
                    temp['salesOrder'] += '</table></td><td>'
                    shipmentDestinationType = location['shipmentDestinationType'] if 'shipmentDestinationType' in location else ''
                    temp['salesOrder'] += '{}</td><td><div class="tracking">'.format(shipmentDestinationType)
                    trackingCounter += 1
                    packageCounter = 0
                    if 'PackageArray' in location and 'Package' in location['PackageArray']:
                        for package in location['PackageArray']['Package']:
                            temp['salesOrder'] += '<h3>TRN: {}</h3><div><table class="table-striped">'.format(package['trackingNumber'])
                            for k,v in package.items():
                                if v and k != 'ItemArray':
                                    temp['salesOrder'] += '<tr><td class="right bold">' + k + '</td><td class="left">' + str(v) + "</td></tr>"
                            if 'ItemArray' in package and package['ItemArray']['Item']:
                                temp['salesOrder'] += '<tr><td colspan="2"><div class="packages">'
                                packageCounter += 1
                                itemCounter = 1  # used for heading only
                                for item in package['ItemArray']['Item']:
                                    temp['salesOrder'] += '<h3>Package #{}</h3><div><table class="table-striped" style="width:100%">'.format(itemCounter)
                                    itemCounter += 1
                                    for k,v in item.items():
                                        if v and v != '.':
                                            temp['salesOrder'] += '<tr><td class="right bold">' + k + '</td><td class="left">' + str(v) + "</td></tr>"
                                    temp['salesOrder'] += '</table></div>'
                            temp['salesOrder'] += '</div></td></tr></table></div>'
                            if package['trackingNumber']:
                                trkingNos = package['trackingNumber'].split(',')
                                carrier = ''
                                if 'carrier' in package:
                                    carrier = package['carrier']
                                for trackno in trkingNos:
                                    trackno = trackno.strip()
                                    trk = Tracking_No(trackno, carrier=carrier)
                                    # elliminates placebo
                                    if trk.valid():
                                        temp['tracking'].append(trk.link())
                temp['salesOrder'] += '</div></tr></tbody></table>'
        temp['packageCounter'] = packageCounter
        temp['trackingCounter'] = trackingCounter
        temp['tracking'] = ', '.join(temp['tracking'])
        data.append(temp)
    return json.dumps(data)


class ShippingStatus(SimpleFormView):
    """
        get order status from submitted form or external post
            or external ajax request using content-type application/x-www-form-urlencoded

        params:
            companyID = PS companyID
            queryType = query search type: 1=PO#,2=SO#,3=from date
            return_type = return type json or html
            [options depend on queryType]
                refNum for PO or SO#
                refDate for from Date

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
    """
    default_view = 'index'
    companies = db.session.query(Company).filter(
            and_(Company.shipping_url != None, Company.user_name != None)
        ).order_by(Company.company_name).all()

    def get_shipping_status(self, c, values, **kw):
        return_type = kw.pop('return_type') if 'return_type' in kw else request.form['return_type']
        form_title = 'Ship Status Request Form'
        error_flag = False
        html_code = 200
        errorMessage = ''
        client = SoapClient(service_method='getOrderShipmentNotification', service_url=c.shipping_url, service_WSDL=c.shipping_wsdl, service_code='OSN',
                service_version=c.shipping_version, filters=False, values=values, **kw)
        data = client.service_call()
        # if error return to request form
        if data == {} \
            or ('errorMessage' not in data and \
                ('OrderShipmentNotificationArray' not in data) \
            or ('OrderShipmentNotificationArray' in data \
                and not data['OrderShipmentNotificationArray'])):
            errorMessage = 'Error: empty response returned for request'
            flash(errorMessage, 'error')
            error_flag = True
        if data == 'Unable to get Response':
            errorMessage = 'Error: {}'.format(data)
            flash(errorMessage, 'error')
            error_flag = True
            html_code = 500
        elif 'SoapFault' in data:
            # safe html from exceptions
            errorMessage = Markup('{}'.format(data['SoapFault']))
            flash(errorMessage, 'error')
            error_flag = True
            html_code = 500
        elif 'errorMessage' in data and data.errorMessage.code > 9:
            # found some non-compliant vendors returning code=0 and description=SUCCESS
            flash('Error Message: {} from {}'.format(data.errorMessage.description, c), 'error')
            error_flag = True

        if error_flag and return_type == 'internal':
            if not errorMessage: #has errorMessage in sobject
                return client.sobject_to_dict(json_serialize=True)
            else:
                return {"errorMessage":{"code":500,"description":errorMessage}}
        # if requesting json
        if  return_type == 'json':
            data = client.sobject_to_json()
            return data, html_code,  {'Content-Type':'applicaion/json'}

        if error_flag and return_type != 'internal':
            return self.render_template( 'shipping/requestForm.html', companies=self.companies, cid = c.id,
                    form_title=form_title, form=self.form, message = "Form was submitted", service_path='shipping'
                    )

        # else redirct to results page
        result = client.sobject_to_dict(json_serialize=True)
        form_values = error = tableSet = {}
        table = True if return_type == 'table' else False
        error['errorMessage'] = ''
        form_values['vendorID'] = c.id
        form_values['vendorName'] = c.company_name
        form_values['return_type'] = return_type
        form_values['refNum'] = kw['referenceNumber'] if 'referenceNumber' in kw else ''
        form_values['refDate'] = kw['shipmentDateTimeStamp'] if 'shipmentDateTimeStamp' in kw else ''

        # found some returning OrderShipmentNotificationArray without OrderShipmentNotification
        try:
            check_row = result['OrderShipmentNotificationArray']['OrderShipmentNotification'][0]
            if check_row:
                if return_type == 'internal':
                    return check_row
                tableSet = create_table_set(result)
        except Exception as e:
            check_row = None
            error['errorMessage'] = "Error: unable to extract an OrderShipmentNotification. "
            error['errorMessage'] += "Expected notification or error message from Vendor. Exception: " + str(e)
            if not PRODUCTION:
                error['errorMessage'] += " Result: " +str(result)
            if return_type == 'internal':
                return result
        return self.render_template(
            'shipping/results.html', check_row=check_row, cid=c.id, tableSet=tableSet, form_title=form_title,
            companies=self.companies, table=table, error=error, form_values=form_values, service_path='shipping'
            )

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        if request.method == 'GET':
            form_title = 'Ship Status Request Form'
            cid = request.values.get('companyID', default_co)
            return self.render_template( 'shipping/requestForm.html',
                    companies=self.companies, cid = int(cid),
                    form_title=form_title, form=self.form, message = "Form was submitted",
                    data=False, service_path='shipping'
                    )
        # else deal with post
        c = db.session.query(Company).get(int(request.form['companyID']))
        kw = dict(
            wsVersion= c.shipping_version,
            password=c.password,
            id=c.user_name,
            queryType=request.form['queryType']
            )
        values = {
            'namespaces': {'ns':"http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/",
                'shar':"http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/SharedObjects/"
            },
            'method': {'ns':'GetOrderShipmentNotificationRequest'},
            'fields': [('shar','wsVersion', kw['wsVersion']),('shar','id', kw['id']),('shar','password', kw['password']),
                ('ns','queryType', kw['queryType'])
            ],
        'Filter': False
        }

        if 'refDate' in request.form and request.form['refDate']:
            kw['shipmentDateTimeStamp']=request.form['refDate']
            values['fields'].append(('ns','shipmentDateTimeStamp',request.form['refDate']))
        if 'refNum' in request.form and request.form['refNum']:
            kw['referenceNumber']=request.form['refNum']
            values['fields'].append(('ns','referenceNumber', request.form['refNum']))
        # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
        # in the debuger: use client.XML (what was sent) & client.response.text (returned response) & client.lastRequest for headers
        #     from .soap_utils import test_call
        #     test_call(service_url=c.order_url, service_method='GetOrderShipmentNotification',
        #                         serviceResponse='GetOrderShipmentNotificationResponse', values=values)

        # new fix in suds/xsd/sxbase.py takes care of the wsdl parsing issue and values only needed if using test_call above
        # However, leaving following line commented until fix is pushed to pypi
        # values = False
        return self.get_shipping_status(c, values, **kw)
