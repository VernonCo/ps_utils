import copy,json

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_, or_

from . import PRODUCTION, db, default_co, default_part
from .models import Company
from .soap_utils import SoapClient


def inventory_companies():
    """ return available inventory companies"""
    return db.session.query(Company).filter(
            or_(
                and_(Company.inventory_url != None, Company.user_name != None),
                and_(Company.inventory_urlV2 != None, Company.user_name != None)
            )
        ).all()

def filter_data_v2(data):
    """
        manipulate data into color, size, and misc (partid) arrays so that the same filters form
        can be used by V! and V2
    """
    temp = copy.deepcopy(data)
    # PS documentation says object for filter_values but getting array from some
    try:
        #only getting one in the list so really doesn't make sense to pass as list, but...
        filter_values = temp['FilterValues'][0]
    except Exception as e:
        print(e)
        filter_values = temp['FilterValues']
    filter_array = filter_values['Filter']
    temp_obj = {"productID":filter_values['productId']}
    try:
        temp_obj['FilterColorArray'] = {}
        temp_array= []
        for color in filter_array['PartColorArray']['partColor']:
            temp_array.append(color)
        temp_obj['FilterColorArray']['filterColor'] = temp_array
    except Exception as e: # fails on missing index
        print(e)
    try:
        temp_obj['FilterSizeArray'] = {}
        temp_array= []
        for label in filter_array['LabelSizeArray']['labelSize']:
            temp_array.append(label)
        temp_obj['FilterSizeArray']['filterSize'] = temp_array
    except Exception as e: # fails on missing index
        print(e)
    try:
        temp_obj['filterSelectionArray'] = {}
        temp_array= []
        for partId in filter_array['partIdArray']['partId']:
            temp_array.append(partId)
        temp_obj['filterSelectionArray']['filterSelection'] = temp_array
    except Exception as e: # fails on missing index
        print(e)
    return temp_obj

