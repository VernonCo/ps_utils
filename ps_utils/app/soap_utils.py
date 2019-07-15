"""
    utilities for processing soap requests
"""
import os, logging, requests, re
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from suds.plugin import DocumentPlugin, MessagePlugin
from flask import request
from urllib.parse import urlparse
from xmljson import parker
from defusedxml.cElementTree import fromstring
from json import dumps
from . import app
from .models import Company
from . import db



PRODUCTION = app.config.get('PRODUCTION')


def getDoctor( code, version, url=False):
    """ return service type for code """
        # set schema doctor to fix missing schemas
    if code == 'INV':
        service =  'InventoryService'
    if code == 'MED':
        service =  'MediaService'
    if code == 'OSN':
        service =  'OrderShipmentNotificationService'
    if code == 'ORDSTAT':
        service =  'OrderStatusService'
    if code == 'Product':
        service =  'ProductDataService'
    if code == 'PPC':
        service =  'PricingAndConfiguration'
    if code == 'PO':
        service =  'POService'
    if code == 'INVC':
        service =  'Invoice'
    if url:
        return 'file:///{}/app/static/wsdl/{}/{}/{}.wsdl'.format(
            os.getenv('SERVER_PATH'), service, version, service)
    imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
    imp.filter.add(request.url_root + '/static/wsdl/{}/{}/'.format(service, version))
    d = ImportDoctor(imp)
    return d

def tryUrl(URL, wsdl_url, code, version):
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

def basic_sobject_to_dict( obj):
    """Converts suds object to dict very quickly.
    Does not serialize date time or normalize key case.
    :return: dict object
    """
    if not hasattr(obj, '__keylist__'):
        return obj
    transposed = {}
    fields = obj.__keylist__
    for field in fields:
        val = getattr(obj, field)
        if isinstance(val, list):
            transposed[field] = []
            for item in val:
                transposed[field].append(basic_sobject_to_dict(item))
        else:
            transposed[field] = basic_sobject_to_dict(val)
    return transposed

class SoapRequest():
    """
        use requests to send soap request
        use
        import requests
        url="http://wsf.cdyne.com/WeatherWS/Weather.asmx?WSDL"
        #headers = {'content-type': 'application/soap+xml'}
        #headers = {'content-type': 'text/xml'}
        headers = {"Host": "http://SOME_URL",
            "Content-Type": "application/soap+xml; charset=UTF-8",
            "Content-Length": str(len(encoded_request)),
            "SOAPAction": "http://SOME_OTHER_URL"}
        request = '''<?xml version="1.0" encoding="UTF-8"?>
                <SOAP-ENV:Envelope xmlns:ns0="http://ws.cdyne.com/WeatherWS/" xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
                    <SOAP-ENV:Header/>
                    <ns1:Body><ns0:GetWeatherInformation/></ns1:Body>
                </SOAP-ENV:Envelope>'''.format(some params)
        encoded_request = request.encode('utf-8')
        response = requests.post(url,data=encoded_request,headers=headers)
        print response.content
    """
    def __init__(self, serviceUrl=False, serviceMethod=False, serviceResponse=False, values=False):
        if not serviceUrl or not serviceMethod or not serviceResponse or not values:
            raise Exception('Missing parameters')
        self.url = serviceUrl
        self.serviceMethod = serviceMethod
        self.serviceResponse = serviceResponse
        self.values = values
        self.XML = ''
        self.lastRequest = ''
        self.response = ''
        self.data = False
        self.error_msg = ''

    def createValues(self):
        """used by individual services to create dict for create XML"""
        pass

    def createXML(self):
        """ create the xml for the request and save as self.lastRequest"""
        xml_version = ''  #<?xml version="1.0" encoding="UTF-8"?>
        envelope = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '

        for k,v in self.values['namespaces'].items():
            envelope += ' xmlns:{}="{}"'.format(k,v)
        envelope += '>'
        body = '<soapenv:Header/><soapenv:Body>'
        for ns,service in self.values['method'].items():
            body += '<{}:{}>'.format(ns,service)
            self.serviceRequest = service
        for field in self.values['fields']:
            ns,name,value = field
            body += '<{}:{}>{}</{}:{}>'.format(ns,name,value,ns,name) #'<{} xmlns="{}">{}</{}>'.format(name,kw['namespaces'][ns],value,name)
        for ns,service in self.values['method'].items():
            body += '</{}:{}>'.format(ns,service)
        body += "</soapenv:Body></soapenv:Envelope>"
        logging.info("newbody: " + body)
        self.XML = '{}{}{}'.format(xml_version, envelope, body)

    def getServiceRequest(self, obj):
        if not hasattr(obj, 'items'):
            raise Exception( 'Bad object' )
        for k,v in obj.items():
            if k == self.serviceResponse:
                return v
            return self.getServiceRequest(v)
        raise Exception( self.serviceResponse + ' Not Found' )

    def pretty_print_POST(self, req):
        """
        At this point it is completely built and ready
        to be fired; it is "prepared".

        However pay attention at the formatting used in
        this function because it is programmed to be pretty
        printed and may differ from the actual request.
        """
        r = '{}\n{}\n{}\n\n{}'.format(
            '-----------START-----------',
            req.method + ' ' + req.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
            req.body,
            )
        self.lastRequest = r

    def removeNamespacesFromKeys(self,obj):
        """Converts Parker object to dict with namespace removed from key.
        Does not serialize date time or normalize key case.
        :return: dict object
        """
        if not hasattr(obj, 'keys'):
            return obj
        transposed = {}
        fields = obj.keys()
        for field in fields:
            val = obj[field]
            tempField = re.sub(r'\{.*\}',r'', field)
            if isinstance(val, list):
                transposed[tempField] = []
                for item in val:
                    transposed[tempField].append(self.removeNamespacesFromKeys(item))
            else:
                transposed[tempField] = self.removeNamespacesFromKeys(val)
        return transposed

    def responseToData(self):
        """get the dict from the envelope.body.serviceResponse"""

        # using defusedxml's fromstring to prevent xml vulnerabilities
        tempParker = parker.data(fromstring(self.response.text), preserve_root=True)
        temp = self.removeNamespacesFromKeys(tempParker)
        self.data = self.getServiceRequest(temp)

    def sendRequest(self):
        """
            send the request
            set error messages as self.error_msg
            set response as self.response
            if not error: set data= response to dict
        """
        self.createXML()
        parsed_uri = urlparse(self.url)
        headers = {"Host": parsed_uri.netloc, 'User-Agent': 'python-requests/2.21.0',
            #"Content-Type": "application/soap+xml; charset=UTF-8",
            "Content-Type": "text/xml; charset=utf-8",
            "Content-Length": str(len(self.XML)),
            "SOAPAction": '"{}"'.format(self.serviceMethod)}
        encoded_request = self.XML.encode('utf-8')
        r = requests.Request('POST',self.url,data=encoded_request,headers=headers)
        prepared = r.prepare()
        # save request as lastRequest
        self.pretty_print_POST(prepared)
        s = requests.Session()
        self.response = s.send(prepared)
        try:
            self.response.raise_for_status()
        except Exception as e:
            self.data = {'SoapFault': str(e)}
            return False
        self.responseToData()
        return self.data


