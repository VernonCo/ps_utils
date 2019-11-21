#!/bin/python3
import re

def titlize(columnName):
    """
    Splits column name for ease of readability and titles it
    ie. columnName -> Column Name
    """
    return ' '.join(re.findall('[a-zA-Z][^A-Z]*', columnName)).title()

def get_field(obj):
    """get the field that has the main # for the row"""
    number = ''
    keyList = list(obj.keys())
    for name in keyList:
        if 'Number' in name:
            number = name
            break
    if not number:
        for name in keyList:
            if 'Id' in name:
                number = name
                break
    if not number and 'id' in keyList:
        number = 'id'
    return number

def get_id_field(obj):
    """get the id field from the dict"""
    number = ''
    if isinstance(obj,dict):
        number = get_field(obj)
    elif isinstance(obj,list) and isinstance(obj[0],dict):
        number = get_field(obj[0])
    return number


class Table():
    """create objects for templates to display the information retrieved from a SOAP request"""

    def __init__(self, obj, action):
        self.soap_obj = obj
        self.parsed = {}
        self.list_columns = []
        self.action = action  #ie. OrderShipmentNotification
        self.html = ''
        self.list_header = ''

    def _html_column(self,obj, tableId):
        """ create a table in the column from the obj"""
        # insert table
        #******************************************************
        header_list = self._html_header(obj, tableId)
        if header_list:
            self.html += '<tbody><tr>'
            for name in header_list:
                self.html += '<td>'
                # insert value, table with one row, or table with rows
                ##################################################################
                if not isinstance(obj[name],list) and not isinstance(obj[name],dict):
                    self.html += '{}'.format(obj[name])
                elif isinstance(obj[name],dict):
                    self._html_column(obj[name], name)
                elif isinstance(obj[name],list):
                    #list of text
                    if 'suds.sax.text.Text' in str(type(obj[name][0])):
                        self.html += '<section><h3>{}</h3><ul>'.format(name.capitalize())
                        for row in obj[name]:
                            self.html += '<li>{}</li>'.format(row)
                        self.html += '</ul></section>'
                    # list of objects
                    else:
                        self.html += '<div class="{}">'.format(name)
                        self._html_list(obj[name], name)
                        self.html += '</div>'
                ###################################################################
                self.html += '</td>'
            self.html += '</tr></tbody>'
        self.html += '</table>'
        #*****************************************************************

    def _html_list(self,obj, tableId):
        """
        create rows of html from obj following the structure of the header_list
        """
        number = get_id_field(obj)
        for row in obj:
            if number:
                self.html += '<h3>{} {}</h3><div class="table-striped">'.format(titlize(tableId),row[number])
            else:
                self.html += '<h3>{}</h3><div class="table-striped">'.format(titlize(tableId))
            # insert table
            ##***************************************************************
            header_list = self._html_header(obj, tableId)  #<table><thead></thead>
            if header_list:
                self.html += '<tbody><tr>'
                for name in header_list:
                    self.html += '<td>'
                    # insert value, table with one row, or table with rows
                    ##################################################################
                    if not isinstance(row[name],list) and not isinstance(row[name],dict):
                        self.html += '{}'.format(row[name])
                    elif isinstance(row[name],dict):
                        self._html_column(row[name], name)
                    elif isinstance(row[name],list):
                        if 'suds.sax.text.Text' in str(type(row[name][0])):
                            self.html += '<section><h3>{}</h3><ul>'.format(name.capitalize())
                            for item in row[name]:
                                self.html += '<li>{}</li>'.format(item)
                            self.html += '</ul></section>'
                        # list of objects
                        else:
                            self.html += '<div class="{}">'.format(name)
                            self._html_list(row[name], name)
                            self.html += '</div>'
                    ###################################################################
                    self.html += '</td>'
                self.html += '</tr></tbody>'
            self.html += '</table>'
            #*****************************************************************
            self.html += '</div>'

    def _html_header(self,obj, tableId):
        """create header row from dict.keys() and place list items last in line
            return header_list for sort and endingHtml to place at end of _html_list
        """
        reg_col = []
        reg_list = []
        reg_dict = []
        self.is_list = False
        if isinstance(obj,list):
            head_row = obj[0]
            if isinstance(head_row,list):
                for row in obj:
                    self.html += '<div class="{}">'.format(self.action)
                    self._html_list(row, tableId)
                    self.html += '</div>'
                return
            self.is_list = True
        else:
            head_row = obj
        column_names = list(head_row.keys())
        number = get_id_field(head_row)
        if  number:
            #removing the id field from the header as it will be displayed in the div title
            column_names.remove(number)
        for name in column_names:
            if isinstance(head_row[name],list):
                reg_list.append(name)
            elif isinstance(head_row[name],dict):
                reg_dict.append(name)
            else:
                reg_col.append(name)
        column_names = reg_col + reg_dict
        self.html += '<table class="{}" border="1" style="width:100%"><thead><tr>'.format(tableId)
        self.list_header = tableId if not self.list_header else self.list_header
        for name in column_names:
            self.html += '<th>{}</th>'.format(titlize(name))
        for name in reg_list:
            self.html += '<th>{}(s)</th>'.format(titlize(name))
        self.html += '</tr></thead>'
        return column_names + reg_list


    def table_html(self):
        """ create the html for the table"""
        # self.html = '<table id="resultsTable1"  style="text-align: center;" class="display table-bordered"\
        #     data-page-length="25" data-order="[[ 0, \'asc\' ]]" width="100%"><tr>'
        # try:
        if isinstance(self.parsed,list):
            self.html += '<div class="{}">'.format(self.action)
            self._html_list(self.parsed,self.action)
            self.html += '</div>'
        elif isinstance(self.parsed,dict):
            self._html_column(self.parsed,self.action)
        # except Exception as e:
        #     logging.error(str(e))
        #     self.html = 'Error parsing result'
        # self.html += '</tr></table>'
        return self.html

    def parse_return(self):
        """ break up the soap_obj by fields and lists"""
        if not isinstance(self.soap_obj, dict):
            return
        self.parsed = self._parse_obj(self.soap_obj,self.action)

    def _parse_obj(self, obj, fieldName):
        if not isinstance(obj, dict) and not isinstance(obj,list):
            return obj
        elif isinstance(obj, dict):
            temp = {}
            columns = list(obj.keys())
            for column in columns:
                if 'Array' in column:
                    field = column.replace('Array','')
                    if field not in self.list_columns:
                        self.list_columns.append(field)
            for k, v in obj.items():
                if 'Array' in k:
                    next_field_name = k.replace('Array','')
                    # this name does not follow the standard naming convention
                    if k == 'ProductPackagingArray':
                        next_field_name = "ProductPackage"
                    v = v[next_field_name]
                    # print({'k':k,'path':path,'parsed':self.parsed[path][field]})
                    temp[k.replace('Array','')] = self._parse_obj(v,fieldName)
                else:
                    temp[k] = self._parse_obj(v,fieldName)
            return temp
        elif isinstance(obj,list):
            # pp.pprint({'field':field,'path':path,'parsed':self.parsed})
            temp = []
            for l in obj:
                temp.append(self._parse_obj(l, fieldName))
            return temp



    def _test(self):
        self.soap_obj = {"OrderShipmentNotificationArray":
                {"OrderShipmentNotification": [{
                    "purchaseOrderNumber": "6100088",
                    "complete": True,
                    "SalesOrderArray": {
                        "SalesOrder": [{
                            "salesOrderNumber": "3836235",
                            "complete": True,
                            "ShipmentLocationArray": {
                                "ShipmentLocation": [{
                                    "id":
                                    3514724,
                                    "complete":
                                    True,
                                    "ShipFromAddress": {
                                        "address1":
                                        "Ariel Premium Supply, Inc",
                                        "address2": "8825 Page Ave",
                                        "city": "St Louis",
                                        "region": "MO",
                                        "postalCode": "63114",
                                        "country": "US"
                                    },
                                    "ShipToAddress": {
                                        "address1": "GREENSBORO COLLEGE",
                                        "address2": "JENNA AVENT",
                                        "address3": "815 W MARKET ST",
                                        "address4": None,
                                        "city": "GREENSBORO",
                                        "region": "NC",
                                        "postalCode": "27401-1823",
                                        "country": "US"
                                    },
                                    "shipmentDestinationType":
                                    "Commercial",
                                    "PackageArray": {
                                        "Package": [{
                                            "id": 3927287,
                                            "trackingNumber":
                                            "1Z37786W0399251528",
                                            "shipmentDate":
                                            "2019-06-10T15:57:47-05:00",
                                            "dimUOM": "Inches",
                                            "length": 18.0,
                                            "width": 18.0,
                                            "height": 9.0,
                                            "weightUOM": "Pounds",
                                            "weight": 13.0,
                                            "carrier": "UPS",
                                            "shipmentMethod": "UPS Ground",
                                            "shipmentTerms": "Prepaid",
                                            "ItemArray": {
                                                "Item": [{
                                                    "supplierProductId":
                                                    "DTM-OL17SV",
                                                    "quantity": 25.0
                                                }]
                                            }
                                        }, {
                                            "id": 3927288,
                                            "trackingNumber":
                                            "1Z37786W0395725130",
                                            "shipmentDate":
                                            "2019-06-10T15:57:47-05:00",
                                            "dimUOM": "Inches",
                                            "length": 18.0,
                                            "width": 18.0,
                                            "height": 9.0,
                                            "weightUOM": "Pounds",
                                            "weight": 13.0,
                                            "carrier": "UPS",
                                            "shipmentMethod": "UPS Ground",
                                            "shipmentTerms": "Prepaid",
                                            "ItemArray": {
                                                "Item": [{
                                                    "supplierProductId":
                                                    "DTM-OL17SV",
                                                    "quantity": 25.0
                                                }]
                                            }
                                        }, {
                                            "id": 3927289,
                                            "trackingNumber":
                                            "1Z37786W0396864345",
                                            "shipmentDate":
                                            "2019-06-10T15:57:47-05:00",
                                            "dimUOM": "Inches",
                                            "length": 18.0,
                                            "width": 18.0,
                                            "height": 9.0,
                                            "weightUOM": "Pounds",
                                            "weight": 13.0,
                                            "carrier": "UPS",
                                            "shipmentMethod": "UPS Ground",
                                            "shipmentTerms": "Prepaid",
                                            "ItemArray": {
                                                "Item": [{
                                                    "supplierProductId":
                                                    "DTM-OL17SV",
                                                    "quantity": 25.0
                                                }]
                                            }
                                        }, {
                                            "id": 3927290,
                                            "trackingNumber":
                                            "1Z37786W0396645153",
                                            "shipmentDate":
                                            "2019-06-10T15:57:47-05:00",
                                            "dimUOM": "Inches",
                                            "length": 18.0,
                                            "width": 18.0,
                                            "height": 9.0,
                                            "weightUOM": "Pounds",
                                            "weight": 13.0,
                                            "carrier": "UPS",
                                            "shipmentMethod": "UPS Ground",
                                            "shipmentTerms": "Prepaid",
                                            "ItemArray": {
                                                "Item": [{
                                                    "supplierProductId":
                                                    "DTM-OL17SV",
                                                    "quantity": 25.0
                                                }]
                                            }
                                        }]
                                    }
                                }]
                            }
                        }]
                    }
                }]
            }
        }


