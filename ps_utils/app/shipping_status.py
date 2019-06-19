import json, logging
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from flask import request, flash
from suds.client import Client
from .models import Company
from . import appbuilder, db
from .forms import OrderStatusForm
from .soap_utils import sobject_to_dict, sobject_to_json, basic_sobject_to_dict, getDoctor, RawXML
from .tracking_util import Tracking_No
from . import app
from jinja2 import Markup
from sqlalchemy import or_, and_
from suds.xsd.doctor import Import, ImportDoctor

PRODUCTION = app.config.get('PRODUCTION')

class ShippingStatus(SimpleFormView):
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
                        if 'Package' in location['PackageArray']:
                            for package in location['PackageArray']['Package']:
                                temp['salesOrder'] += '<h3>TRN: {}</h3><div><table class="table-striped">'.format(package['trackingNumber'])
                                for k,v in package.items():
                                    if v and k != 'ItemArray':
                                        temp['salesOrder'] += '<tr><td class="right bold">' + k + '</td><td class="left">' + str(v) + "</td></tr>"
                                if package['ItemArray']['Item']:
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
                                if package['trackingNumber']: # elliminates placebo
                                    trk = Tracking_No(package['trackingNumber'], carrier=package['carrier'])
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
        c = db.session.query(Company).get(int(request.form['companyID']))
        data = self.shippingCall(c, 'getOrderShipmentNotification')

        # else if requesting json
        if  request.form['returnType'] == 'json':
            data = sobject_to_json(data)
            return data, 200,  {'Content-Type':'applicaion/json'}
        # if error return to request form
        if data == 'Unable to get Response' \
            or 'SoapFault' in data \
            or 'errorMessage' in data and data.errorMessage.code > 9:
            # found some non-compliant vendors returning code=0 and description=SUCCESS

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
            return self.render_template( 'shipping/requestForm.html', companies=companies, id=int(id),
                    form_title=form_title, form=self.form, message = "Form was submitted"
                    )

        # else redirct to results page
        result = sobject_to_dict(data, json_serialize=True)
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
                error['errorMessage'] = "Response structure error"
            if not PRODUCTION:
                error['errorMessage'] += ": " +str(sobject_to_dict(data, json_serialize=True))
        table = True if request.form['returnType'] == 'table' else False
        tableSet = {}
        if checkRow:
            tableSet = self.createTableSet(result)
        return self.render_template(
            'shipping/results.html', checkRow=checkRow, c=c, tableSet=tableSet, form_title=form_title,
            companies=companies, table=table, error=error, formValues=formValues
            )

    def shippingCall(self,c, serviceType):
        """ call the order status service """
        data = 'Unable to get Response'
        # get the local wsdl and inject the endpoint
        # ...should almost always work if they follow the wsdl and give a valid endpoint to PS
        local_wsdl = getDoctor('OSN', c.shipping_version, url=True)
        kw = dict(
                password=c.password,
                id=c.user_name,
                queryType=request.form['queryType'],
                wsVersion= c.shipping_version)
        raw = dict(
            namespaces=[
                dict(ns="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/"),
                dict(shar="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/SharedObjects/")
            ],
            body=dict(ns='GetOrderShipmentNotificationRequest'),
            fields=[['shar','id',kw['id']],['shar','password',kw['password']],['shar','wsVersion',kw['wsVersion']],
            ['ns','queryType',kw['queryType']]
            ]
        )
        if 'refDate' in request.form and request.form['refDate']:
            kw['shipmentDateTimeStamp']=request.form['refDate']
            raw['fields'].append(['ns','shipmentDateTimeStamp',request.form['refDate']])
        if 'refNum' in request.form and request.form['refNum']:
            kw['referenceNumber']=request.form['refNum']
            raw['fields'].append(['ns','referenceNumber',request.form['refNum']])
        ### suds3-py has trouble parsing this wsdl which has orderstatus in it but not used
        #   and multiple nested namespaces that are not quite consistant (ie. service xsd has shared objects
        #   as ns3, but sharedobjects.xsd has it as ns2
        # So creating the xml (provided by SoapUI) to inject and send
        rh = RawXML(**raw)
        message = rh.xml()
        try:
            client = Client(local_wsdl, location=c.shipping_url)
            client.set_options(cache=None)
            # call the method
            func = getattr(client.service, serviceType)
            data = func(__inject={'msg':message})
        except Exception as e:
            logging.error('WSDL Error on local wsdl and location {}: {}'.format(c.shipping_url,str(e)))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault': 'Error(1): ' +str(e)}
            assert False
            d = getDoctor('OSN', c.shipping_version)
            try:
                # use remote wsdl
                client = Client(c.shipping_wsdl, plugins=[d])
                func = getattr(client.service, serviceType)
                data = func(**kw)
            except Exception as e:
                msg = 'Soap Fault Error(2) on remote wsdl location {}: {}'.format(c.shipping_wsdl,str(e))
                if not PRODUCTION:
                    error_msg['SoapFault'] += '<br>' + msg
                logging.error(msg)
                try:
                    # use remote wsdl but set location to endpoint
                    client = Client(c.shipping_wsdl, location='{}'.format(c.shipping_url), plugins=[d])
                    func = getattr(client.service, serviceType)
                    data = func(**kw)
                except Exception as e:
                    msg = 'Soap Fault Error(3) on remote wsdl and location {}: {}'.format(c.shipping_url,str(e))
                    if not PRODUCTION:
                        error_msg['SoapFault'] += '<br>' + msg
                    logging.error(str(e))
                    data = error_msg

        return data

    def shippingCompanies(self):
        """ return available inventory companies"""
        return db.session.query(Company).filter(
                and_(Company.shipping_url != None, Company.user_name != None)
            ).all()
