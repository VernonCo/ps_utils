import re

class Tracking_No():
    def __init__(self, trk_no, carrier='', shipmentMethod=''):
        self.trk_no = trk_no
        UPS = "http://wwwapps.ups.com/etracking/tracking.cgi?AcceptUPSLicenseAgreement=yes&TypeOfInquiryNumber=T&InquiryNumber1="
        FEDEX ="https://www.fedex.com/apps/fedextrack/?action=track&cntry_code=us_english&tracknumbers="
        USPS = "https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1="

        if carrier:
            carrier1 = carrier.lower()
        else:
            carrier1 = ''
        if shipmentMethod:
            shipmentMethod1 = shipmentMethod.lower()
        else:
            shipmentMethod1 = ''

        carrierdata=" (Not Specified)"

        # determine carrier link by carrier or shipmentMethod given
        if carrier1 != "":
            carrierdata = " (" + carrier + ")"
        else:
            carrierdata = ''
        if carrier1 == 'ups (usa)' or carrier1 == 'ups' or carrier1 == 'ups (us)':
            clink = UPS
        elif carrier1 == "" and len(shipmentMethod) > 3 and shipmentMethod[0:3] == 'ups':
            clink = UPS
            carrierdata =" (" + shipmentMethod1 + ")"
        elif carrier1 == 'fedex (usa)' or carrier1 == 'fedex' or  carrier1 == 'fedex (us)':
            clink = FEDEX
        elif carrier1 == '' and len(shipmentMethod) > 6 and  shipmentMethod[0, 5] =='fedex':
            clink = FEDEX
            carrierdata =" (" + shipmentMethod1 + ")"
        elif carrier1 == 'us postal service':
            clink = USPS
        else: clink = ""

        # if carrier is not determined, use the trk_no to determine carrier
        if clink == "":
            if self.UPS_match():
                clink = UPS
            elif self.FED_match():
                clink = FEDEX
            elif self.USPS_match():
                clink = USPS

        if clink != "":
            self.trdata = "<a href='" + clink + "" + trk_no + "' target='_blank'>" + trk_no + "</a>" + carrierdata
        else:
            self.trdata=trk_no + "" + carrierdata
        if trk_no == "" : self.trdata = ""

    def link(self):
        return self.trdata

    def valid(self):
        """
            check if is a tracking number self.trk_no
            returns tracking no or null
        """
        valid = False
        if self.UPS_match():
            # covers UPS
            valid = True
        elif self.FED_match():
            # covers USPS, and FEDEX
            valid = True
        elif self.USPS_match():
            #covers some flavors of USPS
            valid = True
        return valid

    def UPS_match(self):
        ups_pattern = [
            '^(1Z)[0-9A-Z]{16}$',
            '^(T)+[0-9A-Z]{10}$',
            '^[0-9]{9}$',
            '^[0-9]{26}$'
        ]
        ups= "(" + ")|(".join(ups_pattern) + ")"
        if re.match(ups, self.trk_no) != None:
            return True

    def FED_match(self):
        fedex_pattern = [
            '^[0-9]{20}$',
            '^[0-9]{15}$',
            '^[0-9]{12}$',
            '^[0-9]{22}$'
        ]
        fedex = "(" + ")|(".join(fedex_pattern) + ")"
        if re.match(fedex, self.trk_no) != None:
            return True

    def USPS_match(self):
        usps_pattern = [
            '^(94|93|92|94|95)[0-9]{20}$',
            '^(94|93|92|94|95)[0-9]{22}$',
            '^(70|14|23|03)[0-9]{14}$',
            '^(M0|82)[0-9]{8}$',
            '^([A-Z]{2})[0-9]{9}([A-Z]{2})$'
        ]
        usps = "(" + ")|(".join(usps_pattern) + ")"
        if re.match(usps, self.trk_no) != None:
            return True
