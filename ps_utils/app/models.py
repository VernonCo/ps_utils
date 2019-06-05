from flask_appbuilder import Model
from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from flask_appbuilder.models.mixins import AuditMixin

"""

You can use the extra Flask-AppBuilder fields and Mixin's

AuditMixin will add automatic timestamp of created and modified by who


"""
class Company(Model, AuditMixin):
    """ model of companies and their service _urls """
    id = Column(Integer, primary_key=True)
    erp_id = Column(Integer, nullable=True)  # may have multiple accounts for ps_id
    ps_id =  Column(String(255), unique=True, nullable=False)
    company_name =  Column(String(255))  # may have multiple names in erp for for ps_id, but will have at least one to go with ps_id
    user_name =  Column(String(150), nullable=True)
    password =  Column(String(150), nullable=True)
    inventory_url =  Column(String(255), nullable=True)
    inventory_wsdl =  Column(String(255), nullable=True)
    inventory_version =  Column(String(564), default='1.2.1')
    inventory_urlV2 =  Column(String(255), nullable=True)
    inventory_wsdlV2 =  Column(String(255), nullable=True)
    inventory_versionV2 =  Column(String(564), default='2.0.0')
    media_url =  Column(String(255), nullable=True)
    media_wsdl =  Column(String(255), nullable=True)
    media_version =  Column(String(564), default='1.0.0')
    order_url =  Column(String(255), nullable=True)
    order_wsdl =  Column(String(255), nullable=True)
    order_version =  Column(String(564), default='1.0.0')
    po_url =  Column(String(255), nullable=True)
    po_wsdl =  Column(String(255), nullable=True)
    po_version =  Column(String(564), default='1.0.0')
    produc_url =  Column(String(255), nullable=True)
    product_wsdl =  Column(String(255), nullable=True)
    produc_vVersion =  Column(String(564), default='1.0.0')
    price_url =  Column(String(255), nullable=True)
    price_wsdl =  Column(String(255), nullable=True)
    price_version =  Column(String(564), default='1.0.0')
    shipping_url =  Column(String(255), nullable=True)
    shipping_wsdl =  Column(String(255), nullable=True)
    shipping_version =  Column(String(564), default='1.0.0')
    live_inventory = Column(Integer, default=0)
    live_media = Column(Integer, default=0)
    live_order = Column(Integer, default=0)
    live_po = Column(Integer, default=0)
    live_pricing = Column(Integer, default=0)
    live_product = Column(Integer, default=0)
    live_shipping = Column(Integer, default=0)
    invoice_url =  Column(String(255), nullable=True)
    invoice_wsdl =  Column(String(255), nullable=True)
    invoice_version =  Column(String(564), default='0.1.0')

    def __repr__(self):
        return self.company_name