# t = Table({},'OrderShipmentNotification')
# t._test()
# t.parse_return()
# print(t.table_html())
# print(t.list_columns)
# # pp.pprint(t.parsed)
# f = open('test.html','w')
# f.write(t.html)
# f.close()

data = {
    'Configuration': {
        'PartArray': {
            'Part': [{
                'partId': 'BG344-34-00',
                'partDescription': 'BG344-3L U P Dry Bag',
                'PartPriceArray': {
                    'PartPrice': [{
                        'minQuantity': 60,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 120,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 250,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 500,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }]
                },
                'partGroup': 1,
                'nextPartGroup': 0,
                'partGroupRequired': True,
                'partGroupDescription': 'Main Product',
                'ratio': 1.0,
                'defaultPart': True,
                'LocationIdArray': {
                    'LocationId': [{
                        'locationId': 135
                    }]
                }
            }, {
                'partId': 'BG344-36-00',
                'partDescription': 'BG344-3L U P Dry Bag',
                'PartPriceArray': {
                    'PartPrice': [{
                        'minQuantity': 60,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 120,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 250,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 500,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }]
                },
                'partGroup': 1,
                'nextPartGroup': 0,
                'partGroupRequired': True,
                'partGroupDescription': 'Main Product',
                'ratio': 1.0,
                'defaultPart': True,
                'LocationIdArray': {
                    'LocationId': [{
                        'locationId': 135
                    }]
                }
            }, {
                'partId': 'BG344-37-00',
                'partDescription': 'BG344-3L U P Dry Bag',
                'PartPriceArray': {
                    'PartPrice': [{
                        'minQuantity': 60,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 120,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 250,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 500,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }]
                },
                'partGroup': 1,
                'nextPartGroup': 0,
                'partGroupRequired': True,
                'partGroupDescription': 'Main Product',
                'ratio': 1.0,
                'defaultPart': True,
                'LocationIdArray': {
                    'LocationId': [{
                        'locationId': 135
                    }]
                }
            }, {
                'partId': 'BG344-42-00',
                'partDescription': 'BG344-3L U P Dry Bag',
                'PartPriceArray': {
                    'PartPrice': [{
                        'minQuantity': 60,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 120,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 250,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }, {
                        'minQuantity': 500,
                        'price': 3.3417,
                        'discountCode': ' ',
                        'priceUom': 'EA',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }]
                },
                'partGroup': 1,
                'nextPartGroup': 0,
                'partGroupRequired': True,
                'partGroupDescription': 'Main Product',
                'ratio': 1.0,
                'defaultPart': True,
                'LocationIdArray': {
                    'LocationId': [{
                        'locationId': 135
                    }]
                }
            }]
        },
        'LocationArray': {
            'Location': [{
                'locationId': 135,
                'locationName': 'Front Center of Bag',
                'DecorationArray': {
                    'Decoration': [{
                        'decorationId': 20,
                        'decorationName': 'TruColor',
                        'decorationGeometry': 'RECTANGLE',
                        'decorationHeight': 4.0,
                        'decorationWidth': 3.0,
                        'decorationDiameter': 0.0,
                        'decorationUom': 'Inches',
                        'allowSubForDefaultLocation': True,
                        'allowSubForDefaultMethod': True,
                        'itemPartQuantityLTM': 30,
                        'ChargeArray': {
                            'Charge': [{
                                'chargeId': 29,
                                'chargeName': 'Personalization',
                                'chargeDescription': 'Personalization',
                                'chargeType': 'Run',
                                'ChargePriceArray': {
                                    'ChargePrice': [{
                                        'xMinQty':
                                        1,
                                        'xUom':
                                        'EA',
                                        'yMinQty':
                                        1,
                                        'yUom':
                                        'Other',
                                        'price':
                                        0.8,
                                        'discountCode':
                                        'G',
                                        'repeatPrice':
                                        0.8,
                                        'repeatDiscountCode':
                                        'G',
                                        'priceEffectiveDate':
                                        '2019-01-01T00:00:00',
                                        'priceExpiryDate':
                                        '2019-12-31T00:00:00'
                                    }]
                                },
                                'chargesAppliesLTM': False,
                                'chargesPerLocation': 0,
                                'chargesPerColor': 0
                            }, {
                                'chargeId': 134,
                                'chargeName': 'Set-up TruColor',
                                'chargeDescription': 'Set-up TruColor',
                                'chargeType': 'Setup',
                                'ChargePriceArray': {
                                    'ChargePrice': [{
                                        'xMinQty':
                                        1,
                                        'xUom':
                                        'EA',
                                        'yMinQty':
                                        1,
                                        'yUom':
                                        'Locations',
                                        'price':
                                        44.0,
                                        'discountCode':
                                        'G',
                                        'repeatPrice':
                                        0.0,
                                        'repeatDiscountCode':
                                        'G',
                                        'priceEffectiveDate':
                                        '2019-01-01T00:00:00',
                                        'priceExpiryDate':
                                        '2019-12-31T00:00:00'
                                    }]
                                },
                                'chargesAppliesLTM': False,
                                'chargesPerLocation': 0,
                                'chargesPerColor': 0
                            }, {
                                'chargeId': 137,
                                'chargeName': 'TruColor Large Imprint',
                                'chargeDescription': 'TruColor Large Imprint',
                                'chargeType': 'Run',
                                'ChargePriceArray': {
                                    'ChargePrice': [{
                                        'xMinQty':
                                        1,
                                        'xUom':
                                        'EA',
                                        'yMinQty':
                                        1,
                                        'yUom':
                                        'Inches',
                                        'price':
                                        0.192,
                                        'discountCode':
                                        'G',
                                        'repeatPrice':
                                        0.192,
                                        'repeatDiscountCode':
                                        'G',
                                        'priceEffectiveDate':
                                        '2019-01-01T00:00:00',
                                        'priceExpiryDate':
                                        '2019-12-31T00:00:00'
                                    }]
                                },
                                'chargesAppliesLTM': False,
                                'chargesPerLocation': 0,
                                'chargesPerColor': 0
                            }, {
                                'chargeId': 168,
                                'chargeName': 'TruColor PMS Color Match',
                                'chargeDescription':
                                'TruColor PMS Color Match',
                                'chargeType': 'Order',
                                'ChargePriceArray': {
                                    'ChargePrice': [{
                                        'xMinQty':
                                        1,
                                        'xUom':
                                        'EA',
                                        'yMinQty':
                                        1,
                                        'yUom':
                                        'Colors',
                                        'price':
                                        0.0,
                                        'discountCode':
                                        'G',
                                        'repeatPrice':
                                        20.0,
                                        'repeatDiscountCode':
                                        'G',
                                        'priceEffectiveDate':
                                        '2019-01-01T00:00:00',
                                        'priceExpiryDate':
                                        '2019-12-31T00:00:00'
                                    }]
                                },
                                'chargesAppliesLTM': False,
                                'chargesPerLocation': 0,
                                'chargesPerColor': 0
                            }, {
                                'chargeId': 192,
                                'chargeName': 'Tariff Surcharge',
                                'chargeDescription': 'Tariff Surcharge',
                                'chargeType': 'Run',
                                'ChargePriceArray': {
                                    'ChargePrice': [{
                                        'xMinQty':
                                        1,
                                        'xUom':
                                        'EA',
                                        'yMinQty':
                                        1,
                                        'yUom':
                                        'Other',
                                        'price':
                                        0.25,
                                        'discountCode':
                                        'Z',
                                        'repeatPrice':
                                        0.25,
                                        'repeatDiscountCode':
                                        'Z',
                                        'priceEffectiveDate':
                                        '2019-01-01T00:00:00',
                                        'priceExpiryDate':
                                        '2019-12-31T00:00:00'
                                    }]
                                },
                                'chargesAppliesLTM': False,
                                'chargesPerLocation': 0,
                                'chargesPerColor': 0
                            }]
                        },
                        'decorationUnitsIncluded': 3,
                        'decorationUnitsIncludedUom': 'SQUARE INCHES',
                        'decorationUnitsMax': 25,
                        'defaultDecoration': True,
                        'leadTime': 3,
                        'rushLeadTime': 1
                    }]
                },
                'decorationsIncluded': 1,
                'defaultLocation': False,
                'maxDecoration': 1,
                'minDecoration': 1,
                'locationRank': 1
            }]
        },
        'productId': 'BG344',
        'currency': 'USD',
        'FobArray': {
            'Fob': [{
                'fobId': '1',
                'fobPostalCode': '14072'
            }]
        },
        'priceType': 'Customer'
    }
}
parsed = {
    'Configuration': {
        'Part': [{
            'partId':
            'BG344-34-00',
            'partDescription':
            'BG344-3L U P Dry Bag',
            'PartPrice': [{
                'minQuantity': 60,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 120,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 250,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 500,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }],
            'partGroup':
            1,
            'nextPartGroup':
            0,
            'partGroupRequired':
            True,
            'partGroupDescription':
            'Main Product',
            'ratio':
            1.0,
            'defaultPart':
            True,
            'LocationId': [{
                'locationId': 135
            }]
        }, {
            'partId':
            'BG344-36-00',
            'partDescription':
            'BG344-3L U P Dry Bag',
            'PartPrice': [{
                'minQuantity': 60,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 120,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 250,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 500,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }],
            'partGroup':
            1,
            'nextPartGroup':
            0,
            'partGroupRequired':
            True,
            'partGroupDescription':
            'Main Product',
            'ratio':
            1.0,
            'defaultPart':
            True,
            'LocationId': [{
                'locationId': 135
            }]
        }, {
            'partId':
            'BG344-37-00',
            'partDescription':
            'BG344-3L U P Dry Bag',
            'PartPrice': [{
                'minQuantity': 60,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 120,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 250,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 500,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }],
            'partGroup':
            1,
            'nextPartGroup':
            0,
            'partGroupRequired':
            True,
            'partGroupDescription':
            'Main Product',
            'ratio':
            1.0,
            'defaultPart':
            True,
            'LocationId': [{
                'locationId': 135
            }]
        }, {
            'partId':
            'BG344-42-00',
            'partDescription':
            'BG344-3L U P Dry Bag',
            'PartPrice': [{
                'minQuantity': 60,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 120,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 250,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }, {
                'minQuantity': 500,
                'price': 3.3417,
                'discountCode': ' ',
                'priceUom': 'EA',
                'priceEffectiveDate': '2019-01-01T00:00:00',
                'priceExpiryDate': '2019-12-31T00:00:00'
            }],
            'partGroup':
            1,
            'nextPartGroup':
            0,
            'partGroupRequired':
            True,
            'partGroupDescription':
            'Main Product',
            'ratio':
            1.0,
            'defaultPart':
            True,
            'LocationId': [{
                'locationId': 135
            }]
        }],
        'Location': [{
            'locationId':
            135,
            'locationName':
            'Front Center of Bag',
            'Decoration': [{
                'decorationId':
                20,
                'decorationName':
                'TruColor',
                'decorationGeometry':
                'RECTANGLE',
                'decorationHeight':
                4.0,
                'decorationWidth':
                3.0,
                'decorationDiameter':
                0.0,
                'decorationUom':
                'Inches',
                'allowSubForDefaultLocation':
                True,
                'allowSubForDefaultMethod':
                True,
                'itemPartQuantityLTM':
                30,
                'Charge': [{
                    'chargeId':
                    29,
                    'chargeName':
                    'Personalization',
                    'chargeDescription':
                    'Personalization',
                    'chargeType':
                    'Run',
                    'ChargePrice': [{
                        'xMinQty': 1,
                        'xUom': 'EA',
                        'yMinQty': 1,
                        'yUom': 'Other',
                        'price': 0.8,
                        'discountCode': 'G',
                        'repeatPrice': 0.8,
                        'repeatDiscountCode': 'G',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }],
                    'chargesAppliesLTM':
                    False,
                    'chargesPerLocation':
                    0,
                    'chargesPerColor':
                    0
                }, {
                    'chargeId':
                    134,
                    'chargeName':
                    'Set-up TruColor',
                    'chargeDescription':
                    'Set-up TruColor',
                    'chargeType':
                    'Setup',
                    'ChargePrice': [{
                        'xMinQty': 1,
                        'xUom': 'EA',
                        'yMinQty': 1,
                        'yUom': 'Locations',
                        'price': 44.0,
                        'discountCode': 'G',
                        'repeatPrice': 0.0,
                        'repeatDiscountCode': 'G',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }],
                    'chargesAppliesLTM':
                    False,
                    'chargesPerLocation':
                    0,
                    'chargesPerColor':
                    0
                }, {
                    'chargeId':
                    137,
                    'chargeName':
                    'TruColor Large Imprint',
                    'chargeDescription':
                    'TruColor Large Imprint',
                    'chargeType':
                    'Run',
                    'ChargePrice': [{
                        'xMinQty': 1,
                        'xUom': 'EA',
                        'yMinQty': 1,
                        'yUom': 'Inches',
                        'price': 0.192,
                        'discountCode': 'G',
                        'repeatPrice': 0.192,
                        'repeatDiscountCode': 'G',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }],
                    'chargesAppliesLTM':
                    False,
                    'chargesPerLocation':
                    0,
                    'chargesPerColor':
                    0
                }, {
                    'chargeId':
                    168,
                    'chargeName':
                    'TruColor PMS Color Match',
                    'chargeDescription':
                    'TruColor PMS Color Match',
                    'chargeType':
                    'Order',
                    'ChargePrice': [{
                        'xMinQty': 1,
                        'xUom': 'EA',
                        'yMinQty': 1,
                        'yUom': 'Colors',
                        'price': 0.0,
                        'discountCode': 'G',
                        'repeatPrice': 20.0,
                        'repeatDiscountCode': 'G',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }],
                    'chargesAppliesLTM':
                    False,
                    'chargesPerLocation':
                    0,
                    'chargesPerColor':
                    0
                }, {
                    'chargeId':
                    192,
                    'chargeName':
                    'Tariff Surcharge',
                    'chargeDescription':
                    'Tariff Surcharge',
                    'chargeType':
                    'Run',
                    'ChargePrice': [{
                        'xMinQty': 1,
                        'xUom': 'EA',
                        'yMinQty': 1,
                        'yUom': 'Other',
                        'price': 0.25,
                        'discountCode': 'Z',
                        'repeatPrice': 0.25,
                        'repeatDiscountCode': 'Z',
                        'priceEffectiveDate': '2019-01-01T00:00:00',
                        'priceExpiryDate': '2019-12-31T00:00:00'
                    }],
                    'chargesAppliesLTM':
                    False,
                    'chargesPerLocation':
                    0,
                    'chargesPerColor':
                    0
                }],
                'decorationUnitsIncluded':
                3,
                'decorationUnitsIncludedUom':
                'SQUARE INCHES',
                'decorationUnitsMax':
                25,
                'defaultDecoration':
                True,
                'leadTime':
                3,
                'rushLeadTime':
                1
            }],
            'decorationsIncluded':
            1,
            'defaultLocation':
            False,
            'maxDecoration':
            1,
            'minDecoration':
            1,
            'locationRank':
            1
        }],
        'productId':
        'BG344',
        'currency':
        'USD',
        'Fob': [{
            'fobId': '1',
            'fobPostalCode': '14072'
        }],
        'priceType':
        'Customer'
    }
}
