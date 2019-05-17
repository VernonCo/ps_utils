from flask_appbuilder.fieldwidgets import BS3TextFieldWidget
from flask_appbuilder.forms import DynamicForm
from wtforms import StringField, SelectField, SubmitField
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

    field1 = QuerySelectField(
        u"Supplier", get_label=u'company_name', query_factory=companyList( "Inventory" ), validators=[DataRequired("Please Select Supplier.")]
    )
    field2 = StringField(
        ("Product SKU"),
        description=("Enter the SKU for the Item you want to check for inventory."),
        validators=[DataRequired("Please enter SKU.")],
        widget=BS3TextFieldWidget()
    )
    field3 = SelectField(
        ("Service"), choices=[('','-- Select One --'),('getFilterValues', 'Get Filters'),('getInventoryLevels', 'Get Results')], validators=[DataRequired("Please select service.")],
        description=("Enter the desired service call."),
    )
    field4 = SelectField(
        ("Return Type"), choices=[('','-- Select One --'),('json', 'Return As JSON'),('page', 'Return As Table')],
        validators=[DataRequired("Please select return type.")]
    )
