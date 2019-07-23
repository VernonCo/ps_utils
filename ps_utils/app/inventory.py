import json
import copy
from flask_appbuilder import SimpleFormView, expose
from flask import request, flash
from .models import Company
from . import appbuilder, db
from . import app
from .soap_utils import SoapClient
from jinja2 import Markup
from sqlalchemy import or_, and_

PRODUCTION = app.config.get('PRODUCTION')

class Inventory(SimpleFormView):
    default_view = 'index'

    def filterDataV2(self, data):
        """
            manipulate data into color, size, and misc (partid) arrays so that the same filters form
            can be used by V! and V2
        """
        temp = copy.deepcopy(data)
        # PS documentation says object for FilterValues but getting array from some
        try:
            #only getting one in the list so really doesn't make sense to pass as list, but...
            filterValues = temp['FilterValues'][0]
        except:
            filterValues = temp['FilterValues']
        filterArray = filterValues['Filter']
        tempObj = {"productID":filterValues['productId']}
        try:
            tempObj['FilterColorArray'] = {}
            tempArray= []
            for color in filterArray['PartColorArray']['partColor']:
                tempArray.append(color)
            tempObj['FilterColorArray']['filterColor'] = tempArray
        except: # fails on missing index
            pass # is empty
        try:
            tempObj['FilterSizeArray'] = {}
            tempArray= []
            for label in filterArray['LabelSizeArray']['labelSize']:
                tempArray.append(label)
            tempObj['FilterSizeArray']['filterSize'] = tempArray
        except:
            pass # is empty
        try:
            tempObj['filterSelectionArray'] = {}
            tempArray= []
            for partId in filterArray['partIdArray']['partId']:
                tempArray.append(partId)
            tempObj['filterSelectionArray']['filterSelection'] = tempArray
        except:
            pass # is empty
        return tempObj

    @expose('/getVersion/', methods=['POST'])
    def getVersion(self, **kw):
        """ get latest inventory service version used by company """
        data = {"version":'1'}
        companyID = request.values.get('companyID', 0)
        if companyID != 0:
            companyID = int(companyID)
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
            companyID = int
            productID = 'SKU'
            serviceMethod = 'getFilterValues' or 'getInventoryLevels'
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
        id = request.values.get('companyID', 98)
        prodID = request.values.get('productID', 'BG344')
        if request.method == 'GET':
            return self.render_template(
                    'inventory/requestForm.html', companies=companies, title=form_title, id=int(id),
                    prodID=prodID, form=self.form, message = "Form was submitted", data=False
                    )
        # else deal with post
        data = False
        errorFlag = False
        htmlCode = 200
        # get request variables
        c = db.session.query(Company).get(int(request.form['companyID']))
        filters = {}
        if 'color' in request.values:
            filters['color'] = request.values.getlist('color')
        if 'size' in request.values:
            filters['size'] = request.values.getlist('size')
        if 'misc' in request.values:
            filters['misc'] = request.values.getlist('misc')
        serviceMethod = request.form['serviceMethod']
        service_version = request.form['serviceVersion']
        # make the soap request
        if service_version == 'V2':
            if not c.inventory_urlV2:
                flash('Version 2 not available for this supplier', 'error')
                errorFlag = True
                data = 'Unable to get Response'
            else:
                serviceVersion = c.inventory_versionV2
                serviceUrl = c.inventory_urlV2
                serviceWSDL = c.inventory_wsdlV2
                productID = 'productId'  # changed field name in V2...why?
        else:
            if not c.inventory_url:
                flash('Version 1 not available for this supplier', 'error')
                errorFlag = True
                data = 'Unable to get Response'
            else:
                serviceVersion = c.inventory_version
                serviceUrl = c.inventory_url
                serviceWSDL = c.inventory_wsdl
                productID = 'productID'
        if not errorFlag:
            kw = dict(
                wsVersion=serviceVersion,
                id=c.user_name)
            if c.password:
                kw['password'] = c.password
            kw[productID] = request.form['productID']
            values = None
            if service_version == 'V2':
                # create values for injected xml on Version 2 as the suds-py3 client has issues parcing the shared objects
                # some vendors accept the parced encoding while others reject it due to it being slightly off
                # injecting the correct xml each time takes care of this issue
                # Will need to look at this again when suds-py fix for issue #41 is released to pypi
                values = {
                    'method':{'ns':'GetFilterValuesRequest' if serviceMethod == 'getFilterValues' else 'GetInventoryLevelsRequest'},
                    'namespaces':{
                        'ns':"http://www.promostandards.org/WSDL/Inventory/2.0.0/",
                        'shar':"http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/"
                    },
                    'fields':[('shar','wsVersion', kw['wsVersion']),('shar','id', kw['id']),
                        ('shar','password', kw['password']),('shar',productID, kw[productID])],
                    'Filter': False
                }
                if filters:
                    values['Filter'] = {'ns':'shar','name':'Filter','filters':[]}
                    if 'misc' in filters:
                        temp = {'ns':'shar', 'name': 'partIdArray', 'filters':[]}
                        for filter in filters['misc']:
                            temp['filters'].append({'ns': 'shar', 'name':'partId','value': filter})
                        values['Filter']['filters'].append(temp)
                    if 'size' in filters:
                        temp = {'ns':'shar', 'name': 'LabelSizeArray', 'filters':[]}
                        for filter in filters['size']:
                            temp['filters'].append({'ns': 'shar', 'name':'labelSize','value': filter})
                        values['Filter']['filters'].append(temp)
                    if 'color' in filters:
                        temp = {'ns':'shar', 'name': 'PartColorArray', 'filters':[]}
                        for filter in filters['color']:
                            temp['filters'].append({'ns': 'shar', 'name':'partColor','value': filter})
                        values['Filter']['filters'].append(temp)
            else:
                kw['productIDtype'] = 'Supplier'

            # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
            #     from .soap_utils import testCall
            #     serviceResponse = 'GetFilterValuesResponse'if serviceMethod == 'getFilterValues' else 'GetInventoryLevelsResponse'
            #     testCall(serviceUrl=serviceUrl, serviceMethod=serviceMethod,
            #                         serviceResponse=serviceResponse, values=values)

            if not data:
                client = SoapClient(serviceMethod=serviceMethod, serviceUrl=serviceUrl, serviceCode='INV',
                    serviceVersion=serviceVersion, serviceWSDL=serviceWSDL, filters=filters, values=values, **kw)
                data = client.serviceCall()
                data = client.sobject_to_dict(json_serialize=True)


        # if error return to request form
        if data == 'Unable to get Response':
            flash('Error: {}'.format(data), 'error')
            errorFlag = True
            htmlCode = 500
        elif 'SoapFault' in data:
            # safe html from exceptions
            flash(Markup('{}'.format(data['SoapFault'])), 'error')
            errorFlag = True
            htmlCode = 500
        elif 'errorMessage' in data and data['errorMessage']:
            # unsafe html...errorMessage from suppliers
            flash('Error Message: {} from {}'.format(data['errorMessage'], c), 'error')
            errorFlag = True
        try:
            if data['ServiceMessageArray']['ServiceMessage'][0]['description']:
                # unsafe html...Message from suppliers
                msg = ''
                for row in data['ServiceMessageArray']['ServiceMessage']:
                    msg += row['description'] + "\n"
                flash(msg)
                errorFlag = True
        except:
            pass # on missing index

        # if requesting json
        if  request.form['returnType'] == 'json':
            return json.dumps(data), htmlCode,  {'Content-Type':'applicaion/json'}

        if errorFlag:
            return self.render_template(
                    'inventory/requestForm.html', companies=companies, form_title=form_title,
                    id=id, prodID=prodID, form=self.form, message = "Form was submitted"
                    )


        if request.form['serviceMethod'] == 'getFilterValues':
            #redirect to new form with filter options
            if service_version == 'V2':
                # manipulate data into color, size and misc (partId) arrays
                result = self.filterDataV2(data)
            result['vendorID'] = c.id
            result['vendorName'] = c.company_name
            result['returnType'] = request.form['returnType']
            result['serviceVersion'] = request.form['serviceVersion']

            return self.render_template('inventory/filtersRequestForm.html', data=result, form=self.form)

        # or finally redirct to results page
        result=data
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
                        result['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))
            else:
                try:
                    checkRow = result['Inventory']['PartInventoryArray']['PartInventory'][0]
                except:
                    checkRow = None
                    result['errorMessage'] = "Response structure error"
                    if not PRODUCTION:
                        result['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))

        table = False
        template = 'inventory/results{}.html'.format(service_version)
        if request.form['returnType'] == 'table': # return html for table only
            table=True
        return self.render_template(
            template, data=result, checkRow=checkRow, companies=companies, form=self.form,
            id=id, prodID=prodID, table=table, form_title=form_title
            )

    def inventoryCompanies(self):
        """ return available inventory companies"""
        return db.session.query(Company).filter(
                or_(
                    and_(Company.inventory_url != None, Company.user_name != None),
                    and_(Company.inventory_urlV2 != None, Company.user_name != None)
                )
            ).all()
