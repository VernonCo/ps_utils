import json, logging
import copy
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from flask import request, flash
from suds.client import Client
from .models import Company
from . import appbuilder, db
from .forms import InventoryForm
from .soap_utils import sobject_to_dict, sobject_to_json, basic_sobject_to_dict, getDoctor
from . import app
from jinja2 import Markup
from sqlalchemy import or_, and_

PRODUCTION = app.config.get('PRODUCTION')

class Inventory(SimpleFormView):
    default_view = 'index'
    form = InventoryForm

    def check4InventoryFiltersV1(self, client, kw, filters):
        """ check for filters to set on soap call on version 1.0.0 and 1.2.1"""
        if filters:
            if 'color' in filters:
                filterColorArray = client.factory.create('FilterColorArray')
                filterColorArray.filterColor = filters['color']
                kw['FilterColorArray'] = filterColorArray
            if 'size' in filters:
                filterSizeArray = client.factory.create('FilterSizeArray')
                filterSizeArray.filterSize = filters['size']
                kw['FilterSizeArray'] = filterSizeArray
            if 'misc' in filters:
                filterMiscArray = client.factory.create('FilterSelectionArray')
                filterMiscArray.filterSelection = filters['misc']
                kw['FilterSelectionArray'] = filterMiscArray
        return kw

    def check4InventoryFiltersV2(self, client, kw, filters):
        """ check for filters to set on soap call on version 1.0.0 and 1.2.1"""
        if filters:
            Filter = client.factory.create('ns3:Filter')
            if 'color' in filters:
                PartColorArray = client.factory.create('ns3:PartColorArray')
                PartColorArray.PartColor = filters['color']
                Filter.filterColorArray = PartColorArray
            if 'size' in filters:
                LabelSizeArray = client.factory.create('ns3:LabelSizeArray')
                LabelSizeArray.LabelSize = filters['size']
                Filter.LabelSizeArray = LabelSizeArray
            if 'misc' in filters:
                partIdArray = client.factory.create('ns3:partIdArray')
                partIdArray.partId = filters['misc']
                Filter.partIdArray = partIdArray
            kw['Filter'] = Filter
        return kw

    def filterDataV2(self, data):
        """
            manipulate data into color, size, and misc (partid) arrays so that the same filters form
            can be used by V! and V2
        """
        temp = copy.deepcopy(data)
        data = {"productID":temp['FilterValues']['productId']}
        try:
            data['FilterColorArray'] = {}
            data['FilterColorArray']['filterColor'] = temp['FilterValues']['Filter']['PartColorArray']['partColor']
        except: # fails on missing index
            pass # is empty
        try:
            data['FilterSizeArray'] = {}
            data['FilterSizeArray']['filterSize'] = temp['FilterValues']['Filter']['LabelSizeArray']['labelSize']
        except:
            pass # is empty
        try:
            data['filterSelectionArray'] = {}
            data['filterSelectionArray']['filterSelection'] = temp['FilterValues']['Filter']['partIdArray']['partId']
        except:
            pass # is empty
        return data

    @expose('/getVersion/', methods=['POST'])
    def getVersion(self, **kw):
        """ get latest inventory service version used by company """
        data = {"version":'1'}
        companyID = int(request.values.get('companyID', 0))
        if companyID:
            c = db.session.query(Company).get(companyID)
            if c.inventory_urlV2:
                data['version'] = '2'
        return json.dumps(data), 200,  {'Content-Type':'applicaion/json'}

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for inventory requests

        params:
        companyID = 'STAR'
        productID = 'SKU'
        serviceType = 'getFilterValues' or 'getInventoryLevels'
        returnType = return json, table (getInventoryLevels only), or html
        serviceVersion = 'V1' or 'V2'
        [options]
            color = color filter
            size = size filter
            misc = generic filter (v1) or array of partIds(v2)

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """
        form_title = "Inventory Request Form"
        companies = self.inventoryCompanies()
        if request.method == 'GET':
            id = request.values.get('companyID', 126)
            prodID = request.values.get('productID', 8268)
            return self.render_template(
                    'inventory/requestForm.html', companies=companies, title=form_title, id=int(id),
                    prodID=prodID, form=self.form, message = "Form was submitted", data=False
                    )
        else:
            errorFlag = False
            # get request variables
            c = db.session.query(Company).get(int(request.form['companyID']))
            filters = {}
            if 'color' in request.values:
                filters['color'] = request.values.getlist('color')
            if 'size' in request.values:
                filters['size'] = request.values.getlist('size')
            if 'misc' in request.values:
                filters['misc'] = request.values.getlist('misc')
            serviceMethod = request.form['serviceType']
            service_version = request.form['serviceVersion']

            # make the soap request
            if service_version == 'V2':
                if not c.inventory_urlV2:
                    flash('Version 2 not available for this supplier', 'error')
                    errorFlag = True
                    data = 'Unable to get Response'
                else:
                    data = self.inventoryCallV2(c, filters, serviceMethod)
            else:
                if not c.inventory_url:
                    flash('Version 1 not available for this supplier', 'error')
                    errorFlag = True
                    data = 'Unable to get Response'
                else:
                    data = self.inventoryCallV1(c, filters, serviceMethod)

            if  request.form['returnType'] == 'json':
                data = sobject_to_json(data)
                return data, 200,  {'Content-Type':'applicaion/json'}

            # if error return to request form
            if data == 'Unable to get Response':
                flash('Error: {}'.format(data), 'error')
                errorFlag = True
            elif 'SoapFault' in data:
                # safe html from exceptions
                flash(Markup('{}'.format(data['SoapFault'])), 'error')
                errorFlag = True
            elif 'errorMessage' in data and data['errorMessage']:
                # unsafe html...errorMessage from suppliers V1
                flash('Error Message: {} from {}'.format(data['errorMessage'],c), 'error')
                errorFlag = True
            try:
                if data['ServiceMessageArray']['ServiceMessage'][0]['description']:
                    # unsafe html...errorMessage from suppliers
                    msg = ''
                    for row in data['ServiceMessageArray']['ServiceMessage']:
                        msg += row['description'] + "\n"
                    flash(msg)
                    errorFlag = True
            except:
                pass # on missing index
            if errorFlag:
                return self.render_template(
                        'inventory/requestForm.html', companies=companies, title=form_title,
                        id=int(request.form['companyID']),
                        prodID=request.form['productID'],
                        form=self.form, message = "Form was submitted"
                        )


            if request.form['serviceType'] == 'getFilterValues':
                #redirect to new form with filter options
                result = sobject_to_dict(data)
                if service_version == 'V2':
                    # manipulate data into color, size and misc (partId) arrays
                    result = self.filterDataV2(result)
                result['vendorID'] = c.id
                result['vendorName'] = c.company_name
                result['returnType'] = request.form['returnType']
                result['serviceVersion'] = request.form['serviceVersion']

                return self.render_template('inventory/filtersRequestForm.html', data=result, form=self.form)

            # or finally redirct to results page
            result=sobject_to_dict(data, json_serialize=True)
            result['vendorID'] = c.id
            result['vendorName'] = c.company_name
            result['returnType'] = request.form['returnType']
            if 'SoapFault' in result:
                result['errorMessage'] = result['SoapFault']
            if 'errorMessage' in result and result['errorMessage']:
                checkRow = None
            else:
                if service_version == 'V1':
                    try:
                        checkRow = result['ProductVariationInventoryArray']['ProductVariationInventory'][0]
                    except:
                        checkRow = None
                        result['errorMessage'] = "Response structure error"
                        if not PRODUCTION:
                            result['errorMessage'] += ": " +str(sobject_to_dict(data, json_serialize=True))
                else:
                    try:
                        checkRow = result['Inventory']['PartInventoryArray']['PartInventory'][0]
                    except:
                        checkRow = None
                        result['errorMessage'] = "Response structure error"
                        if not PRODUCTION:
                            result['errorMessage'] += ": " +str(sobject_to_dict(data, json_serialize=True))

            table = False
            template = 'inventory/results{}.html'.format(service_version)
            if request.form['returnType'] == 'table': # return html for table only
                table=True
            return self.render_template(
                template, data=result, checkRow=checkRow, companies=companies, form=self.form,
                productID=request.form['productID'], table=table
                )

    def inventoryCallV1(self,c, filters, serviceMethod):
        """ used with version 1.0.0 and 1.2.1 """
        data = 'Unable to get Response'
        local_wsdl = getDoctor('INV', c.inventory_version, url=True)
        kw = dict(
            id=c.user_name,
            productID=request.form['productID'],
            productIDtype='Supplier',
            wsVersion= c.inventory_version)
        if c.password:
            kw['password'] =c.password
        try:
            client = Client(local_wsdl, location='{}'.format(c.inventory_url))
            # must create filters after each client request
            kw = self.check4InventoryFiltersV1(client, kw, filters)

            # call the method
            func = getattr(client.service, serviceMethod)
            data = func(**kw)
        except Exception as e:
            logging.error('WSDL Error on local wsdl and location {}: {}'.format(c.inventory_url,str(e)))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault': 'Soap Fault Error(1): ' +str(e)}
            # set schema doctor to fix missing schemas
            d = getDoctor('INV', c.inventory_version)
            try:
                # use remote wsdl
                client = Client(c.inventory_wsdl, plugins=[d])
                kw = self.check4InventoryFiltersV1(client, kw, filters)

                func = getattr(client.service, request.form['serviceType'])
                data = func(**kw)
            except Exception as e:
                msg = 'Soap Fault Error(2) on remote wsdl: {}'.format(str(e))
                if not PRODUCTION:
                    error_msg['SoapFault'] += '<br>' + msg
                logging.error(msg)
                try:
                    # use remote wsdl but set location to endpoint
                    client = Client(c.inventory_wsdl, location='{}'.format(c.inventory_url), plugins=[d])
                    kw = self.check4InventoryFiltersV1(client, kw, filters)

                    func = getattr(client.service, request.form['serviceType'])
                    data = func(**kw)
                except Exception as e:
                    msg = 'Soap Fault Error(3) on remote wsdl and location {}: {}'.format(c.inventory_url,str(e))
                    if not PRODUCTION:
                        error_msg['SoapFault'] += '<br>' + msg
                    logging.error(str(e))
                    data = error_msg
        if not PRODUCTION and 'SoapFault' in data:
            data['SoapFault'] = Markup(data['SoapFault'])

        return data

    def inventoryCallV2(self,c, filters, serviceMethod):
        """ used with version 2.0.0 """
        data = 'Unable to get Response'
        local_wsdl = getDoctor('INV', c.inventory_versionV2, url=True)
        kw = dict(
            id=c.user_name,
            productId=request.form['productID'],
            wsVersion=c.inventory_versionV2)
        if c.password:
            kw['password'] =c.password
        try:
            client = Client(local_wsdl, location='{}'.format(c.inventory_urlV2))
            # must create filters after each client request
            kw = self.check4InventoryFiltersV2(client, kw, filters)
            # call the method
            func = getattr(client.service, serviceMethod)
            data = func(**kw)
        except Exception as e:
            logging.error('WSDL Error on local wsdl and location {}: {}'.format(c.inventory_urlV2,str(e)))
            # set up error message to be given if all tries fail. As this one should have worked, give this error
            error_msg = {'SoapFault': 'Soap Fault Error(1): ' +str(e)}
            # set schema doctor to fix missing schemas
            d = getDoctor('INV', c.inventory_versionV2)
            try:
                # use remote wsdl
                client = Client(c.inventory_wsdl, plugins=[d])
                kw = self.check4InventoryFiltersV2(client, kw, filters)

                func = getattr(client.service, serviceMethod)
                data = func(**kw)
            except Exception as e:
                msg = 'Soap Fault Error(2) on remote wsdl: {}'.format(str(e))
                if not PRODUCTION:
                    error_msg['SoapFault'] += '<br>' + msg
                logging.error(msg)
                try:
                    # use remote wsdl but set location to endpoint
                    client = Client(c.inventory_wsdl, location='{}'.format(c.inventory_urlV2), plugins=[d])
                    kw = self.check4InventoryFiltersV2(client, kw, filters)

                    func = getattr(client.service, serviceMethod)
                    data = func(**kw)
                except Exception as e:
                    msg = 'Soap Fault Error(3) on remote wsdl and location {}: {}'.format(c.inventory_urlV2,str(e))
                    if not PRODUCTION:
                        error_msg['SoapFault'] += '<br>' + msg
                    logging.error(str(e))
                    data = error_msg
        if not PRODUCTION and 'SoapFault' in data:
            data['SoapFault'] = Markup(data['SoapFault'])

        return data

    def inventoryCompanies(self):
        """ return available inventory companies"""
        return db.session.query(Company).filter(
                or_(
                    and_(Company.inventory_url != None, Company.user_name != None),
                    and_(Company.inventory_urlV2 != None, Company.user_name != None)
                )
            ).all()
