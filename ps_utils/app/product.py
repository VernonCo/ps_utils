import json, logging

from flask import flash, request
from flask_appbuilder import SimpleFormView, expose
from jinja2 import Markup
from sqlalchemy import and_, or_

from . import PRODUCTION, db, default_co, default_part
from .models import Company
from .soap_utils import SoapClient
from .table_utils import Table


def product_companies():
    """ return available product companies"""
    return db.session.query(Company).filter(
            or_(
                and_(Company.product_url != None, Company.user_name != None),
                and_(Company.product_urlV2 != None, Company.user_name != None)
            )
        ).all()


class Product(SimpleFormView):
    default_view = 'index'

    @expose('/getVersion/', methods=['POST'])
    def get_version(self, **kw):
        """ get latest product service version used by company """
        data = {"version":'1'}
        companyID = request.values.get('companyID', 0)
        if companyID != 0:
            companyID = int(companyID)
        if companyID:
            c = db.session.query(Company).get(companyID)
            if c.product_urlV2:
                data['version'] = '2'
        return json.dumps(data), 200,  {'Content-Type':'applicaion/json'}

    @expose('/index/', methods=['GET', 'POST'])
    def index(self, **kw):
        """
        form and display for product data requests

        params:
            companyID = int
            productID = 'SKU'
            service_method = 'getFilterValues' or 'getInventoryLevels'
            return_type = return json, table (getInventoryLevels only), or html
            service_version = 'V1' or 'V2'
            [options]
                color = color filter
                size = size filter
                misc = generic filter (v1) or array of partIds(v2)

        use request.form or request.values(for default values):  to be able to get either form post
            or external ajax request using content-type application/x-www-form-urlencoded
        """
        form_title = "Product Info Request Form"
        companies = product_companies()
        cid = request.values.get('companyID', default_co)
        prodID = request.values.get('productID', default_part)
        if request.method == 'GET':
            return self.render_template(
                    'product/requestForm.html', companies=companies, form_title=form_title, cid=int(cid),
                    prodID=prodID, form=self.form, message = "Form to submit for Product Data", data=False,
                    service_path='product'
                    )
        # else deal with post
        data = False
        error_flag = False
        html_code = 200
        # get request variables
        c = db.session.query(Company).get(int(request.form['companyID']))
        service_method = request.form['service_method']
        service_version = request.form['service_version']
        # make the soap request
        if service_version == 'V2':
            if not c.product_urlV2:
                flash('Version 2 not available for this supplier', 'error')
                error_flag = True
                data = 'Unable to get Response'
            else:
                service_version = c.product_versionV2
                service_url = c.product_urlV2
                service_WSDL = c.product_wsdl
        else:
            if not c.product_url:
                flash('Version 1 not available for this supplier', 'error')
                error_flag = True
                data = 'Unable to get Response'
            else:
                service_version = c.product_version
                service_url = c.product_url
                service_WSDL = c.product_wsdl
        if not error_flag:
            result={}
            result['vendorName'] = c.company_name
            result['return_type'] = request.form['return_type']
            kw = dict(
                wsVersion=service_version,
                id=c.user_name)
            if c.password:
                kw['password'] = result['companyID'] = c.password
            kw['productId'] = result['productId'] = request.form['productId']
            if 'partId' in request.form and request.form['partId']:
                kw['partId'] = result['partId'] = request.form['partId']
            if service_method == 'getProduct':
                kw['localizationCountry'] = result['localizationCountry'] = request.form['localizationCountry']
                kw['localizationLanguage'] = result['localizationLanguage'] = request.form['localizationLanguage']
            values = Filters = False

            # this block can be uncommented to get the returned xml if not parsing via WSDL to see what is the error
            #     serviceResponse = 'GetFilterValuesResponse'if service_method == 'getFilterValues' else 'GetInventoryLevelsResponse'

            #     test_call(service_url=service_url, service_method=service_method,
            #                         serviceResponse=serviceResponse, values=values)
            if not data:
                client = SoapClient(service_method=service_method, service_url=service_url, service_code='Product',
                    service_version=service_version, service_WSDL=service_WSDL, filters=Filters, values=values, **kw)
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
                    'product/requestForm.html', companies=companies, form_title=form_title,
                    cid=c.id, prodID=prodID, form=self.form, message = "Form was submitted",
                    service_path='product'
                    )

        # or finally redirct to results page
        if 'SoapFault' in result:
            result['errorMessage'] = result['SoapFault']
        return_field_name = request.form['service_method'].replace('get','')
        if return_field_name != 'Product':
            if return_field_name == 'ProductDateModified':
                return_field_name = 'ProductDateModifiedArray' if service_version == 'V2' else ''
            else:
                return_field_name +=  'Array'

        html_table = ''
        list_header = ''
        accordion_list = []
        if not error_flag:
            try:
                t = Table(data, return_field_name)
                t.parse_return()
                html_table = t.table_html()
                accordion_list = t.list_columns
                list_header = t.list_header
            except Exception as e:
                result['ErrorMessage'] = str(e)
                if not PRODUCTION:
                    result['ErrorMessage'] += ": " +str(client.sobject_to_dict(json_serialize=True))
        logging.debug("{}".format(data))
        logging.debug("{}".format(t.parsed))
        table = False
        template = 'product/results.html'
        if request.form['return_type'] == 'table': # return html for table only
            table=True
        return self.render_template(
            template, data=result, accordion_list=accordion_list, html_table=html_table, companies=companies, form=self.form,
            cid=c.id, table=table, form_title=form_title, list_header=list_header, service_path='product', prodID=prodID
            )
