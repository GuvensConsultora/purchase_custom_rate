# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Por qué: Permitir definir tipo de cambio manual independiente del sistema
    # Patrón: Override de comportamiento estándar de Odoo
    custom_currency_rate = fields.Float(
        string='Tipo de Cambio Manual',
        digits=(12, 6),
        help='Tipo de cambio a utilizar en lugar del tipo de cambio del sistema'
    )

    use_custom_rate = fields.Boolean(
        string='Usar Tipo de Cambio Manual',
        default=False,
        help='Activar para usar el tipo de cambio manual definido'
    )

    @api.onchange('currency_id', 'date_order')
    def _onchange_currency_rate(self):
        """
        Por qué: Pre-cargar el tipo de cambio del sistema como sugerencia
        Tip: El usuario puede modificarlo después si usa tipo de cambio manual
        """
        if self.currency_id and self.date_order:
            # Por qué: Obtener tasa actual del sistema como base
            rate = self.currency_id._get_conversion_rate(
                self.currency_id,
                self.company_id.currency_id,
                self.company_id,
                self.date_order
            )
            if rate:
                self.custom_currency_rate = rate

    def _prepare_invoice(self):
        """
        Por qué: Heredar tipo de cambio manual a la factura generada
        Patrón: Hook method - interceptamos la creación de factura
        """
        invoice_vals = super()._prepare_invoice()

        # Por qué: Transferir configuración de tipo de cambio manual a factura
        if self.use_custom_rate and self.custom_currency_rate:
            invoice_vals.update({
                'use_custom_rate': True,
                'custom_currency_rate': self.custom_currency_rate,
            })

        return invoice_vals

    def _get_currency_rate(self):
        """
        Por qué: Sobrescribir método que calcula el tipo de cambio
        Patrón: Template method - cambiamos el cálculo base
        Tip: Este método es usado internamente por Odoo para conversiones
        """
        self.ensure_one()

        # Por qué: Si hay tipo de cambio manual activo, usarlo
        if self.use_custom_rate and self.custom_currency_rate:
            return self.custom_currency_rate

        # Por qué: Sino, delegar al comportamiento estándar de Odoo
        return super()._get_currency_rate()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        """
        Por qué: Asegurar que los cálculos usen el tipo de cambio manual
        Patrón: Computed field override para inyectar contexto
        """
        for line in self:
            # Por qué: Inyectar tipo de cambio manual en el contexto de cálculo
            if line.order_id.use_custom_rate and line.order_id.custom_currency_rate:
                # Tip: with_context crea una copia temporal con datos extra
                line = line.with_context(
                    custom_rate=line.order_id.custom_currency_rate
                )

        return super(PurchaseOrderLine, self)._compute_amount()
