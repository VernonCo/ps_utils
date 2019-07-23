import requests, logging, re
from urllib.parse import urlparse
from flask_appbuilder import BaseView, expose, has_access
from .models import Company
from . import db
from .soap_utils import tryUrl
from . import app
# only needed if importing passwords from previous db
import MySQLdb

PRODUCTION = app.config.get('PRODUCTION')

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
            except Exception as e:
                print(e)
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
                good_url = tryUrl(row['URL'].strip(), wsdl_url, code, service_version)
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
