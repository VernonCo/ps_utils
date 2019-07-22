import json, logging, copy, re, html
from flask_appbuilder import SimpleFormView, expose, has_access
from flask_appbuilder.api import  safe
from flask import request, flash, redirect, Response
from .models import Company
from . import app, appbuilder, db, csrf
from .soap_utils import SoapClient
from jinja2 import Markup
from sqlalchemy import or_, and_
from schema import Schema, Optional, And, Or, Regex, Const, Use
from decimal import Decimal, Context, Inexact
from datetime import datetime

PRODUCTION = app.config.get('PRODUCTION')
htmlCode = 200

# validation functions
def validDecimal_12_4(d):
    """validate that d is dec(12,4)"""
    FOURPLACES = Decimal(10) ** -4
    try:
        d.quantize(FOURPLACES, context=Context(traps=[Inexact]))
        if d < Decimal("1000000000000"):
            return True
    except:
        pass
    return False

def to_decimal_4(d):
    """verifies that it is a decimal"""
    x = "{:.4f}".format(d)
    return Decimal(x)

def xml_bool(v):
    """verifies that it is a xml standard boolean"""
    v = str(v)
    if v in ['1', '0', 'false', 'true']:
        return v
    return False

def var_check(v,l):
    """
    verifies v is str and len(v) <= l
    """
    if isinstance(v,str) and len(v) <= l:
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

    # Make sure this is only accessible by apps you want as it is open
    # or add authentication protection
    # send POST header 'Content-Type: applicaion/json'
    @expose('/index/', methods=['POST'])
    @csrf.exempt
    @safe
    def index(self, **kw):
        """process json request received"""
        req_json = request.get_json()
        companyID = req_json.pop('companyID', None)
        if not companyID or not isinstance(companyID, int):
            error = dict(ServiceMessageArray=[dict(Code=120, Description="The following field(s) are required: companyID")])
            data = json.dumps(error)
            return data, 400,  {'Content-Type':'application/json'}
        c = db.session.query(Company).get(companyID)
        if not c:
            error = dict(ServiceMessageArray=[dict(Code=100, Description="ID (companyID) not found")])
            data = json.dumps(error)
            return data, 500,  {'Content-Type':'application/json'}
        kw = {"wsVersion": c.po_version, "id": c.user_name, "password": c.password, "PO": req_json['PO']}
        try:
            self.validatePO(**kw)
        except Exception as e:
            data = {"ServiceMessageArray":[{"ServiceMessage": {"code": 999, "description": str(e)}}]}
            return data, 400,  {'Content-Type':'application/json'}
        data = self.sendPO(c, **kw)
        return data, htmlCode,  {'Content-Type':'application/json'}

    @expose('/instructions/', methods=['GET'])
    def instructions(self):
        """ diplay instructions for sending jsonPO"""
        return self.render_template( 'purchaseOrder/instructions.html')

    def sendPO(self, company, **kw):
        """send the request.  Can be used by index or a plugin"""
        client = SoapClient(serviceMethod='sendPO', serviceUrl=company.po_url, serviceWSDL=company.po_wsdl, serviceCode='PO',
                serviceVersion=company.po_version, filters=False, values=False, **kw)
        client.serviceCall()
        if client.data == 'Unable to get Response' or 'SoapFault' in client.data:
            htmlCode = 500
        # response = client.response
        # assert False
        return client.sobject_to_json()

    @expose('/test/', methods=['GET'])
    def test(self):
        """
            test the service using exampleSimplePO.json
            *** MAKE SURE to SET the test link for the company (or receiveTest below) in the DB so that it doesn't hit the production with this test! ***
            currently don't have separate fields for test urls
            or create a new company which hits http://localhost/jsonpo/test2/ to return the xml to you to view
        """
        with open('exampleSimplePO.json') as json_file:
            req_json = json.load(json_file)
        companyID = req_json.pop('companyID', None)
        if not companyID or not isinstance(companyID, int):
            error = dict(ServiceMessageArray=[dict(Code=120, Description="The following field(s) are required: companyID")])
            data = json.dumps(error)
            return data, 400,  {'Content-Type':'application/json'}
        c = db.session.query(Company).get(companyID)
        if not c:
            error = dict(ServiceMessageArray=[dict(Code=100, Description="ID (companyID) not found")])
            data = json.dumps(error)
            return data, 500,  {'Content-Type':'application/json'}
        kw = {"wsVersion": c.po_version, "id": c.user_name, "password": c.password, "PO": req_json['PO']}
        try:
            self.validatePO(**kw)
        except Exception as e:
            data = {"ServiceMessageArray":[{"ServiceMessage": {"code": 999, "description": str(e)}}]}
            return data, 400,  {'Content-Type':'application/json'}
        data = self.sendPO(c, **kw)
        return data, htmlCode,  {'Content-Type':'application/json'}

    @expose('/receiveTest/', methods=['GET','POST'])
    @csrf.exempt
    def receiveTest(self):
        """return the xml received"""
        sent = html.escape("Sent: ({})".format(request.data))
        data = u'<?xml version="1.0" encoding="UTF-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><SendPOResponse xmlns="http://www.promostandards.org/WSDL/PO/1.0.0/"><ServiceMessageArray><ServiceMessage><code>999</code><description>'
        data = data + sent
        data = data + u'</description><severity>Info</severity></ServiceMessage></ServiceMessageArray></SendPOResponse></s:Body></s:Envelope>'
        r = Response(response=data.strip(), status=200, mimetype="application/xml")
        r.headers["Content-Type"] = "text/xml; charset=utf-8"
        return r

    def validatePO(self, **kw):
        """
        validate required fields are present and validate types
        uses schema to validate and return validated kw
        """
        # following vars are used for validation
        #ISO-8601 format for date and datetime.
        rdatetime = r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(([+-]\d\d:\d\d)|Z)?$'
        toleranceList = ('AllowOverRun', 'AllowUnderrun', 'AllowOverrunOrUnderrun', 'ExactOnly')
        uomList = ['BX', 'CA', 'DZ', 'EA', 'KT', 'PR', 'PK', 'RL', 'ST', 'SL', 'TH']

        conact_schema = Schema({
            Optional("attentionTo"): And(lambda s: var_check(s,35), error='"attentionTo" should evaluate to varchar(35)'),
            Optional("companyName"): And(lambda s: var_check(s,35), error='"companyName" should evaluate to varchar(35)'),
            Optional("address1"): And(lambda s: var_check(s,35), error='"address1" should evaluate to varchar(35)'),
            Optional("address2"): And(lambda s: var_check(s,35), error='"address2" should evaluate to varchar(35)'),
            Optional("address3"): And(lambda s: var_check(s,35), error='"address3" should evaluate to varchar(35)'),
            Optional("city"): And(lambda s: var_check(s,30), error='"city" should evaluate to varchar(30)'),
            Optional("region"): And(lambda s: var_check(s,3), error='"region" should evaluate to varchar(3)'),
            Optional("postalCode"): And(lambda s: var_check(s,10), error='"postalCode" should evaluate to varchar(10)'),
            Optional("country"): And(lambda s: var_check(s,2), error='"country" should evaluate to varchar(2)'),
            Optional("email"): And(lambda s: var_check(s,128), error='"email" should evaluate to varchar(128)'),
            Optional("phone"): And(lambda s: var_check(s,32), error='"phone" should evaluate to varchar(32)'),
            Optional("comments"): str,
        })

        quantity_schema = Schema({
                                    "value": And(Use(to_decimal_4),validDecimal_12_4),
                                    "uom": And(str,lambda s: s in uomList)
                                })
        # schema used for validating PO version 1.0.0
        v1_0_0_schema = Schema({"wsVersion": And(str, len), "id": And(str, len), Optional("password"): str,
            "PO": {
                "orderType": And(str, lambda s: s in ('Blank', 'Sample', 'Simple', 'Configured')),
                "orderNumber": And(lambda s: var_check(s,64), error='"orderNumber" should evaluate to varchar(64)'),
                "orderDate": And(Const(Use(datetime.fromisoformat)), Regex(r'{}'.format(rdatetime))),
                Optional("lastModified"): And(Const(Use(datetime.fromisoformat)), Regex(r'{}'.format(rdatetime))),
                "totalAmount": And(Use(to_decimal_4),validDecimal_12_4),
                Optional("paymentTerms"): str,
                "rush": Use(xml_bool),
                "currency": And(lambda s: var_check(s,3), error='"currency" should evaluate to varchar(3)'),
                Optional("DigitalProof"): {
                    "required": Use(xml_bool),
                    "DigitalProofAddressesArray": [
                        {
                            "DigitalProofAddress": {
                                "type": And(lambda s: var_check(s,64), error='"type" should evaluate to varchar(64)'),
                                "email": And(lambda s: var_check(s,128), error='"email" should evaluate to varchar(128)'),
                                "lineItemGroupingId": int
                            }
                        }
                    ]
                },
                Optional("OrderContactArray"): [
                    {"Contact": {
                        "contactType": And(str,lambda s: s in ['Art', 'Bill', 'Expeditor', 'Order', 'Sales', 'Ship', 'Sold']),
                        "ContactDetails": conact_schema
                    }}
                ],
                "ShipmentArray": [
                    {"Shipment":{
                        "ShipTo": {
                            "customerPickup": Use(xml_bool),
                            "shipmentId": int,
                            "ContactDetails": conact_schema
                        },
                        "packingListRequired": Use(xml_bool),
                        "blindShip": Use(xml_bool),
                        "allowConsolidation": Use(xml_bool),
                        "FreightDetails": {
                            "carrier": And(lambda s: var_check(s,64), error='"carrier" should evaluate to varchar(64)'),
                            "service": And(lambda s: var_check(s,64), error='"service" should evaluate to varchar(64)')
                        }
                    }}
                ],
                "LineItemArray": [
                    {"LineItem":{
                        "lineNumber": int,
                        "description": str,
                        "lineType": And(str,lambda s: s in ['New', 'Repeat', 'Reference']),
                        Optional("Quantity"): quantity_schema,
                        Optional("fobid"): And(lambda s: var_check(s,64), error='"fobid" should evaluate to varchar(64)'),
                        "ToleranceDetails": {
                            "tolerance": And(str,lambda s: s in toleranceList),
                            Optional("value"): And(Use(to_decimal_4),validDecimal_12_4),
                            Optional('uom'): And(str,lambda s: s in uomList)
                        },
                        "allowPartialShipments": Use(xml_bool),
                        Optional("unitPrice"): And(Use(to_decimal_4),validDecimal_12_4),
                        "lineItemTotal": And(Use(to_decimal_4),validDecimal_12_4),
                        Optional("requestedShipDate"): And(Const(Use(datetime.fromisoformat)), Regex(r'{}'.format(rdatetime))),
                        Optional("requestedInHands"): And(Const(Use(datetime.fromisoformat)), Regex(r'{}'.format(rdatetime))),
                        Optional("referenceSalesQuote"): And(lambda s: var_check(s,64), error='"referenceSalesQuote" should evaluate to varchar(64)'),
                        Optional("Program"): {
                            Optional("id"): And(lambda s: var_check(s,64), error='"id" should evaluate to varchar(64)'),
                            Optional("name"): And(lambda s: var_check(s,64), error='"name" should evaluate to varchar(64)')
                        },
                        Optional("endCustomerSalesOrder"): And(lambda s: var_check(s,64), error='"endCustomerSalesOrder" should evaluate to varchar(64)'),
                        Optional("productId"): And(lambda s: var_check(s,64), error='"productId" should evaluate to varchar(64)'),
                        Optional("customerProductId"): And(lambda s: var_check(s,64), error='"customerProductId" should evaluate to varchar(64)'),
                        Optional("lineItemGroupingId"): int,
                        Optional("PartArray"): [
                            {
                                "Part":{
                                    Optional("partGroup"): And(lambda s: var_check(s,64), error='"partGroup" should evaluate to varchar(64)'),
                                    "partId": And(lambda s: var_check(s,64), error='"partId" should evaluate to varchar(64)'),
                                    Optional("customerPartId"): And(lambda s: var_check(s,64), error='"customerPartId" should evaluate to varchar(64)'),
                                    "customerSupplied": Use(xml_bool),
                                    Optional("description"): str,
                                    "Quantity": quantity_schema,
                                    Optional("locationLinkId"): [int],
                                    Optional("unitPrice"): And(Use(to_decimal_4),validDecimal_12_4),
                                    Optional("extendedPrice"): And(Use(to_decimal_4),validDecimal_12_4),
                                    Optional("ShipmentLinkArray"): [
                                        {
                                            "ShipmentLink":{
                                                "shipmentId": int,
                                                "Quantity": quantity_schema,
                                            }
                                        }
                                    ]
                                }
                            }
                        ],
                        Optional("Configuration"): {
                            Optional("referenceNumber"): And(lambda s: var_check(s,64), error='"referenceNumber" should evaluate to varchar(64)'),
                            Optional("referenceNumberType"): And(str,lambda s: s in ['PurchaseOrder','SalesOrder', 'JobOrWorkOrder']),
                            "preProductionProof": Use(xml_bool),
                            Optional("ChargeArray"): [
                                {
                                    "Charge": {
                                        "chargeId": And(lambda s: var_check(s,64), error='"chargeId" should evaluate to varchar(64)'),
                                        Optional("chargeName"): And(lambda s: var_check(s,128), error='"chargeName" should evaluate to varchar(128)'),
                                        Optional("description"): str,
                                        "chargeType": And(str,lambda s: s in ['Freight', 'Order', 'Run', 'Setup']),
                                        "Quantity": quantity_schema,
                                        Optional("unitprice"): And(Use(to_decimal_4),validDecimal_12_4),
                                        Optional("extendedPrice"): And(Use(to_decimal_4),validDecimal_12_4)
                                    }
                                }
                            ],
                            Optional("LocationArray"): [
                                {
                                    "Location":{
                                        "locationLinkId": int,
                                        "locationId": int,
                                        Optional("locationName"): And(lambda s: var_check(s,128), error='"locationName" should evaluate to varchar(128)'),
                                        "DecorationArray": [
                                            {
                                                "Decoration": {
                                                    "decorationId": int,
                                                    Optional("decorationName"): And(lambda s: var_check(s,128), error='"decorationName" should evaluate to varchar(128)'),
                                                    "Artwork":{
                                                        Optional("refArtworkId"): And(lambda s: var_check(s,64), error='"refArtworkId" should evaluate to varchar(64)'),
                                                        Optional("description"): str,
                                                        Optional("Dimensions"): {
                                                            "geometry": And(str,lambda s: s in ['Circle', 'Rectangle', 'Other']),
                                                            "useMaxLocationDimensions": Use(xml_bool),
                                                            Optional("height"): And(Use(to_decimal_4),validDecimal_12_4),
                                                            Optional("width"): And(Use(to_decimal_4),validDecimal_12_4),
                                                            Optional("diameter"): And(Use(to_decimal_4),validDecimal_12_4),
                                                            Optional('uom'): And(str,lambda s: s in uomList)
                                                        },
                                                        Optional("instructions"): str,
                                                        Optional("Layers"):{
                                                            "colorSystem": And(str,lambda s: s in ['Cmyk', 'Other', 'Pms', 'Rgb', 'Thread']),
                                                            "LayerOrStopArray": {
                                                                "nameOrNumber": And(lambda s: var_check(s,64), error='"nameOrNumber" should evaluate to varchar(64)'),
                                                                "description": str,
                                                                "color": And(lambda s: var_check(s,64), error='Layer "color" should evaluate to varchar(64)')
                                                            }
                                                        },
                                                        Optional("TypesetArray"): [
                                                            {
                                                                "sequenceNumber": int,
                                                                "value": And(lambda s: var_check(s,1024), error='Typset "value" should evaluate to varchar(1024)'),
                                                                Optional("font"): And(lambda s: var_check(s,64), error='"font" should evaluate to varchar(64)'),
                                                                Optional("fontSize"): Use(Decimal)
                                                            }
                                                        ],
                                                        Optional("totalStitchCount"): int
                                                    }
                                                }
                                            }
                                        ],
                                    }
                                }
                            ]
                        }
                    }}
                ],
                "termsAndConditions": str,
                Optional("salesChannel"): And(lambda s: var_check(s,64), error='"salesChannel" should evaluate to varchar(64)'),
                Optional("promoCode"): And(lambda s: var_check(s,64), error='"promoCode" should evaluate to varchar(64)'),
                Optional("TaxInformationArray"): [
                    {
                        "TaxInformation": {
                            "taxId": And(lambda s: var_check(s,64), error='"taxId" should evaluate to varchar(64)'),
                            "taxType": And(lambda s: var_check(s,64), error='"taxType" should evaluate to varchar(64)'),
                            "taxExempt": Use(xml_bool),
                            "taxJurisdiction": And(lambda s: var_check(s,64), error='"taxJurisdiction" should evaluate to varchar(64)'),
                            Optional("taxAmount"): Use(Decimal)
                        }
                    }
                ]
            }}
        )

        # run the validation
        v1_0_0_schema.validate(kw)
