import copy,json, logging

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_, or_

from . import PRODUCTION, db
from .models import Company
from .soap_utils import SoapClient
from .table_utils import Table

def ppcCompanies():
    """ return available inventory companies"""
    return db.session.query(Company).filter(
            or_(
                and_(Company.price_url != None, Company.user_name != None)
                #,and_(Company.price_urlV2 != None, Company.user_name != None)
            )
        ).all()

class PPC(SimpleFormView):
    default_view = 'index'

    @expose('/getVersion/', methods=['POST'])
    def getVersion(self, **kw):
        """ get latest inventory service version used by company """
        data = {"version":'1'}
        companyID = request.values.get('companyID', 0)
        if companyID != 0:
            companyID = int(companyID)
        if companyID:
            c = db.session.query(Company).get(companyID)
            if c.price_urlV2:
                data['version'] = '2'
        return json.dumps(data), 200,  {'Content-Type':'applicaion/json'}

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for inventory requests

        params:
            companyID = int
            productId = 'SKU'
            serviceMethod = 'getAvailableLocations', 'getDecorationColors' (requires locationId), 'GetFobPointsRequest',
                'GetAvailableChargesRequest', or 'GetConfigurationAndPricingRequest (requires fobid)'
            returnType = return json, table (getInventoryLevels only), or html
            serviceVersion = 'V1' or 'V2'

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """

        form_title = "PPC Request Form"
        companies = ppcCompanies()
        cid = request.values.get('companyID', 101)
        prodID = request.values.get('productId', 'BG344')
        if request.method == 'GET':
            return self.render_template(
                    'ppc/requestForm.html', companies=companies, form_title=form_title, cid=int(cid),
                    prodID=prodID, form=self.form, message = "Form was submitted", data=False, service_path='ppc'
                    )
        # else deal with post
        data = False
        errorFlag = False
        htmlCode = 200
        # get request variables
        c = db.session.query(Company).get(int(request.form['companyID']))
        serviceMethod = request.form['serviceMethod']
        service_version = 'V1'
        #TODO: add when version 2 added request.form['serviceVersion']
        # make the soap request
        # if service_version == 'V2':
        #     if not c.price_urlV2:
        #         flash('Version 2 not available for this supplier', 'error')
        #         errorFlag = True
        #         data = 'Unable to get Response'
        #     else:
        #         serviceVersion = c.price_versionV2
        #         serviceUrl = c.price_urlV2
        #         serviceWSDL = c.price_wsdlV2
        #         productId = 'productId'  # changed field name in V2...why?
        # else:
        if not c:
            flash('PS Service does not exist for Company # {}'.format(request.form['companyID']), 'error')
            errorFlag = True
            data = 'Unable to get Response'
        if not c.price_url:
            flash('Version 1 not available for this supplier', 'error')
            errorFlag = True
            data = 'Unable to get Response'
        else:
            serviceVersion = c.price_version
            serviceUrl = c.price_url
            serviceWSDL = c.price_wsdl
            productId = 'productId'
        if not errorFlag:
            kw = dict(
                wsVersion=serviceVersion,
                id=c.user_name)
            if c.password:
                kw['password'] = c.password
            kw[productId] = request.form['productId']
            kw['localizationCountry'] = request.form['localizationCountry']
            kw['localizationLanguage'] = request.form['localizationLanguage']
            if serviceMethod == 'getDecorationColors':
                kw['decorationId'] = request.form['decorationId']
            elif serviceMethod == 'getConfigurationAndPricing':
                kw['currency'] = request.form['currency']
                kw['fobId'] = request.form['fobId']
                kw['priceType'] = request.form['priceType']
                kw['configurationType'] = request.form['configurationType']
            values = None
            #TODO: when adding v2
            # if service_version == 'V2':
            #     # create values for injected xml on Version 2 as the suds-py3 client has issues parcing the shared objects
            #     # some vendors accept the parced encoding while others reject it due to it being slightly off
            #     # injecting the correct xml each time takes care of this issue
            #     # Will need to look at this again when suds-py fix for issue #41 is released to pypi
            #     values = {
            #         'method':{'ns':'GetFilterValuesRequest' if serviceMethod == 'getFilterValues' else 'GetInventoryLevelsRequest'},
            #         'namespaces':{
            #             'ns':"http://www.promostandards.org/WSDL/Inventory/2.0.0/",
            #             'shar':"http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/"
            #         },
            #         'fields':[('shar','wsVersion', kw['wsVersion']),('shar','id', kw['id']),
            #             ('shar','password', kw['password']),('shar',productID, kw[productID])],
            #         'Filter': False
            #     }
            #     if Filters:
            #         values['Filter'] = {'ns':'shar','name':'Filter','filters':[]}
            #         if 'misc' in Filters:
            #             temp = {'ns':'shar', 'name': 'partIdArray', 'filters':[]}
            #             for filterValue in Filters['misc']:
            #                 temp['filters'].append({'ns': 'shar', 'name':'partId','value': filterValue})
            #             values['Filter']['filters'].append(temp)
            #         if 'size' in Filters:
            #             temp = {'ns':'shar', 'name': 'LabelSizeArray', 'filters':[]}
            #             for filterValue in Filters['size']:
            #                 temp['filters'].append({'ns': 'shar', 'name':'labelSize','value': filterValue})
            #             values['Filter']['filters'].append(temp)
            #         if 'color' in Filters:
            #             temp = {'ns':'shar', 'name': 'PartColorArray', 'filters':[]}
            #             for filterValue in Filters['color']:
            #                 temp['filters'].append({'ns': 'shar', 'name':'partColor','value': filterValue})
            #             values['Filter']['filters'].append(temp)
            Filters = False
            # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
            #     serviceResponse = 'GetFilterValuesResponse'if serviceMethod == 'getFilterValues' else 'GetInventoryLevelsResponse'

            #     testCall(serviceUrl=serviceUrl, serviceMethod=serviceMethod,
            #                         serviceResponse=serviceResponse, values=values)

            if not data:
                client = SoapClient(serviceMethod=serviceMethod, serviceUrl=serviceUrl, serviceCode='PPC',
                    serviceVersion=serviceVersion, serviceWSDL=serviceWSDL, filters=Filters, values=values, **kw)
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
        elif 'ErrorMessage' in data and data['ErrorMessage']:
            # unsafe html...ErrorMessage from suppliers
            flash('Error Message: {} from {}'.format(data['ErrorMessage']['description'], c), 'error')
            errorFlag = True


        # if requesting json
        if  request.form['returnType'] == 'json':
            return json.dumps(data), htmlCode,  {'Content-Type':'applicaion/json'}

        if errorFlag and request.form['returnType'] != 'table':
            return self.render_template(
                    'ppc/requestForm.html', companies=companies, form_title=form_title,
                    cid=int(cid), prodID=prodID, form=self.form, message = "Form was submitted"
                    , service_path='ppc'
                    )


        result={}
        result['companyID'] = c.id
        result['vendorName'] = c.company_name
        result['returnType'] = request.form['returnType']
        result['productId'] = request.form['productId']
        result['localizationCountry'] = request.form['localizationCountry']
        result['localizationLanguage'] = request.form['localizationLanguage']
        result['configurationType'] = request.form['configurationType']
        result['priceType'] = request.form['priceType']
        result['currency'] = request.form['currency']
        if request.form['serviceMethod'] == 'getFobPoints':
            data.update(result)
            #redirect to new form with filter options
            # if service_version == 'V2':
            #     # manipulate data into color, size and misc (partId) arrays
            #     result = filterDataV2(data)
            # result['serviceVersion'] = request.form['serviceVersion']

            return self.render_template('ppc/filtersRequestForm.html', data=data,
                                        form=self.form, service_path='ppc')
        html_table = ''
        list_header = ''
        accordionList = []
        if not errorFlag:
            # try:
            t = Table(data, request.form['serviceMethod'].replace('get',''))
            t.parse_return()
            html_table = t.table_html()
            accordionList = t.listColumns
            list_header = t.list_header
            # except Exception as e:
            #     result['ErrorMessage'] = str(e)
            #     if not PRODUCTION:
            #         result['ErrorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))
        logging.debug("{}".format(data))
        logging.debug("{}".format(t.parsed))
        table = False
        template = 'ppc/results{}.html'.format(service_version)
        if request.form['returnType'] == 'table': # return html for table only
            table=True
        return self.render_template(
            template, data=result, accordionList=accordionList, html_table=html_table, companies=companies, form=self.form,
            cid=c.id, table=table, form_title=form_title, list_header=list_header, service_path='ppc', prodID=prodID
            )
