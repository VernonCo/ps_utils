import html, json, logging
from datetime import datetime
from decimal import Context, Decimal, Inexact

from flask import Response, request
from flask_appbuilder import SimpleFormView, expose
from flask_appbuilder.api import safe
from schema import And, Const, Optional, Regex, Schema, Use

from . import csrf, db  # , PRODUCTION
from .models import Company
from .soap_utils import SoapClient

# validation functions

# Helpers for parsing the result of isoformat()
def _parse_isoformat_date(dtstr):
    # It is assumed that this function will only be called with a
    # string of length exactly 10, and (though this is not used) ASCII-only
    year = int(dtstr[0:4])
    if dtstr[4] != '-':
        raise ValueError('Invalid date separator: %s' % dtstr[4])
    month = int(dtstr[5:7])
    if dtstr[7] != '-':
        raise ValueError('Invalid date separator')
    day = int(dtstr[8:10])
    return [year, month, day]

def _parse_hh_mm_ss_ff(tstr):
    # Parses things of the form HH[:MM[:SS[.fff[fff]]]]
    len_str = len(tstr)
    time_comps = [0, 0, 0, 0]
    pos = 0
    for comp in range(0, 3):
        if (len_str - pos) < 2:
            raise ValueError('Incomplete time component')
        time_comps[comp] = int(tstr[pos:pos+2])
        pos += 2
        next_char = tstr[pos:pos+1]
        if not next_char or comp >= 2:
            break
        if next_char != ':':
            raise ValueError('Invalid time separator: %c' % next_char)
        pos += 1
    if pos < len_str:
        if tstr[pos] != '.':
            raise ValueError('Invalid microsecond component')
        else:
            pos += 1
            len_remainder = len_str - pos
            if len_remainder not in (3, 6):
                raise ValueError('Invalid microsecond component')
            time_comps[3] = int(tstr[pos:])
            if len_remainder == 3:
                time_comps[3] *= 1000
    return time_comps

def _parse_isoformat_time(tstr):
    # Format supported is HH[:MM[:SS[.fff[fff]]]][+HH:MM[:SS[.ffffff]]]
    len_str = len(tstr)
    if len_str < 2:
        raise ValueError('Isoformat time too short')
    # This is equivalent to re.search('[+-]', tstr), but faster
    tz_pos = (tstr.find('-') + 1 or tstr.find('+') + 1)
    timestr = tstr[:tz_pos-1] if tz_pos > 0 else tstr
    time_comps = _parse_hh_mm_ss_ff(timestr)
    tzi = None
    if tz_pos > 0:
        tzstr = tstr[tz_pos:]
        # Valid time zone strings are:
        # HH:MM               len: 5
        # HH:MM:SS            len: 8
        # HH:MM:SS.ffffff     len: 15
        if len(tzstr) not in (5, 8, 15):
            raise ValueError('Malformed time zone string')
        tz_comps = _parse_hh_mm_ss_ff(tzstr)
        if all(x == 0 for x in tz_comps):
            tzi = timezone.utc
        else:
            tzsign = -1 if tstr[tz_pos - 1] == '-' else 1
            td = timedelta(hours=tz_comps[0], minutes=tz_comps[1],
                           seconds=tz_comps[2], microseconds=tz_comps[3])
            tzi = timezone(tzsign * td)
    time_comps.append(tzi)
    return time_comps

def fromisoformat(date_string):
        """
            validate a datetime from the code used in datetime.isoformat().
            added in python 3.7, but pypy3 does not yet have it

        """
        if not isinstance(date_string, str):
            raise TypeError('fromisoformat: argument must be str')

        # Split this at the separator
        dstr = date_string[0:10]
        tstr = date_string[11:]

        try:
            date_components = _parse_isoformat_date(dstr)
        except ValueError:
            raise ValueError(f'Invalid isoformat string: {date_string!r}')

        if tstr:
            try:
                time_components = _parse_isoformat_time(tstr)
            except ValueError:
                raise ValueError(f'Invalid isoformat string: {date_string!r}')
        else:
            time_components = [0, 0, 0, 0, None]
        return date_string

def to_decimal_4(d):
    """verifies that it is a decimal"""
    x = "{:.4f}".format(Decimal(d))
    return Decimal(x)

