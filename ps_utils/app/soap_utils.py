"""
    utilities for processing soap requests
"""
import json, logging, os, re, requests
from urllib.parse import urlparse

from defusedxml.cElementTree import fromstring
from flask import request
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from xmljson import parker

from . import PRODUCTION

def get_doctor( code, version, url=False):
    """ return service type for code """
        # set schema doctor to fix missing schemas
    if code == 'INV':
        service =  'InventoryService'
    if code == 'MED':
        service =  'MediaService'
    if code == 'OSN':
        service =  'OrderShipmentNotificationService'
    if code == 'ODRSTAT':
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

def try_url(URL, wsdl_url, code, version):
        """ verify that we can get a valid wsdl to use """
        # set schema doctor to fix missing schemas
        d = get_doctor(code, version)
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
                    URL = try_url(url_with_wsdl, False, code, version)
                    if URL:
                        return URL
                    else:
                        # FINALLY -- try the wsdl url provided using the scheme and domain in the regular url
                        URL = try_url(wsdl_url, False, code, version)
                        if URL:
                            return URL
                        else:
                            return
        except Exception as e:
            print(e)
            if wsdl_url != False:
                url_with_wsdl = URL + '?wsdl'
                URL = False
                try:
                    URL = try_url(url_with_wsdl, False, code, version)
                    if not URL:
                        try:
                            URL = try_url(wsdl_url, False, code, version)
                        except Exception as e:
                            print(e)
                            return
                except Exception as e:
                    print(e)
                    try:
                        URL = try_url(wsdl_url, False, code, version)
                    except Exception as e:
                        print(e)
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

def object_to_dict(obj, key_to_lower=False, json_serialize=False):
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
                transposed[field].append(object_to_dict(item, json_serialize=True))
        else:
            transposed[field] = object_to_dict(val, json_serialize=True)
    return transposed

def test_call(service_url, service_method, serviceResponse, values):
    """used to debug a soapcall call to a url"""
    try:
        client = SoapRequest(service_url=service_url, service_method=service_method,
                            serviceResponse=serviceResponse, values=values)
        data = client.send_request()
        print(data)
    except Exception as e:
        print(e)
        # assert False
        exit()
    # assert False    # in the debuger: use client.XML (what was sent) & client.response.text (returned response)
    print(client.XML)
    print(client.response.text)
    exit()


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
    def __init__(self, service_url=False, service_method=False, serviceResponse=False, values=False):
        if not service_url or not service_method or not serviceResponse or not values:
            raise Exception('Missing parameters')
        self.url = service_url
        self.service_method = service_method
        self.serviceResponse = serviceResponse
        self.values = values
        self.XML = ''
        self.lastRequest = ''
        self.response = ''
        self.data = False
        self.error_msg = ''

    def _create_values(self):
        """used by individual services to create dict for create XML"""
        pass

    def _create_XML(self):
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

    def _get_service_request(self, obj):
        if not hasattr(obj, 'items'):
            raise Exception( 'Bad object' )
        for k,v in obj.items():
            if k == self.serviceResponse:
                return v
            return self._get_service_request(v)
        raise Exception( self.serviceResponse + ' Not Found' )

    def _pretty_print_POST(self, req):
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

    def _remove_namespaces_from_keys(self,obj):
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
                    transposed[tempField].append(self._remove_namespaces_from_keys(item))
            else:
                transposed[tempField] = self._remove_namespaces_from_keys(val)
        return transposed

    def _response_to_data(self):
        """get the dict from the envelope.body.serviceResponse"""

        # using defusedxml's fromstring to prevent xml vulnerabilities
        tempParker = parker.data(fromstring(self.response.text), preserve_root=True)
        temp = self._remove_namespaces_from_keys(tempParker)
        self.data = self._get_service_request(temp)

    def send_request(self):
        """
            send the request
            set error messages as self.error_msg
            set response as self.response
            if not error: set data= response to dict
        """
        self._create_XML()
        parsed_uri = urlparse(self.url)
        headers = {"Host": parsed_uri.netloc, 'User-Agent': 'python-requests/2.21.0',
            #"Content-Type": "application/soap+xml; charset=UTF-8",
            "Content-Type": "text/xml; charset=utf-8",
            "Content-Length": str(len(self.XML)),
            "SOAPAction": '"{}"'.format(self.service_method)}
        encoded_request = self.XML.encode('utf-8')
        r = requests.Request('POST',self.url,data=encoded_request,headers=headers)
        prepared = r.prepare()
        # save request as lastRequest
        self._pretty_print_POST(prepared)
        s = requests.Session()
        self.response = s.send(prepared)
        try:
            self.response.raise_for_status()
        except Exception as e:
            self.data = {'SoapFault': str(e)}
            return False
        self._response_to_data()
        return self.data