class SoapClient():
    """Client to process soap requests"""
    def __init__(self, serviceMethod='', serviceUrl='', serviceWSDL='', serviceCode='',
                 serviceVersion='1.0.0', filters=None, values=None, **kw):
        self.serviceMethod = serviceMethod #
        self.serviceUrl = serviceUrl  # service url
        self.serviceWSDL = serviceWSDL  #url for remote wsdl
        self.serviceCode = serviceCode  # ie INV, OSN, ORDSTAT, etc.
        self.serviceVersion = serviceVersion   #ie. 1.0.0, 1.2.1, etc.
        self.filters = filters
        self.KW = kw
        self.XML = False
        self.callIndex = 0  # used to check which call succeeded / failed
        # get local wsdl file
        local_wsdl = getDoctor(self.serviceCode, self.serviceVersion, url=True)
        # set schema doctor to fix missing schemas
        d = getDoctor(self.serviceCode, self.serviceVersion)
        self.callArray = [
            {'msg':'SoapFault: Error(1) on local wsdl and location {}: '.format(self.serviceUrl),
                'wsdl':local_wsdl, 'location':self.serviceUrl, 'doctor':d},
            {'msg':'SoapFault: Error(2) on remote wsdl {}: '.format(self.serviceWSDL),
                'wsdl':self.serviceWSDL, 'location':False, 'doctor':d},
            {'msg':'SoapFault: Error(3) on remote location {}: '.format(self.serviceUrl),
                'wsdl':self.serviceUrl, 'location':False, 'doctor':d},
        ]
        if values:
            self.values = values
            self.rawXML()
            self.callArray.insert(0,{'msg':'SoapFault: Error(1b) on  injected xml and location {}: '.format(self.serviceUrl),
                'wsdl':local_wsdl, 'location':self.serviceUrl})
        self.error_msg = {'SoapFault':'No Response Available'}

    def basic_sobject_to_dict(self, obj):
        """Converts suds object to dict very quickly.
        Does not serialize date time or normalize key case.
        :return: dict object
        """
        if not hasattr(obj, '__keylist__'):
            return obj
        transposed = {}
        fields = obj.__keylist__
        for field in fields:
            val = getattr(obj, field)
            if isinstance(val, list):
                transposed[field] = []
                for item in val:
                    transposed[field].append(self.basic_sobject_to_dict(item))
            else:
                transposed[field] = self.basic_sobject_to_dict(val)
        return transposed

    def call(self):
        """
            make the service call using the index on the self.callArray
        """
        response = {'SoapFault':'Unable to get Response'}
        # index== 0: get the local wsdl and inject the endpoint
        # ...should almost always work if they follow the wsdl and give a valid endpoint to PS
        args = self.callArray[self.callIndex]
        self.callIndex += 1
        try:
            if args['location']:
                client = Client(args['wsdl'], location=args['location'])
            else:
                client = Client(args['wsdl'])
            # call the method
            func = getattr(client.service, self.serviceMethod)
            if self.XML and self.callIndex == 1:
                # used for suppliers that reject the suds-py3 parsing of the wsdl. Tried on the first call
                self.data = func(__inject={'msg':self.XML})
            else:
                kw = self.KW
                # must create filters after each client created to use that client's factory for services using filters
                kw = self.check4Filters(client, **kw)
                self.data = func(**kw)
            # check for error that could be caused by improper wsdl parsing so that it will try the next
            # call. Will raise exception to go on to next
            self.check4Error(response)
            self.error_msg['SoapFault'] = False
            del client
        except Exception as e:
            response = {'SoapFault': args['msg'] +str(e)}
            # assert False
            if self.callIndex == 1:
                self.setErrorMsg(args['msg'],e)
            else:  # does not need to try with doctor on injected correct xml
                #try with schema doctor
                try:
                    if args['location']:
                        client = Client(args['wsdl'], location=args['location'], plugins=[args['doctor']])
                    else:
                        client = Client(args['wsdl'], plugins=[args['doctor']])
                    func = getattr(client.service, self.serviceMethod)
                    self.data = func(**self.KW)
                    self.check4Error(response)
                    self.error_msg['SoapFault'] = False
                    del client
                except Exception as e:
                   self.setErrorMsg(args['msg'],e)
        # assert False
        if not hasattr(self, 'data'):
            self.data = self.error_msg
        return self.data

    def check4Error(self, response):
        """
            check for error that could be caused by improper wsdl parsing so that it will try the next
            possible call.  Have to check both ServiceMessage and ErrorMessage for different services
        """
        if 'ServiceMessageArray' in response and 'ServiceMessage' in response['ServiceMessageArray'] \
            and response['ServiceMessageArray']['ServiceMessage'][0] \
                and response['ServiceMessageArray']['ServiceMessage'][0]['code'] in [115,120,125]:
            raise Exception('Service Error: ' + response['ServiceMessageArray']['ServiceMessage'][0]['description'])

        if 'ErrorMessageArray' in response and 'ErrorMessage' in response['ErrorMessageArray'] \
            and response['ErrorMessageArray']['ErrorMessage'][0] \
                and response['ErrorMessageArray']['ErrorMessage'][0]['code'] in [115,120,125]:
            raise Exception('Service Error: ' + response['ErrorMessageArray']['ErrorMessage'][0]['description'])

    def check4Filters(self, client, **kw):
        """ update kw with filters as needed """
        if self.serviceCode == 'INV' and self.filters:
            if self.serviceVersion == '2.0.0':
                kw = self.check4InventoryFiltersV2(client, kw)
            else:
                kw = self.check4InventoryFiltersV1(client, kw)
        return kw

    def check4InventoryFiltersV1(self, client, kw):
        """ check for filters to set on soap call on version 1.0.0 and 1.2.1"""
        if 'color' in self.filters:
            filterColorArray = client.factory.create('FilterColorArray')
            filterColorArray.filterColor = self.filters['color']
            kw['FilterColorArray'] = filterColorArray
        if 'size' in self.filters:
            filterSizeArray = client.factory.create('FilterSizeArray')
            filterSizeArray.filterSize = self.filters['size']
            kw['FilterSizeArray'] = filterSizeArray
        if 'misc' in self.filters:
            filterMiscArray = client.factory.create('FilterSelectionArray')
            filterMiscArray.filterSelection = self.filters['misc']
            kw['FilterSelectionArray'] = filterMiscArray
        return kw

    def check4InventoryFiltersV2(self, client, kw):
        """ check for filters to set on soap call on version 1.0.0 and 1.2.1"""
        Filter = client.factory.create('ns3:Filter')
        if 'color' in self.filters:
            PartColorArray = client.factory.create('ns3:PartColorArray')
            PartColorArray.PartColor = self.filters['color']
            Filter.PartColorArray = PartColorArray
        if 'size' in self.filters:
            LabelSizeArray = client.factory.create('ns3:LabelSizeArray')
            LabelSizeArray.LabelSize = self.filters['size']
            Filter.LabelSizeArray = LabelSizeArray
        if 'misc' in self.filters:
            partIdArray = client.factory.create('ns3:partIdArray')
            partIdArray.partId = self.filters['misc']
            Filter.partIdArray = partIdArray
        kw['Filter'] = Filter
        return kw

    def createFilters(self, F):
        """cycle through to create levels for request"""

        if 'filters' in F:
            self.XML +='<{}:{}>'.format(F['ns'],F['name'])
            for row in F['filters']:
                self.createFilters(row)
            self.XML +='</{}:{}>'.format(F['ns'],F['name'])
        elif 'value' in F:
            self.XML += '<{}:{}>{}</{}:{}>'.format(F['ns'],F['name'],F['value'],F['ns'],F['name'])


    def object_to_dict(self, obj, key_to_lower=False, json_serialize=False):
        """
        Converts an object to a dict.
        :param json_serialize: If set, changes date and time types to iso string.
        :param key_to_lower: If set, changes index key name to lower case.
        :return: dict object
        """
        import datetime

        if not hasattr(obj, '__keylist__'):
            if json_serialize and isinstance(obj, (datetime.datetime, datetime.time, datetime.date)):
                return obj.isoformat()
            else:
                return obj
        transposed = {}
        fields = obj.__keylist__
        for field in fields:
            val = getattr(obj, field)
            if key_to_lower:
                field = field.lower()
            if isinstance(val, list):
                transposed[field] = []
                for item in val:
                    transposed[field].append(self.object_to_dict(item, json_serialize=json_serialize))
            else:
                transposed[field] = self.object_to_dict(val, json_serialize=json_serialize)
        return transposed

    def rawXML(self):
        """used to create the xml sent to the service"""
        self.XML = ''
        self.XML += '<?xml version="1.0" encoding="UTF-8"?>'
        self.XML += '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '

        for k,v in self.values['namespaces'].items():
            self.XML += ' xmlns:{}="{}"'.format(k,v)
        self.XML += '>'
        self.XML += '<soapenv:Header/><soapenv:Body>'
        for ns,service in self.values['method'].items():
            self.XML += '<{}:{}>'.format(ns,service)
            self.serviceRequest = service
        for field in self.values['fields']:
            ns,name,value = field
            self.XML += '<{}:{}>{}</{}:{}>'.format(ns,name,value,ns,name) #'<{} xmlns="{}">{}</{}>'.format(name,kw['namespaces'][ns],value,name)
        if self.values['Filter']:
           self.createFilters(self.values['Filter'])
        for ns,service in self.values['method'].items():
            self.XML += '</{}:{}>'.format(ns,service)
        self.XML += "</soapenv:Body></soapenv:Envelope>"
        logging.info("newbody: " + self.XML)
        return self.XML

    def sendPO(self):
        """get & process values, and send po"""
        #TODO: figure out
        return False

    def serviceCall(self, injectionCheck=False):
        """ call the order status service
            Suds-py3 struggles with a couple of services with shared objects. Some suppliers work with the
            parsed version of the wsdl.  Others require a strict interpretation and we inject it on the second
            pass using a loop on the first exception. An ugly solution unless WSDL is changed or the Suds-py3
            module is updated to be able to parse it correctly.
        """
        while self.error_msg['SoapFault'] and self.callIndex < 3:
            response = self.call()

        return response

    def setErrorMsg(self, msg, e):
        logging.error(msg + str(e))
        # set up error message to be given if all tries fail. As this one should have worked, give this error
        # if not PRODUCTION, all errors will be given
        if self.callIndex == 0 or not PRODUCTION:
            self.error_msg['SoapFault'] += msg +str(e) + " | "

    def sobject_to_dict(self, key_to_lower=False, json_serialize=False):
        """
        Converts a suds object to a dict.
        :param json_serialize: If set, changes date and time types to iso string.
        :param key_to_lower: If set, changes index key name to lower case.
        :return: dict object
        """
        return self.object_to_dict(self.data, key_to_lower=key_to_lower, json_serialize=json_serialize)


    def sobject_to_json(self, key_to_lower=False):
        """
        Converts a suds object to json.
        :param key_to_lower: If set, changes index key name to lower case.
        :return: json object
        """
        import json
        transposed = self.sobject_to_dict( key_to_lower=key_to_lower, json_serialize=True)
        return json.dumps(transposed)
