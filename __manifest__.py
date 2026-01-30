# -*- coding: utf-8 -*-
{
    'name': 'Purchase Custom Rate',
    'version': '17.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Tipo de cambio manual en presupuestos de compra',
    'description': '''
        Permite definir un tipo de cambio manual en presupuestos de compra
        que se mantiene en todo el proceso hasta la factura.
    ''',
    'author': 'Surtecnica',
    'depends': ['purchase', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
