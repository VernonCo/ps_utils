import json, logging
from flask_appbuilder import SimpleFormView, expose, has_access
from flask import request, flash
from .models import Company
from . import appbuilder, db
from .soap_utils import SoapClient, SoapRequest
from .tracking_util import Tracking_No
from . import app
from jinja2 import Markup
from sqlalchemy import or_, and_

PRODUCTION = app.config.get('PRODUCTION')

class ShippingStatus(SimpleFormView):
    """
        get order status from submitted form or external post
            or external ajax request using content-type application/x-www-form-urlencoded

        params:
            companyID = PS companyID
            queryType = query search type: 1=PO#,2=SO#,3=from date
            returnType = return type json or html
            [options depend on queryType]
                refNum for PO or SO#
                refDate for from Date

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
    """
    default_view = 'index'

    def createTableSet(self, result):
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

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        companies = self.shippingCompanies()
        form_title = 'Ship Status Request Form'
        if request.method == 'GET':
            # TODO: add and_ to check for username and password
            id = request.values.get('companyID', 126)
            return self.render_template( 'shipping/requestForm.html', companies=companies, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted", data=False
                    )
        # else deal with post
        errorFlag = False
        htmlCode = 200
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
        # try:
        #     client = SoapRequest(serviceUrl=c.shipping_url, serviceMethod='GetOrderShipmentNotification',
        #                         serviceResponse='GetOrderShipmentNotificationResponse', values=values)
        #     data = client.sendRequest()
        # except:
        #     assert False
        # assert False    # in the debuger: use client.XML (what was sent) & client.response.text (returned response)

        client = SoapClient(serviceMethod='getOrderShipmentNotification', serviceUrl=c.shipping_url, serviceWSDL=c.shipping_wsdl, serviceCode='OSN',
                serviceVersion=c.shipping_version, filters=False, values=values, **kw)
        data = client.serviceCall()

        # if error return to request form
        if data == {}:
            flash('Error: data not found for request', 'error')
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
        elif 'errorMessage' in data and data.errorMessage.code > 9:
            # found some non-compliant vendors returning code=0 and description=SUCCESS
            flash('Error Message: {} from {}'.format(data.errorMessage.description, c), 'error')
            errorFlag = True

        # if requesting json
        if  request.form['returnType'] == 'json':
            data = client.sobject_to_json()
            return data, htmlCode,  {'Content-Type':'applicaion/json'}

        if errorFlag:
            id = request.values.get('companyID', 126)
            return self.render_template( 'shipping/requestForm.html', companies=companies, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted"
                    )

        # else redirct to results page
        result = client.sobject_to_dict(json_serialize=True)
        formValues = error = {}
        error['errorMessage'] = ''
        formValues['vendorID'] = c.id
        formValues['vendorName'] = c.company_name
        formValues['returnType'] = request.form['returnType']
        formValues['refNum'] = request.form['refNum']
        formValues['refDate'] = request.form['refDate']
        if 'SoapFault' in result:
            error['errorMessage'] = result.SoapFault
        if 'errorMessage' in result and result['errorMessage']['code'] > 9:
            error['errorMessage'] = result.errorMessage.description
        try:
            checkRow = result['OrderShipmentNotificationArray']['OrderShipmentNotification'][0]
        except:
            checkRow = None
            if not error['errorMessage']:
                error['errorMessage'] = "Empty Response"
            if not PRODUCTION:
                error['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))
        table = True if request.form['returnType'] == 'table' else False
        tableSet = {}
        if checkRow:
            tableSet = self.createTableSet(result)
        return self.render_template(
            'shipping/results.html', checkRow=checkRow, c=c, tableSet=tableSet, form_title=form_title,
            companies=companies, table=table, error=error, formValues=formValues
            )

    def shippingCompanies(self):
        """ return available inventory companies"""
        return db.session.query(Company).filter(
                and_(Company.shipping_url != None, Company.user_name != None)
            ).all()
