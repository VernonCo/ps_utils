import json, logging
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from flask import request, flash
from suds.client import Client
from .models import Company
from . import appbuilder, db
from .forms import InventoryForm
from .soap_utils import sobject_to_dict, sobject_to_json, basic_sobject_to_dict, getDoctor
from . import app
from jinja2 import Markup

PRODUCTION = app.config.get('PRODUCTION')

class Inventory(SimpleFormView):
    default_view = 'index'
    form = InventoryForm

    def check4InventoryFiltersV1(self, client, kw):
        """ check for filters to set on soap call on version 1.0.0 and 1.2.1"""
        if 'color' in request.form:
            filterColorArray = client.factory.create('FilterColorArray')
            filterColorArray.filterColor = request.form.getlist('color')
            kw['FilterColorArray'] = filterColorArray
        if 'size' in request.form:
            filterSizeArray = client.factory.create('FilterSizeArray')
            filterSizeArray.filterSize = request.form.getlist('size')
            kw['FilterSizeArray'] = filterSizeArray
        if 'misc' in request.form:
            filterMiscArray = client.factory.create('FilterSelectionArray')
            filterMiscArray.filterSelection = request.form.getlist('misc')
            kw['FilterSelectionArray'] = filterMiscArray
        return kw

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for inventory requests

        params:
        companyID = PS companyID
        productID = SKU
        serviceType = service method
        returnType = return type json or html
        [options v1]
            color = color filter
            size = size filter
            misc = generic filter
        """
        form_title = "Inventory Request Form"
        if request.method == 'GET':
            # TODO: get companies with version 2.0.0
            # set up javascript event for select if company selected has version 2.0.0
            c = db.session.query(Company).filter(Company.inventory_url != None).all()
            id = request.args.get('companyID', 126)
            prodID = request.args.get('productID', 8268)
            return self.render_template(
                    'inventory/requestForm.html', companies = c, title=form_title, id=int(id),
                    prodID=prodID, form=self.form, message = "Form was submitted", data=False
                    )
        else:
            c = db.session.query(Company).get(int(request.form['companyID']))
            service_version = 'V1'
            # TODO: will be changed to form variable when version 2.0.0 incorporated
            if c.inventory_version[:1] == '1':
                data = self.inventoryCallv1(c)
            else:
                data = self.inventoryCallv2(c)
                service_version = 'V2'
            if data == 'Unable to get Response' or \
                (request.form['serviceType'] == 'getFilterValues' and 'SoapFault' in data \
                    or 'errorMessage' in data and data['errorMessage']):

                if  request.form['returnType'] == 'json':
                    data = json.dumps(data)
                    return data, 200,  {'Content-Type':'applicaion/json'}
                # setup flash message for error
                if 'SoapFault' in data:
                    flash('Soap Fault: {}'.format(data['SoapFault']), 'error')
                elif 'errorMessage' in data and data['errorMessage']:
                    flash('Error Message: {} from {}'.format(data['errorMessage'],c), 'error')
                else:
                    flash('Error: {}'.format(data), 'error')

                c = db.session.query(Company).filter(Company.inventory_url != None).all()
                return self.render_template(
                        'inventory/requestForm.html', companies = c, title=form_title,
                        id=int(request.form['companyID']),
                        prodID=request.form['productID'],
                        form=self.form, message = "Form was submitted"
                        )

            if  request.form['returnType'] == 'json':
                data = sobject_to_json(data)
                return data, 200,  {'Content-Type':'applicaion/json'}

            if request.form['serviceType'] == 'getFilterValues':
                #redirect to new form with filter options
                data = sobject_to_dict(data)
                data['vendorID'] = c.id
                data['vendorName'] = c.company_name
                data['returnType'] = request.form['returnType']
                return self.render_template('inventory/filtersRequestForm{}.html'.format(service_version), data=data, form=self.form)

            # or finally redirct to results page
            data=sobject_to_dict(data, json_serialize=True)
            data['vendorID'] = c.id
            data['vendorName'] = c.company_name
            data['returnType'] = request.form['returnType']
            if 'SoapFault' in data:
                data['errorMessage'] = data['SoapFault']
            if 'errorMessage' in data and data['errorMessage']:
                checkRow = None
            else:
                if service_version == 'V1':
                    checkRow = data['ProductVariationInventoryArray']['ProductVariationInventory'][0]
                else:
                    checkRow = data['Inventory']['PartInventoryArray'][0]
            table = False
            template = 'inventory/results{}.html'.format(service_version)
            companies=db.session.query(Company).filter(Company.inventory_url != None).all()
            if request.form['returnType'] == 'table': # return html for table only
                table=True
                template = 'inventory/resultsTable{}.html'.format(service_version)
            return self.render_template(
                template, data=data, checkRow=checkRow, companies=companies,
                productID=request.form['productID'], table=table
                )

    def inventoryCallv1(self,c):
        """ used with version 1.0.0 and 1.2.1 """
        data = 'Unable to get Response'
        local_wsdl = getDoctor('INV', c.inventory_version, url=True)
        kw = dict(
                password=c.password,
                id=c.user_name,
                productID=request.form['productID'],
                productIDtype='Supplier',
                wsVersion= c.inventory_version)
        try:
            client = Client(local_wsdl, location='{}'.format(c.inventory_url))
            kw = self.check4InventoryFiltersV1(client, kw)

            # call the method
            func = getattr(client.service, request.form['serviceType'])
            data = func(**kw)
        except Exception as e:
            logging.error('WSDL Error on local wsdl and location {}: {}'.format(c.inventory_url,str(e)))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault': 'Soap Fault Error(1): ' +str(e)}
            try:
                # use remote wsdl
                # set schema doctor to fix missing schemas
                d = getDoctor('INV', c.inventory_version)
                client = Client(c.inventory_wsdl, doctor=d)
                kw = self.check4InventoryFiltersV1(client, kw)

                func = getattr(client.service, request.form['serviceType'])
                data = func(**kw)
            except Exception as e:
                msg = 'Error(2) on remote wsdl: {}'.format(str(e))
                if not PRODUCTION:
                    error_msg['SoapFault'] += '<br>' + msg
                logging.error(msg)
                try:
                    # use remote wsdl but set location to endpoint
                    # doctor to fix missing schemas
                    d = getDoctor('INV', c.inventory_version)
                    client = Client(c.inventory_wsdl, location='{}'.format(c.inventory_url), doctor=d)
                    kw = self.check4InventoryFiltersV1(client, kw)

                    func = getattr(client.service, request.form['serviceType'])
                    data = func(**kw)
                except Exception as e:
                    msg = 'Error(3) on remote wsdl and location {}: {}'.format(c.inventory_url,str(e))
                    if not PRODUCTION:
                        error_msg['SoapFault'] += '<br>' + msg
                    logging.error(str(e))
                    data = error_msg
        if not PRODUCTION and 'SoapFault' in data:
            data['SoapFault'] = Markup(data['SoapFault'])

        return data

    def inventoryCallv2(self,c):
        """ used with version 2.0.0 """
        # data = 'Unable to get Response'
        # TODO: finish code for version 2.0.0
        return {"SoapFault": 'Version 2.0.0 is not available yet.'}
