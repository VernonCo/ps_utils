import re

class Tracking_No():
    def __init__(self, trk_no, carrier='', shipmentMethod=''):
        self.trk_no = trk_no
        UPS = "http://wwwapps.ups.com/etracking/tracking.cgi?AcceptUPSLicenseAgreement=yes&TypeOfInquiryNumber=T&InquiryNumber1="
        FEDEX ="https://www.fedex.com/apps/fedextrack/?action=track&cntry_code=us_english&tracknumbers="
        USPS = "https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1="

        carrier1 = carrier.lower()
        shipmentMethod1 = shipmentMethod.lower()

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
        if self.UPS_match():
            # covers UPS
            return self.trk_no
        elif self.FED_match():
            # covers USPS, and FEDEX
            return self.trk_no
        elif self.USPS_match():
            #covers some flavors of USPS
            return self.trk_no
        else:
            return None

    def UPS_match(self):
        return re.match("\b(1Z ?[0-9A-Z]{3} ?[0-9A-Z]{3} ?[0-9A-Z]{2} ?[0-9A-Z]{4} ?[0-9A-Z]{3} ?[0-9A-Z]|[\dT]\d\d\d ?\d\d\d\d ?\d\d\d)\b", self.trk_no)

    def FED_match(self):
        if re.match("(\b\d{22}\b)|(\b\d{20}\b)|(\b\d{15}\b)|(\b\d{12}\b)", self.trk_no) \
            or re.match("(\b96\d{20}\b)|(\b\d{15}\b)|(\b\d{12}\b)", self.trk_no) \
            or re.match("^[0-9]{15} | ^[0-9]{12}", self.trk_no) \
            or re.match("\b((98\d\d\d\d\d?\d\d\d\d|98\d\d) ?\d\d\d\d ?\d\d\d\d( ?\d\d\d)?)\b", self.trk_no):
            return True
        else: return False

    def USPS_match(self):
        if re.match("\b[A-Z]{2}\d{9}[A-Z]{2}\b", self.trk_no) \
            or re.match("^[0-9]{22} | ^[0-9]{20} | ^[A-Z]{2} ?\d\d\d ?\d\d\d ?\d\d\d ?US", self.trk_no):
            return True
        else: return False