class Inventory(SimpleFormView):
    default_view = 'index'

    @expose('/getVersion/', methods=['POST'])
    def get_version(self, **kw):
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
            service_method = 'getfilter_values' or 'getInventoryLevels'
            return_type = return json, table (getInventoryLevels only), or html
            service_version = 'V1' or 'V2'
            [options]
                color = color filter
                size = size filter
                misc = generic filter (v1) or array of partIds(v2)

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """
        form_title = "Inventory Request Form"
        companies = inventory_companies()
        cid = request.values.get('companyID', default_co)
        prodID = request.values.get('productID', default_part)
        if request.method == 'GET':
            return self.render_template(
                    'inventory/requestForm.html', companies=companies, form_title=form_title, cid=int(cid),
                    form=self.form, message = "Form was submitted", data=False,
                    prodID=prodID, service_path='inventory'
                    )
        # else deal with post
        data = False
        error_flag = False
        html_code = 200
        # get request variables
        c = db.session.query(Company).get(int(request.form['companyID']))
        filter_array = {}
        if 'color' in request.values:
            filter_array['color'] = request.values.getlist('color')
        if 'size' in request.values:
            filter_array['size'] = request.values.getlist('size')
        if 'misc' in request.values:
            filter_array['misc'] = request.values.getlist('misc')
        service_method = request.form['service_method']
        service_version = request.form['service_version']
        # make the soap request
        if service_version == 'V2':
            if not c.inventory_urlV2:
                flash('Version 2 not available for this supplier', 'error')
                error_flag = True
                data = 'Unable to get Response'
            else:
                inv_version = c.inventory_versionV2
                service_url = c.inventory_urlV2
                service_WSDL = c.inventory_wsdlV2
                productID = 'productId'  # changed field name in V2...why?
        else:
            if not c.inventory_url:
                flash('Version 1 not available for this supplier', 'error')
                error_flag = True
                data = 'Unable to get Response'
            else:
                inv_version = c.inventory_version
                service_url = c.inventory_url
                service_WSDL = c.inventory_wsdl
                productID = 'productID'
        if not error_flag:
            kw = dict(
                wsVersion=inv_version,
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
                    'method':{'ns':'Getfilter_valuesRequest' if service_method == 'getfilter_values' else 'GetInventoryLevelsRequest'},
                    'namespaces':{
                        'ns':"http://www.promostandards.org/WSDL/Inventory/2.0.0/",
                        'shar':"http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/"
                    },
                    'fields':[('shar','wsVersion', kw['wsVersion']),('shar','id', kw['id']),
                        ('shar','password', kw['password']),('shar',productID, kw[productID])],
                    'Filter': False
                }
                if filter_array:
                    values['Filter'] = {'ns':'shar','name':'Filter','filters':[]}
                    if 'misc' in filter_array:
                        temp = {'ns':'shar', 'name': 'partIdArray', 'filters':[]}
                        for filter_value in filter_array['misc']:
                            temp['filters'].append({'ns': 'shar', 'name':'partId','value': filter_value})
                        values['Filter']['filters'].append(temp)
                    if 'size' in filter_array:
                        temp = {'ns':'shar', 'name': 'LabelSizeArray', 'filters':[]}
                        for filter_value in filter_array['size']:
                            temp['filters'].append({'ns': 'shar', 'name':'labelSize','value': filter_value})
                        values['Filter']['filters'].append(temp)
                    if 'color' in filter_array:
                        temp = {'ns':'shar', 'name': 'PartColorArray', 'filters':[]}
                        for filter_value in filter_array['color']:
                            temp['filters'].append({'ns': 'shar', 'name':'partColor','value': filter_value})
                        values['Filter']['filters'].append(temp)
            else:
                kw['productIDtype'] = 'Supplier'

            # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
            #     serviceResponse = 'Getfilter_valuesResponse'if service_method == 'getfilter_values' else 'GetInventoryLevelsResponse'

            #     test_call(service_url=service_url, service_method=service_method,
            #                         serviceResponse=serviceResponse, values=values)

            if not data:
                client = SoapClient(service_method=service_method, service_url=service_url, service_code='INV',
                    service_version=inv_version, service_WSDL=service_WSDL, filters=filter_array, values=values, **kw)
                data = client.service_call()
                data = client.sobject_to_dict(json_serialize=True)


        # if error return to request form
        if data == 'Unable to get Response':
            flash('Error: {}'.format(data), 'error')
            error_flag = True
            html_code = 500
        elif 'SoapFault' in data:
            # safe html from exceptions
            flash(Markup('{}'.format(data['SoapFault'])), 'error')
            error_flag = True
            html_code = 500
        elif 'errorMessage' in data and data['errorMessage']:
            # unsafe html...errorMessage from suppliers
            flash('Error Message: {} from {}'.format(data['errorMessage'], c), 'error')
            error_flag = True
        try:
            if data['ServiceMessageArray']['ServiceMessage'][0]['description']:
                # unsafe html...Message from suppliers
                msg = ''
                for row in data['ServiceMessageArray']['ServiceMessage']:
                    msg += row['description'] + "\n"
                flash(msg)
                error_flag = True
        except Exception as e:
            print(e)
            # pass on missing index

        # if requesting json
        if  request.form['return_type'] == 'json':
            return json.dumps(data), html_code,  {'Content-Type':'applicaion/json'}

        if error_flag:
            return self.render_template(
                    'inventory/requestForm.html', companies=companies, form_title=form_title,
                    cid=int(cid), form=self.form, message = "Form was submitted",
                    prodID=prodID, service_path='inventory'
                    )

        result=data
        if request.form['service_method'] == 'getFilterValues':
            #redirect to new form with filter options
            if service_version == 'V2':
                # manipulate data into color, size and misc (partId) arrays
                result = filter_data_v2(data)
            result['vendorID'] = c.id
            result['vendorName'] = c.company_name
            result['return_type'] = request.form['return_type']
            result['service_version'] = request.form['service_version']

            return self.render_template('inventory/filtersRequestForm.html', data=result, form=self.form)

        # or finally redirct to results page
        result['vendorID'] = c.id
        result['vendorName'] = c.company_name
        result['return_type'] = request.form['return_type']
        if 'SoapFault' in result:
            result['errorMessage'] = result['SoapFault']
        if 'errorMessage' in result and result['errorMessage']:
            check_row = None
        else:
            if service_version == 'V1':
                try:
                    check_row = result['ProductVariationInventoryArray']['ProductVariationInventory'][0]
                except Exception as e:
                    check_row = None
                    result['errorMessage'] = str(e)
                    if not PRODUCTION:
                        result['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))
            else:
                try:
                    check_row = result['Inventory']['PartInventoryArray']['PartInventory'][0]
                except Exception as e:
                    check_row = None
                    result['errorMessage'] = str(e)
                    if not PRODUCTION:
                        result['errorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))

        table = False
        template = 'inventory/results{}.html'.format(service_version)
        if request.form['return_type'] == 'table': # return html for table only
            table=True
        return self.render_template(
            template, data=result, check_row=check_row, companies=companies, form=self.form,
            cid=int(cid), table=table, form_title=form_title, prodID=prodID, service_path='inventory'
            )
