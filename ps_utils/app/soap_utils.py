"""
    utilities for processing soap requests
"""
import os, logging
from suds.xsd.doctor import Import, ImportDoctor
from suds.plugin import DocumentPlugin, MessagePlugin
from flask import request

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

def getDoctor( code, version, url=False):
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
        service =  'PO'
    if code == 'INVC':
        service =  'Invoice'
    if url:
        return 'file:///{}/app/static/wsdl/{}/{}/{}.wsdl'.format(os.getenv('SERVER_PATH'), service,version,service)
    imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
    imp.filter.add(request.url_root + '/static/wsdl/{}/{}/'.format(service, version))
    d = ImportDoctor(imp)
    return d

def fixShippingWSDL():
    # path = request.url_root + '/static/wsdl/'
    imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
    imp.filter.add('xmlns:ns1','http://www.promostandards.org/WSDL/OrderStatusService/1.0.0/')
        # ,path + 'OrderStatusService/1.0.0/' )
    imp.filter.add('xmlns:ns2',' http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/')
        # ,path + 'OrderShipmentNotificationService/1.0.0' )
    imp.filter.add('xmlns:ns3','http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/SharedObjects/')
        # ,path + 'OrderShipmentNotificationService/1.0.0/SharedObjects.xsd' )
    d = ImportDoctor(imp)
    return d

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

class RawXML():
    """used to create the xml sent to the service"""
    def __init__(self, **kw):
        xml_version = '<?xml version="1.0" encoding="UTF-8"?>'+"\n"
        envelope = \
        """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
        """
        for ns in kw['namespaces']:
            for k,v in ns.items():
                envelope += ' xmlns:{}="{}"'.format(k,v) + "\n"
        envelope += '>'
        body = "<soapenv:Header/>\n<soapenv:Body>\n"
        for ns,service in kw['body'].items():
            body += '<{}:{}>'.format(ns,service)
        for field in kw['fields']:
            ns,name,value = field
            body += '<{}:{}>{}</{}:{}>'.format(ns,name,value,ns,name)
        for ns,service in kw['body'].items():
            body += '</{}:{}>'.format(ns,service)
        body += "\n</soapenv:Body>\n</soapenv:Envelope>"
        logging.info("newbody: " + body)
        self.msg = str.encode('{}{}{}'.format(xml_version, envelope, body))

    def xml(self):
        return self.msg
