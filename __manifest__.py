# -*- coding: utf-8 -*-
{
    'name': 'Custom Currency Rate',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Tipo de cambio manual en compras y ventas',
    'description': '''
        Permite definir un tipo de cambio manual en presupuestos de compra y venta
        que se mantiene en todo el proceso hasta la factura.
    ''',
    'author': 'Surtecnica',
    'depends': ['purchase', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