def xml_bool(v):
    """verifies that it is a xml standard boolean"""
    v = str(v)
    if v in ['1', '0', 'false', 'true']:
        return v
    return False

def validDecimal_12_4(d):
    """validate that d is dec(12,4)"""
    FOURPLACES = Decimal(10)**-4
    d.quantize(FOURPLACES, context=Context(traps=[Inexact]))
    if d < Decimal("1000000000000"):
        return True

def var_check(v, l):
    """
    verifies v is str and len(v) <= l
    """
    if isinstance(v, str) and len(v) <= l:
        return v
    return False


class JsonPO(SimpleFormView):
    """
        Receives a json post with the PO info.
        Requires companyID to get url, username, password, and version
        {companyId: int, PO:{...}}
        Other requirements: check https://promostandards.org/service/view/15/
        Returns a status and json response after validating and submitting a sendPO.
    """
    default_view = 'index'

    def createXML(self):
        """parse through the po dict and create the xml to be injected into the request"""
        header = '<?xml version=\"1.0\" encoding=\"UTF-8\"?><SOAP-ENV:Envelope xmlns:SOAP-ENV=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:ns1=\"http://www.promostandards.org/WSDL/PO/1.0.0/\" xmlns:ns2=\"http://www.promostandards.org/WSDL/PO/1.0.0/SharedObjects/\"><SOAP-ENV:Header/>'


    # Make sure this is only accessible by apps you want as it is open
    # or add authentication protection
    # send POST header 'Content-Type: applicaion/json'
    @expose('/index/', methods=['POST'])
    @csrf.exempt
    @safe
    def index(self, **kw):
        """process json request received"""
        req_json = request.get_json()
        return self.processPO(req_json)

    @expose('/instructions/', methods=['GET'])
    def instructions(self):
        """ diplay instructions for sending jsonPO"""
        return self.render_template('purchaseOrder/instructions.html')

    @classmethod
    def processPO(self, req_json):
        companyID = req_json.pop('companyID', None)
        if not companyID or not isinstance(companyID, int):
            error = dict(ServiceMessageArray=[
                dict(
                    Code=120,
                    Description="The following field(s) are required: companyID"
                )
            ])
            data = json.dumps(error)
            return data, 400, {'Content-Type': 'application/json'}
        c = db.session.query(Company).get(companyID)
        if not c:
            error = dict(ServiceMessageArray=[
                dict(Code=100, Description="ID (companyID) not found")
            ])
            data = json.dumps(error)
            return data, 500, {'Content-Type': 'application/json'}
        kw = {
            "wsVersion": c.po_version,
            "id": c.user_name,
            "password": c.password,
            "PO": req_json['PO']
        }
        try:
            self.validatePO(**kw)
        except Exception as e:
            error = {
                "ServiceMessageArray": [{
                    "ServiceMessage": {
                        "code": 999,
                        "description": str(e),
                        "severity": "Error"
                    }
                }]
            }
            data = json.dumps(error)
            return data, 400, {'Content-Type': 'application/json'}
        data, htmlCode = self.sendPO(c, **kw)
        return data, htmlCode, {'Content-Type': 'application/json'}

    @classmethod
    def sendPO(self, company, **kw):
        """send the request.  Can be used by index or a plugin"""
        htmlCode = 200
        # TODO: add test links to the model and use 'if not PRODUCTION:' to switch to test
        client = SoapClient(serviceMethod='sendPO',
                            serviceUrl=company.po_url,
                            serviceWSDL=company.po_wsdl,
                            serviceCode='PO',
                            serviceVersion=company.po_version,
                            filters=False,
                            values=False,
                            **kw)
        client.serviceCall()
        if client.data == 'Unable to get Response' or 'SoapFault' in client.data:
            htmlCode = 500
        # response = client.response
        result = client.sobject_to_dict()
        # sudsy-py3 not parsing response correctly for ServiceMessageArray
        try:
            if result['ServiceMessageArray']['ServiceMessage'][0]['code']:
                temp = result['ServiceMessageArray']
                ServiceMessageArray = [{"ServiceMessage":temp['ServiceMessage'][0]}]
                result['ServiceMessageArray'] = ServiceMessageArray
        except Exception as e:
            print(str(e))
        return [json.dumps(result), htmlCode]

    @expose('/test/', methods=['GET'])
    def test(self):
        """
            test the service using exampleSimplePO.json
            1) Create a "TEST" company which hits hits the receiveTest (http://localhost/jsonpo/receiveTest/)
            and returns the xml that was sent
            OR
            2) Change companyID in the exampleSimplePO.json and set that company's PO url to their
            test link to pass it to the company.
            *** MAKE SURE to SET the test link for the company in the DB so
            that it doesn't hit the production with this test! ***
            PS_utils currently doesn't pull separate fields for test urls into the db
        """
        with open('exampleSimplePO.json') as json_file:
            req_json = json.load(json_file)
        if req_json['companyID'] == 0:
            c = db.session.query(Company).filter(Company.company_name=='TEST').first()
            if not c:
                data = '{"Error": "Missing a TEST company"}'
                return data, 500, {'Content-Type': 'application/json'}
            req_json['companyID'] = c.id
        return self.processPO(req_json)

    @expose('/receiveTest/', methods=['GET', 'POST'])
    @csrf.exempt
    def receiveTest(self):
        """return the xml received in the ServiceMessage.description"""
        sent = html.escape("Sent: ({})".format(request.data))
        logging.error(sent)
        data = u'<?xml version="1.0" encoding="UTF-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><SendPOResponse xmlns="http://www.promostandards.org/WSDL/PO/1.0.0/"><ServiceMessageArray><ServiceMessage><code>999</code><description>'
        data = data + sent
        data = data + u'</description><severity>Info</severity></ServiceMessage></ServiceMessageArray></SendPOResponse></s:Body></s:Envelope>'
        r = Response(response=data.strip(),
                     status=200,
                     mimetype="application/xml")
        r.headers["Content-Type"] = "text/xml; charset=utf-8"
        return r

    @classmethod
    def validatePO(self, **kw):
        """
        validate required fields are present and validate types
        uses schema to validate and return validated kw
        """
        # following vars are used for validation
        #ISO-8601 format for date and datetime.
        rdatetime = r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(([+-]\d\d:\d\d)|Z)?$'
        toleranceList = ('AllowOverRun', 'AllowUnderrun',
                         'AllowOverrunOrUnderrun', 'ExactOnly')
        uomList = [
            'BX', 'CA', 'DZ', 'EA', 'KT', 'PR', 'PK', 'RL', 'ST', 'SL', 'TH'
        ]

        conact_schema = Schema({
            Optional("attentionTo"):
                And(lambda s: var_check(s, 35),
                    error='"attentionTo" should evaluate to varchar(35)'),
            Optional("companyName"):
                And(lambda s: var_check(s, 35),
                    error='"companyName" should evaluate to varchar(35)'),
            Optional("address1"):
                And(lambda s: var_check(s, 35),
                    error='"address1" should evaluate to varchar(35)'),
            Optional("address2"):
                And(lambda s: var_check(s, 35),
                    error='"address2" should evaluate to varchar(35)'),
            Optional("address3"):
                And(lambda s: var_check(s, 35),
                    error='"address3" should evaluate to varchar(35)'),
            Optional("city"):
                And(lambda s: var_check(s, 30),
                    error='"city" should evaluate to varchar(30)'),
            Optional("region"):
                And(lambda s: var_check(s, 3),
                    error='"region" should evaluate to varchar(3)'),
            Optional("postalCode"):
                And(lambda s: var_check(s, 10),
                    error='"postalCode" should evaluate to varchar(10)'),
            Optional("country"):
                And(lambda s: var_check(s, 2),
                    error='"country" should evaluate to varchar(2)'),
            Optional("email"):
                And(lambda s: var_check(s, 128),
                    error='"email" should evaluate to varchar(128)'),
            Optional("phone"):
                And(lambda s: var_check(s, 32),
                    error='"phone" should evaluate to varchar(32)'),
            Optional("comments"): str
        })

        quantity_schema = Schema({
            "uom": And(str, lambda s: s in uomList),
            "value": And(Use(to_decimal_4), validDecimal_12_4)
        })
        thirdParty_schema = Schema({
            "accountName":
                And(lambda s: var_check(s, 64),
                    error='"accountName" should evaluate to varchar(64)'),
            "accountNumber":
                And(lambda s: var_check(s, 64),
                    error='"accountNumber" should evaluate to varchar(64)'),
            "ContactDetails": conact_schema
        })
        # schema used for validating PO version 1.0.0
        v1_0_0_schema = Schema({
            "wsVersion": And(str, len),
            "id": And(str, len),
            Optional("password"): str,
            "PO": {
                "orderType":
                    And(str, lambda s: s in ('Blank', 'Sample', 'Simple', 'Configured')),
                "orderNumber":
                    And(lambda s: var_check(s, 64),
                        error='"orderNumber" should evaluate to varchar(64)'),
                "orderDate":
                    And(Const(Use(fromisoformat)),
                        Regex(r'{}'.format(rdatetime))),
                Optional("lastModified"):
                    And(Const(Use(fromisoformat)),
                        Regex(r'{}'.format(rdatetime))),
                "totalAmount": And(Use(to_decimal_4), validDecimal_12_4),
                Optional("paymentTerms"):  str,
                "rush": Use(xml_bool),
                "currency":
                    And(lambda s: var_check(s, 3),
                        error='"currency" should evaluate to varchar(3)'),
                Optional("DigitalProof"): {
                    "DigitalProofAddressArray": [{
                        "DigitalProofAddress": {
                            "type":
                                And(lambda s: var_check(s, 64),
                                    error='"type" should evaluate to varchar(64)'),
                            "email":
                                And(lambda s: var_check(s, 128),
                                    error='"email" should evaluate to varchar(128)'
                                    ),
                            "lineItemGroupingId": int
                        }
                    }],
                    "required": Use(xml_bool)
                },
                Optional("OrderContactArray"): [{
                    "Contact": {
                        Optional("accountName"):
                            And(lambda s: var_check(s, 64),
                                error='"accountName" should evaluate to varchar(64)'),
                        Optional("accountNumber"):
                            And(lambda s: var_check(s, 64),
                                error='"accountNumber" should evaluate to varchar(64)'),
                        "contactType":
                            And(str, lambda s: s in [
                                    'Art', 'Bill', 'Expeditor', 'Order', 'Sales',
                                    'Ship', 'Sold'
                                ]),
                        "ContactDetails": conact_schema
                    }
                }],
                "ShipmentArray": [{
                    "Shipment": {
                        Optional("shipReferences"):
                            [lambda s: var_check(s, 64)],
                        Optional("comments"): str,
                        Optional("ThirdPartyAccount"): thirdParty_schema,
                        "allowConsolidation": Use(xml_bool),
                        "blindShip": Use(xml_bool),
                        "packingListRequired": Use(xml_bool),
                        "FreightDetails": {
                            "carrier":
                            And(lambda s: var_check(s, 64),
                                error='"carrier" should evaluate to varchar(64)'
                                ),
                            "service":
                            And(lambda s: var_check(s, 64),
                                error='"service" should evaluate to varchar(64)'
                                )
                        },
                        "ShipTo": {
                            "customerPickup": Use(xml_bool),
                            "ContactDetails": conact_schema,
                            "shipmentId": int
                        }
                    }
                }],
                "LineItemArray": [{
                    "LineItem": {
                        "lineNumber": int,
                        Optional("lineReferenceId"):
                            And(lambda s: var_check(s, 64),
                                error='"lineReferenceId" should evaluate to varchar(64)'),
                        "description": str,
                        "lineType": And(str, lambda s: s in ['New', 'Repeat', 'Reference']),
                        Optional("Quantity"): quantity_schema,
                        Optional("fobid"):
                            And(lambda s: var_check(s, 64),
                                error='"fobid" should evaluate to varchar(64)'),
                        "ToleranceDetails": {
                            Optional('uom'): And(str, lambda s: s in uomList),
                            Optional("value"): And(Use(to_decimal_4), validDecimal_12_4),
                            "tolerance": And(str, lambda s: s in toleranceList)
                        },
                        "allowPartialShipments": Use(xml_bool),
                        Optional("unitPrice"): And(Use(to_decimal_4), validDecimal_12_4),
                        "lineItemTotal": And(Use(to_decimal_4), validDecimal_12_4),
                        Optional("requestedShipDate"):
                            And(Const(Use(fromisoformat)),
                                Regex(r'{}'.format(rdatetime))),
                        Optional("requestedInHands"):
                            And(Const(Use(fromisoformat)),
                                Regex(r'{}'.format(rdatetime))),
                        Optional("referenceSalesQuote"):
                            And(lambda s: var_check(s, 64),
                                error='"referenceSalesQuote" should evaluate to varchar(64)'),
                        Optional("Program"): {
                            Optional("id"):
                                And(lambda s: var_check(s, 64),
                                    error='"id" should evaluate to varchar(64)'),
                            Optional("name"):
                                And(lambda s: var_check(s, 64),
                                    error='"name" should evaluate to varchar(64)')
                        },
                        Optional("endCustomerSalesOrder"):
                            And(lambda s: var_check(s, 64),
                                error= '"endCustomerSalesOrder" should evaluate to varchar(64)'),
                        Optional("productId"):
                            And(lambda s: var_check(s, 64),
                                error='"productId" should evaluate to varchar(64)'),
                        Optional("customerProductId"):
                            And(lambda s: var_check(s, 64),
                                error='"customerProductId" should evaluate to varchar(64)'),
                        Optional("lineItemGroupingId"): int,
                        Optional("PartArray"): [{
                            "Part": {
                                Optional("partGroup"):
                                    And(lambda s: var_check(s, 64),
                                        error='"partGroup" should evaluate to varchar(64)'),
                                "partId":
                                    And(lambda s: var_check(s, 64),
                                        error='"partId" should evaluate to varchar(64)'),
                                Optional("customerPartId"):
                                    And(lambda s: var_check(s, 64),
                                        error='"customerPartId" should evaluate to varchar(64)'),
                                "customerSupplied": Use(xml_bool),
                                Optional("description"): str,
                                "Quantity": quantity_schema,
                                Optional("locationLinkId"): [int],
                                Optional("unitPrice"): And(Use(to_decimal_4), validDecimal_12_4),
                                Optional("extendedPrice"): And(Use(to_decimal_4), validDecimal_12_4),
                                Optional("ShipmentLinkArray"): [{
                                    "ShipmentLink": {
                                        "Quantity": quantity_schema,
                                        "shipmentId": int
                                    }
                                }]
                            }
                        }],
                        Optional("Configuration"): {
                            Optional("ChargeArray"): [{
                                "Charge": {
                                    Optional("chargeName"):
                                        And(lambda s: var_check(s, 128),
                                            error='"chargeName" should evaluate to varchar(128)'),
                                    Optional("description"): str,
                                    Optional("extendedPrice"): And(Use(to_decimal_4), validDecimal_12_4),
                                    Optional("unitprice"): And(Use(to_decimal_4), validDecimal_12_4),
                                    "chargeId":
                                        And(lambda s: var_check(s, 64),
                                            error='"chargeId" should evaluate to varchar(64)'),
                                    Optional("chargeName"):
                                        And(lambda s: var_check(s, 128),
                                            error='"chargeName" should evaluate to varchar(128)'),
                                    "chargeType":
                                        And(str, lambda s: s in
                                            ['Freight', 'Order', 'Run', 'Setup']),
                                    "Quantity": quantity_schema
                                }
                            }],
                            Optional("LocationArray"): [{
                                "Location": {
                                    Optional("locationName"):
                                        And(lambda s: var_check(s, 128),
                                            error='"locationName" should evaluate to varchar(128)'),
                                    "DecorationArray": [{
                                        "Decoration": {
                                            Optional("decorationName"):
                                                And(lambda s: var_check(s, 128),
                                                    error='"decorationName" should evaluate to varchar(128)'),
                                            "Artwork": {
                                                Optional("instructions"): str,
                                                Optional("refArtworkId"):
                                                    And(lambda s: var_check(s, 64),
                                                        error='"refArtworkId" should evaluate to varchar(64)'),
                                                Optional("totalStitchCount"): int,
                                                Optional("ArtworkFileArray"): [{
                                                    "ArtworkFile": {
                                                        "artworkType":
                                                            And(str, lambda s: s in [
                                                                'ProductionReady', 'VirtualProof',
                                                                'SupplierArtTemplate', 'NonProductionReady'
                                                            ]),
                                                        "fileLocation":
                                                            And(lambda s: var_check(s, 1024),
                                                                error='"fileLocation" should evaluate to varchar(1024)'),
                                                        "fileName":
                                                            And(lambda s: var_check(s, 256),
                                                                error='"fileName" should evaluate to varchar(256)'),
                                                        "transportMechanism":
                                                            And(str, lambda s: s in [
                                                                'Email', 'Url', 'Ftp', 'ArtworkToFollow'
                                                            ]),
                                                    }
                                                }],
                                                Optional("description"): str,
                                                Optional("Dimensions"): {
                                                    Optional("diameter"):
                                                        And(Use(to_decimal_4),validDecimal_12_4),
                                                    Optional("height"):
                                                        And(Use(to_decimal_4),validDecimal_12_4),
                                                    Optional('uom'):
                                                        And(str, lambda s: s in uomList),
                                                    Optional("width"):
                                                        And(Use(to_decimal_4),validDecimal_12_4),
                                                    "useMaxLocationDimensions": Use(xml_bool),
                                                    "geometry":
                                                        And(str, lambda s: s in [
                                                            'Circle',
                                                            'Other',
                                                            'Rectangle'
                                                        ])
                                                },
                                                Optional("Layers"): {
                                                    "colorSystem":
                                                        And(
                                                            str, lambda s: s in [
                                                                'Cmyk', 'Other',
                                                                'Pms', 'Rgb',
                                                                'Thread'
                                                            ]),
                                                    "LayerOrStopArray": {
                                                        "color":
                                                            And(lambda s: var_check(s, 64),
                                                                error='Layer "color" should evaluate to varchar(64)'),
                                                        "nameOrNumber":
                                                            And(lambda s: var_check(s, 64),
                                                                error='"nameOrNumber" should evaluate to varchar(64)'),
                                                        "description": str
                                                    }
                                                },
                                                Optional("TypesetArray"): [{
                                                    "Typeset":{
                                                        Optional("fontSize"): Use(Decimal),
                                                        Optional("font"):
                                                            And(lambda s: var_check(s, 64),
                                                                error='"font" should evaluate to varchar(64)'),
                                                        "sequenceNumber": int,
                                                        "value":
                                                            And(lambda s: var_check(s, 1024),
                                                            error='Typset "value" should evaluate to varchar(1024)')
                                                    }
                                                }]
                                            },
                                            "decorationId": int
                                        }
                                    }],
                                    "locationLinkId": int,
                                    "locationId": int
                                }
                            }],
                            Optional("referenceNumberType"):
                                And(
                                    str, lambda s: s in [
                                        'PurchaseOrder', 'SalesOrder',
                                        'JobOrWorkOrder'
                                    ]),
                            Optional("referenceNumber"):
                                And(lambda s: var_check(s, 64),
                                    error='"referenceNumber" should evaluate to varchar(64)'),
                            "preProductionProof": Use(xml_bool),
                        }
                    }
                }],
                "termsAndConditions": str,
                Optional("salesChannel"):
                    And(lambda s: var_check(s, 64),
                        error='"salesChannel" should evaluate to varchar(64)'),
                Optional("promoCode"):
                    And(lambda s: var_check(s, 64),
                        error='"promoCode" should evaluate to varchar(64)'),
                Optional("TaxInformationArray"): [{
                    "TaxInformation": {
                        "taxJurisdiction":
                            And(lambda s: var_check(s, 64),
                                error='"taxJurisdiction" should evaluate to varchar(64)'),
                        "taxExempt": Use(xml_bool),
                        "taxId":
                            And(lambda s: var_check(s, 64),
                                error='"taxId" should evaluate to varchar(64)'),
                        "taxType":
                            And(lambda s: var_check(s, 64),
                                error='"taxType" should evaluate to varchar(64)'),
                        Optional("taxAmount"): Use(Decimal)
                    }
                }]
            }
        })

        # run the validation
        v1_0_0_schema.validate(kw)
