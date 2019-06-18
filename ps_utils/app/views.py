
import requests, json, os, re, logging
from urllib.parse import urlparse
from suds.client import Client
from zeep import Client as zClient
# logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
# logging.getLogger('suds.client').setLevel(logging.DEBUG)
from flask import render_template, flash, request, jsonify, config
from flask_babel import lazy_gettext as _
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView, ModelRestApi, SimpleFormView, BaseView, expose, has_access
from .models import Company
from .inventory import Inventory
from .order_status import OrderStatus
from .shipping_status import ShippingStatus
from .soap_utils import  getDoctor
from . import appbuilder, db
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


appbuilder.add_view(
    Inventory,
    "INV Request",
    href='/inventory/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
) #  label=_("Inventory Request Form"),

appbuilder.add_view(
    Inventory,
    "Get Inventory Version",
    href='/inventory/getVersion/'
)

appbuilder.add_view(
    OrderStatus,
    "Order Status Request",
    href='/orderstatus/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
)

appbuilder.add_view(
    ShippingStatus,
    "Shipment Status Request",
    href='/shippingstatus/index/',
    icon="fa-search",
    category='Forms',
    category_icon='fa-wpforms'
)
class Companies(ModelView):
    datamodel = SQLAInterface(Company)
    list_columns = ['company_name', 'erp_id']

appbuilder.add_view( Companies, "List Companies", icon="fa-list", category="Companies", category_icon='fa-database')


class Utilities(BaseView):

    default_view = 'index'

    @expose('/index/')
    def index(self):
        return "Provides Utilities to for Promo Standards"

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
                    # will overwrite each with the latest version given
                    # the endpoints service gives them in increasing order if multiple versions
                    if code == 'INV':
                        if service_version[:1] == '1':
                            c.inventory_url = row['URL']
                            c.inventory_wsdl = good_url
                            c.inventory_version = service_version
                        else:
                            c.inventory_urlV2 = row['URL']
                            c.inventory_wsdlV2 = good_url
                            c.inventory_versionV2 = service_version
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
        jsonStr = {"Companies":companies}
        return str(jsonStr), 200,  {'Content-Type':'applicaion/json'}

    @expose('/updatePasswords/')
    @has_access
    def updatePasswords(self):
        """get passwords from previous data so you don't have to migrate them manually
            set the fields used from your previous db in your config file to map to current db
        """
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
            client = Client(URL, plugins=[d])
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
