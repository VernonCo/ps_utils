
import requests, json, os, re, logging
from urllib.parse import urlparse
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from suds.sudsobject import asdict
# logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
# logging.getLogger('suds.client').setLevel(logging.DEBUG)
from flask import render_template, flash, request, jsonify, config
from flask_babel import lazy_gettext as _
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from .models import Company
from . import appbuilder, db
from .forms import InventoryForm
# only needed if importing passwords from previous db
import MySQLdb
from . import app
import ssl

PRODUCTION = app.config.get('PRODUCTION')

"""
    Create your Model based REST API::

    class MyModelApi(ModelRestApi):
        datamodel = SQLAInterface(MyModel)

    appbuilder.add_api(MyModelApi)


    Create your Views::


    class MyModelView(ModelView):
        datamodel = SQLAInterface(MyModel)


    Next, register your Views::


    appbuilder.add_view(
        MyModelView,
        "My View",
        icon="fa-folder-open-o",
        category="My Category",
        category_icon='fa-envelope'
    )
"""

"""
    Application wide 404 error handler
"""
def getDoctor( code, version, url=False):
    """ return service type for code """
        # set schema doctor to fix missing schemas
    if code == 'INV':
        service =  'InventoryService'
    if code == 'MED':
        service =  'MediaService'
    if code == 'ONS':
        service =  'OrderShipmentNotificationService'
    if code == 'ODRSTAT':
        service =  'OrderStatusService'
    if code == 'Product':
        service =  'ProductDataService'
    if code == 'PPC':
        service =  'PricingAndConfiguration'
    if code == 'PO':
        service =  'PO'
    if code == 'INVC':
        service =  'Invoice'
    if url:
        return 'file:///{}/static/wsdl/{}/{}/{}.wsdl'.format(os.getenv('SERVER_PATH'), service,version,service)
    imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
    imp.filter.add(request.url_root + '/static/wsdl/{}/{}/'.format(service, version))
    d = ImportDoctor(imp)
    return d


def basic_sobject_to_dict(obj):
    """Converts suds object to dict very quickly.
    Does not serialize date time or normalize key case.
    :param obj: suds object
    :return: dict object
    """
    if not hasattr(obj, '__keylist__'):
        return obj
    data = {}
    fields = obj.__keylist__
    for field in fields:
        val = getattr(obj, field)
        if isinstance(val, list):
            data[field] = []
            for item in val:
                data[field].append(basic_sobject_to_dict(item))
        else:
            data[field] = basic_sobject_to_dict(val)
    return data


def sobject_to_dict(obj, key_to_lower=False, json_serialize=False):
    """
    Converts a suds object to a dict.
    :param json_serialize: If set, changes date and time types to iso string.
    :param key_to_lower: If set, changes index key name to lower case.
    :param obj: suds object
    :return: dict object
    """
    import datetime

    if not hasattr(obj, '__keylist__'):
        if json_serialize and isinstance(obj, (datetime.datetime, datetime.time, datetime.date)):
            return obj.isoformat()
        else:
            return obj
    data = {}
    fields = obj.__keylist__
    for field in fields:
        val = getattr(obj, field)
        if key_to_lower:
            field = field.lower()
        if isinstance(val, list):
            data[field] = []
            for item in val:
                data[field].append(sobject_to_dict(item, json_serialize=json_serialize))
        else:
            data[field] = sobject_to_dict(val, json_serialize=json_serialize)
    return data


def sobject_to_json(obj, key_to_lower=False):
    """
    Converts a suds object to json.
    :param obj: suds object
    :param key_to_lower: If set, changes index key name to lower case.
    :return: json object
    """
    import json
    data = sobject_to_dict(obj, key_to_lower=key_to_lower, json_serialize=True)
    return json.dumps(data)

class Companies(ModelView):
    datamodel = SQLAInterface(Company)
    list_columns = ['company_name', 'erp_id']

appbuilder.add_view( Companies, "List Companies", icon="fa-list", category="Companies", category_icon='fa-database')

