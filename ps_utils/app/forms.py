from flask_appbuilder.fieldwidgets import BS3TextFieldWidget, DatePickerWidget
from flask_appbuilder.forms import DynamicForm
from wtforms import StringField, SelectField, SubmitField, DateField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired
from . import db
from .models import Company


def companyList(service):
    serviceList = dict(Inventory=Company.inventory_url, Shipping=Company.shipping_url, Order=Company.order_url)
    url = serviceList[service]
    return lambda: db.session.query(Company).filter(Company.user_name!=None,url!=None)
    # try:
    # return QuerySelectField(
    #     u"Supplier", get_label=u'company_name', query_factory=Company.companyList( service ), validators=[DataRequired("Please Select Supplier.")]
    # )
    # except:
    #     #fails on startup becasue Company table does not yet exist in database from import into view.py
    #     return StringField(u'Suppliers',description='Please update Companies and add credentials First!')


class InventoryForm(DynamicForm):
    # get companies for dropdown

    companyID = QuerySelectField(
        u"Supplier", get_label=u'company_name', query_factory=companyList( "Inventory" ), validators=[DataRequired("Please Select Supplier.")]
    )
    productID = StringField(
        ("Product SKU"),
        description=("Enter the SKU for the Item you want to check for inventory."),
        validators=[DataRequired("Please enter SKU.")],
        widget=BS3TextFieldWidget()
    )
    serviceType = SelectField(
        ("Service"), choices=[('','-- Select One --'),('getFilterValues', 'Get Filters'),('getInventoryLevels', 'Get Results')], validators=[DataRequired("Please select service.")],
        description=("Enter the desired service call."),
    )
    returnType = SelectField(
        ("Return Type"), choices=[('','-- Select One --'),('json', 'Return As JSON'),('page', 'Return As Table')],
        validators=[DataRequired("Please select return type.")]
    )
    serviceVersion = SelectField(
        ("Service Version"), choices=[('V1', '1.x.x'),('V2', '2.X.x')], default='V1',
        validators=[DataRequired("Please select service version. Defaults to 1.x.x")]
    )



class OrderStatusForm(DynamicForm):
    # get companies for dropdown

    companyID = QuerySelectField(
        u"Supplier", get_label=u'company_name', query_factory=companyList( "Order" ), validators=[DataRequired("Please Select Supplier.")]
    )
    queryType = SelectField(
        ("Query Type"),
        choices=[('','-- Select One --'),('1', 'PO Search'),('2','SO Search'), ('3', 'Last Update Search'),('4','All Open Orders')],
        validators=[DataRequired("Please select Query Type.")],
        description=("Enter the desired filter. PO->Customer#, SO->Vendor#"),
    )
    refNum = StringField(
        ("Reference Number"),
        description=("Enter the PO or SO # to search for order status."),
        widget=BS3TextFieldWidget()
    )
    refDate = DateField(
        ("Begin Date"),
        description=("Enter the PO or SO # to search for order status."),
        widget=DatePickerWidget()
    )
    returnType = SelectField(
        ("Return Type"), choices=[('','-- Select One --'),('json', 'Return As JSON'),('page', 'Return As Table')],
        validators=[DataRequired("Please select return type.")]
    )