class SoapClient():
    """Client to process soap requests"""
    def __init__(self, service_method='', service_url='', service_WSDL='', service_code='',
                 service_version='1.0.0', filters=None, values=None, self_cert=False, **kw):
        if self_cert:
            import ssl
            if hasattr(ssl, '_create_unverified_context'):
                ssl._create_default_https_context = ssl._create_unverified_context
        self.service_method = service_method #
        self.service_url = service_url  # service url
        self.service_WSDL = service_WSDL  #url for remote wsdl
        self.service_code = service_code  # ie INV, OSN, ORDSTAT, etc.
        self.service_version = service_version   #ie. 1.0.0, 1.2.1, etc.
        self.filters = filters
        self.KW = kw
        self.XML = False
        self.call_index = 0  # used to check which call succeeded / failed
        # following variables and conditional allows use of the client for calls outside
        # of Promostandards without the service_code
        self.callArray = []
        local_wsdl = self.service_WSDL
        if self.service_code:
            # get local wsdl file
            local_wsdl = get_doctor(self.service_code, self.service_version, url=True)
        # set schema doctor to fix missing schemas
        d = get_doctor(self.service_code, self.service_version)
        self.callArray = [
            {'msg':'SoapFault: Error(1) on local wsdl and location {}: '.format(self.service_url),
                'wsdl':local_wsdl, 'location':self.service_url, 'doctor':d},
            {'msg':'SoapFault: Error(2) on remote wsdl {}: '.format(self.service_WSDL),
                'wsdl':self.service_WSDL, 'location':False, 'doctor':d},
            {'msg':'SoapFault: Error(3) on remote location {}: '.format(self.service_url),
                'wsdl':self.service_url, 'location':False, 'doctor':d},
        ]
        self.multi_call_on_error = True
        if values:
            if not isinstance(values,bool):
                self.values = values
                self._raw_XML()
            else:
                self.multi_call_on_error = False # POService gets called once with injected xml only
            self.callArray.insert(0,{'msg':'SoapFault: Error(1b) on  injected xml and location {}: '.format(self.service_url),
                'wsdl':local_wsdl, 'location':self.service_url})
        self.error_msg = {'SoapFault':'No Response Available'}
        self.response = ''

    def _call(self):
        """
            make the service call using the index on the self.callArray
        """
        self.data = {'SoapFault':'Unable to get Response'}
        # index== 0: get the local wsdl and inject the endpoint
        # ...should almost always work if they follow the wsdl and give a valid endpoint to PS
        args = self.callArray[self.call_index]
        self.call_index += 1
        try:
            if args['location']:
                client = Client(args['wsdl'], location=args['location'])
            else:
                client = Client(args['wsdl'])
            # call the method
            func = getattr(client.service, self.service_method)
            if self.XML and self.call_index == 1:
                # used for suppliers that reject the suds-py3 parsing of the wsdl. Tried on the first call
                # the Dockerfile has a fix for suds-py, but anyone using this local instead of using the docker image
                # will still have issues unless they add following lines to 171,172 in site-packages/suds/xsd/sxbase.py
                # Meanwhile, waiting for fix pushed in suds-py3 for issue #41
                    # if self.ref and self.ref in self.schema.elements.keys():
                    #     ns = self.ref
                self.data = func(__inject={'msg':self.XML})
            else:
                kw = self.KW
                # must create filters after each client created to use that client's factory for services using filters
                kw = self._check_for_filters(client, **kw)
                self.data = func(**kw)
            # check for error that could be caused by improper wsdl parsing so that it will try the next
            # call. Will raise exception to go on to next
            self._check_for_error(self.data)
            self.error_msg['SoapFault'] = False
            self.response = str(client.last_received())
            self.last_sent = str(client.last_sent())
            logging.error("Sent: {}".format(self.last_sent))
            logging.error("Response: {}".format(self.response))
            del client
        except Exception as e:
            self.data = {'SoapFault': args['msg'] +str(e)}
            # assert False
            if self.call_index == 1:
                self._set_error_msg(args['msg'],e)
            else:  # does not need to try with doctor on injected correct xml
                #try with schema doctor
                try:
                    if args['location']:
                        client = Client(args['wsdl'], location=args['location'], plugins=[args['doctor']])
                    else:
                        client = Client(args['wsdl'], plugins=[args['doctor']])
                    func = getattr(client.service, self.service_method)
                    self.data = func(**self.KW)
                    self.response = str(client.last_received())
                    self._check_for_error(self.data)
                    self.error_msg['SoapFault'] = False
                    del client
                except Exception as e:
                    self._set_error_msg(args['msg'],e)
        # assert False
        if not self.multi_call_on_error:
            self.call_index = 3
        if not hasattr(self, 'data'):
            self.data = self.error_msg
        return self.data

    @classmethod
    def _check_for_error(self, response):
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

    def _check_for_filters(self, client, **kw):
        """ update kw with filters as needed """
        if self.service_code == 'INV' and self.filters:
            if self.service_version == '2.0.0':
                kw = self._check_for_inv_filters_v2(client, kw)
            else:
                kw = self._check_for_inv_filters_v1(client, kw)
        return kw

    def _check_for_inv_filters_v1(self, client, kw):
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

    def _check_for_inv_filters_v2(self, client, kw):
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

    def _create_filters(self, F):
        """cycle through to create levels for request"""

        if 'filters' in F:
            self.XML +='<{}:{}>'.format(F['ns'],F['name'])
            for row in F['filters']:
                self._create_filters(row)
            self.XML +='</{}:{}>'.format(F['ns'],F['name'])
        elif 'value' in F:
            self.XML += '<{}:{}>{}</{}:{}>'.format(F['ns'],F['name'],F['value'],F['ns'],F['name'])

    def _raw_XML(self):
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
           self._create_filters(self.values['Filter'])
        for ns,service in self.values['method'].items():
            self.XML += '</{}:{}>'.format(ns,service)
        self.XML += "</soapenv:Body></soapenv:Envelope>"
        logging.info("newbody: " + self.XML)
        return self.XML

    def service_call(self):
        """ call the order status service
            Suds-py3 struggles with a couple of services with shared objects. Some suppliers work with the
            parsed version of the wsdl.  Others require a strict interpretation and we inject it on the second
            pass using a loop on the first exception. An ugly solution unless WSDL is changed or the Suds-py3
            module is updated to be able to parse it correctly.
        """
        while self.error_msg['SoapFault'] and self.call_index < 3:
            response = self._call()

        return response

    def _set_error_msg(self, msg, e):
        logging.error(msg + str(e))
        # set up error message to be given if all tries fail. As this one should have worked, give this error
        # if not PRODUCTION, all errors will be given
        if self.call_index == 0 or not PRODUCTION:
            self.error_msg['SoapFault'] += msg +str(e) + " | "

    def sobject_to_dict(self, key_to_lower=False, json_serialize=False):
        """
        Converts a suds object to a dict.
        :param json_serialize: If set, changes date and time types to iso string.
        :param key_to_lower: If set, changes index key name to lower case.
        :return: dict object
        """
        return object_to_dict(self.data, key_to_lower=key_to_lower, json_serialize=True)


    def sobject_to_json(self, key_to_lower=False):
        """
        Converts a suds object to json.
        :param key_to_lower: If set, changes index key name to lower case.
        :return: json object
        """
        transposed = self.sobject_to_dict( key_to_lower=key_to_lower, json_serialize=True)
        return json.dumps(transposed)