class Inventory(SimpleFormView):
    form = InventoryForm
    form_title = "Inventory Request Form"
    message = "Form was submitted"

    def form_get(self, form, **kw):  # get the form to display
        form.field1.data = 126
        form.field2.data = "2825"

    def form_post(self, form):  # process the form submission
        """
        field1 = companyID
        field2 = productID
        field3 = service method
        field4 = return type json or html
        [options]
            color = color filter
            size = size filter
            misc = generic filter
        """
        data = 'Unable to get Response'
        c = db.session.query(Company).get(int(request.form['field1']))
        # set schema doctor to fix missing schemas
        url = getDoctor('INV', c.inventory_version, url=True)
        kw = dict(
                password=c.password,
                id=c.user_name,
                productID=request.form['field2'],
                productIDtype='Supplier',
                wsVersion= c.inventory_version)
        try:
            client = Client(url, location='{}'.format(c.inventory_url))  #c.inventory_wsdl, doctor=d

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

            # call the method
            func = getattr(client.service, request.form['field3'])
            data = func(**kw)
        except Exception as e:
            if not PRODUCTION:
                logging.error('Error on local wsdl and location: {}'.format(c.inventory_url))
            logging.error(str(e))
            try:
                # use remote wsdl
                # set schema doctor to fix missing schemas
                d = getDoctor('INV', c.inventory_version)
                client = Client(c.inventory_wsdl, doctor=d)

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

                func = getattr(client.service, request.form['field3'])
                data = func(**kw)
            except Exception as e:
                if not PRODUCTION:
                    logging.error('Error on remote wsdl ')
                logging.error(str(e))
                try:
                    # use remote wsdl but set location to endpoint
                    # doctor to fix missing schemas
                    d = getDoctor('INV', c.inventory_version)
                    client = Client(c.inventory_wsdl, location='{}'.format(c.inventory_url), doctor=d)

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

                    func = getattr(client.service, request.form['field3'])
                    data = func(**kw)
                except Exception as e:
                    if not PRODUCTION:
                        logging.error('Error on remote wsdl and location: {}'.format(c.inventory_url))
                    logging.error(str(e))
        # assert False

        if data == 'Unable to get Response':
            if  request.form['field4'] == 'json':
                data = json.dumps(data)
                return data, 200,  {'Content-Type':'applicaion/json'}
            flash('Submitted request to {}'.format(c), "info")
            return data
        elif request.form['field3'] == 'getFilterValues':
            #redirect to new form with filter options
                data = sobject_to_dict(data)
                data['vendorID'] = c.id
                data['vendorName'] = c.company_name
                return self.render_template('inventoryRequestForm.html', data=data, form=form)
        else:
            if  request.form['field4'] == 'json':
                data = sobject_to_json(data)
                return data, 200,  {'Content-Type':'applicaion/json'}
            #redirct to results page
            data=sobject_to_dict(data, json_serialize=True)
            # assert False
            return self.render_template('inventoryRequest.html', data=data)


appbuilder.add_view(
    Inventory,
    "INV Request",
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
) #  label=_("Inventory Request Form"),

class Utilities(BaseView):

    default_view = 'index'

    @expose('/index/')
    def index(self):
        return "Provides Utilities to for Promo Standards"

    @expose('/inventoryRequest/')
    def inventoryRequest(self):
        # do something with param1
        # and render template with param
        param1 = 'Goodbye %s' % ('rtest')
        return self.render_template('inventoryRequest.html', param1=param1)

    @expose('/statusRequest/')
    def statusRequest(self):
        # do something with param1
        # and render template with param
        param1 = 'Goodbye %s' % ('rtest')
        return param1

    @expose('/updateCompanies/')
    @has_access
    def updateCompanies(self):
        """ gets a list of companies from PromoStandards
            Checks if a distributor and gets services and urls for company
            Check urls and versions and saves company information
        """
        # get company list
        uri = 'https://services.promostandards.org/WebServiceRepository/WebServiceRepository.svc/json/companies'
        try:
            uResponse = requests.get(uri)
            companies = uResponse.json()
        except requests.ConnectionError:
            return "Connection Error"
        #for each company get url endpoints and versions
        for company in companies:
            if company['Type'] == 'Supplier':
                addC = False
                # set c from existing or create new one
                c = db.session.query(Company).filter_by(ps_id = company['Code']).first()
                if not c:
                    c = Company()
                    c.ps_id = company['Code']
                    c.company_name = company['Name']
                    addC = True
            else:
                continue
            # get endpoints for c
            uri = 'https://services.promostandards.org/WebServiceRepository/WebServiceRepository.svc/json/companies/{}/endpoints'.format(c.ps_id)
            try:
                r = requests.get(uri)
                endpoints = r.json()
            except:
                continue
            #test retreiving wsdl with out errors from each endpoint
            has_url = False
            for row in endpoints:
                epS = row['Service']
                print(str(epS))
                # check if url status is Production, no consistency here and the other variables on placement
                try:
                    status = epS['Status']
                except Exception as e:
                    try:
                        logging.error("Get Status Error {0}".format(getattr(e, 'message', repr(e))))
                        status = epS['Service']['Status']
                    except Exception as e:
                        logging.error("Get Status Error {0}".format(getattr(e, 'message', repr(e))))
                        logging.error(str(epS))
                        continue
                if status != 'Production': continue
                try:  # found some without ServiceType['code']
                    code = epS['ServiceType']['Code']
                except Exception as e:
                    logging.error("Get Code Error {0}".format(getattr(e, 'message', repr(e))))
                    logging.error(str(epS))
                    continue
                try:
                    service_version = epS['Version']
                except Exception as e:
                    try:
                        logging.error("Error {0}".format(getattr(e, 'message', repr(e))))
                        service_version = epS['ServiceType']['Version']
                    except Exception as e:
                        logging.error("Error {0}".format(getattr(e, 'message', repr(e))))
                        logging.error(str(epS))
                        continue
                # set wsdl endpoint as valid uri in case service URL doesn't work...can use this as backup
                if not row['URL'].strip(): continue  # had some as Production with out a URL
                url = urlparse(row['URL'])    # use scheme and domain from URL
                wsdl_url = '{}://{}/{}'.format(url.scheme, url.netloc, re.sub('wsdl','',epS['WSDL'].strip(), 1, flags=re.I))
                # check endpoint for wsdl retrieval
                good_url = self.tryUrl(row['URL'].strip(), wsdl_url, code, service_version)
                if good_url:
                    has_url = True
                    if code == 'INV':
                        c.inventory_url = row['URL']
                        c.inventory_wsdl = good_url
                        c.inventory_version = service_version
                    if code == 'INVC':
                        c.invoice_url = row['URL']
                        c.invoice_wsdl = good_url
                        c.invoice_version = service_version
                    if code == 'MED':
                        c.media_url = row['URL']
                        c.media_wsdl = good_url
                        c.media_version = service_version
                    if code == 'OSN':
                        c.shipping_url = row['URL']
                        c.shipping_wsdl = good_url
                        c.shipping_version = service_version
                    if code == 'ODRSTAT':
                        c.order_url = row['URL']
                        c.order_wsdl = good_url
                        c.order_version = service_version
                    if code == 'Product':
                        c.produc_url = row['URL']
                        c.produc_wsdl = good_url
                        c.produc_version = service_version
                    if code == 'PPC':
                        c.price_url = row['URL']
                        c.price_wsdl = good_url
                        c.price_version = service_version
                    if code == 'PO':
                        c.po_url = row['URL']
                        c.po_wsdl = good_url
                        c.po_version = service_version

            #save working url endpoints into db
            if has_url:
                try:
                    if addC:
                        db.session.add(c)
                    db.session.commit()
                except Exception as e:
                    logging.error("Error {0}".format(getattr(e, 'message', repr(e))))
                    continue
        return str(companies)

    @expose('/updatePasswords/')
    @has_access
    def updatePasswords(self):
        "get passwords from previous data so you don't have to migrate them manually"
        #set up a connection to your database that has passwords
        conn = MySQLdb.connect(
            host='{}'.format(app.config['OLD_DB_HOST']),
            port=int(app.config['OLD_DB_PORT']),
            user='{}'.format(app.config['OLD_DB_AUTH']),
            passwd='{}'.format(app.config['OLD_DB_PASS']),
            db='{}'.format(app.config['OLD_DATABASE'])
            )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT {},{},{},{} FROM {} WHERE {} IS NOT NULL".format(
                app.config['ERP_ID'],
                app.config['PS_USER'],
                app.config['PS_PSSWD'],
                app.config['PS_CODE'],
                app.config['PS_TABLE'],
                app.config['PS_USER']
                )
            )
        data = cursor.fetchall()
        count = 0
        for row in data:
            # (erp_id,user_name,password, ps_id)
            c = db.session.query(Company).filter_by(ps_id ='{}'.format(row[3])).first()
            if c:
                c.erp_id = row[0]
                c.user_name = row[1]
                c.password = row[2]
                db.session.commit()
                count += 1
        return 'Updated {} companies'.format(count)


    def tryUrl(self, URL, wsdl_url, code, version):
        """ verify that we can get a valid wsdl to use """
        # set schema doctor to fix missing schemas
        d = getDoctor(code, version)
        if not d: return
        try:
            # FIRST -- try the provided url
            client = Client(URL, doctor=d)
            print(client.__str__())
            if 'Methods' not in client.__str__():
                # need to try this on first call, self loops have this as False and will return empty
                if wsdl_url == False:
                    return
                else:
                    # SECOND -- add ?wsdl to provided url
                    url_with_wsdl = URL + '?wsdl'
                    URL = self.tryUrl(url_with_wsdl, False, code, version)
                    if URL:
                        return URL
                    else:
                        # FINALLY -- try the wsdl url provided using the scheme and domain in the regular url
                        URL = self.tryUrl(wsdl_url, False, code, version)
                        if URL:
                            return URL
                        else:
                            return
        except:
            if wsdl_url != False:
                url_with_wsdl = URL + '?wsdl'
                URL = False
                try:
                    URL = self.tryUrl(url_with_wsdl, False, code, version)
                    if not URL:
                        try:
                            URL = self.tryUrl(wsdl_url, False, code, version)
                        except:
                            return
                except:
                    try:
                        URL = self.tryUrl(wsdl_url, False, code, version)
                    except:
                        return
        return URL





appbuilder.add_view( Utilities, "Update Company Urls", icon="fa-link",href='/utilities/updateCompanies/', category='Utilities',category_icon="fa-cubes")
try:
    if app.config['PS_USER']:
        logging.info('PS_USER: {}'.format(app.config['PS_USER']))
        appbuilder.add_link("Update Passwords", icon='fa-exclamation-triangle', href='/utilities/updatePasswords/', category='Utilities')
except:
    pass  #fails if db connection is not set to bring in passwords from existing db


"""
    Application wide 404 error handler
"""
@appbuilder.app.errorhandler(404)
def page_not_found(e):
    return (
        render_template(
            "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
        ),
        404,
    )

db.create_all()
