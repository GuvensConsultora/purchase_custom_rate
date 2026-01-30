# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Por qué: Permitir que las facturas también tengan tipo de cambio manual
    # Patrón: Herencia de funcionalidad desde purchase.order
    custom_currency_rate = fields.Float(
        string='Tipo de Cambio Manual',
        digits=(12, 6),
        help='Tipo de cambio heredado del presupuesto de compra'
    )

    use_custom_rate = fields.Boolean(
        string='Usar Tipo de Cambio Manual',
        default=False,
        help='Activar para usar el tipo de cambio manual definido'
    )

    @api.onchange('currency_id', 'invoice_date')
    def _onchange_currency_rate(self):
        """
        Por qué: Pre-cargar tipo de cambio del sistema como sugerencia
        Tip: Solo si no viene heredado de un presupuesto
        """
        if self.currency_id and self.invoice_date and not self.custom_currency_rate:
            rate = self.currency_id._get_conversion_rate(
                self.currency_id,
                self.company_id.currency_id,
                self.company_id,
                self.invoice_date
            )
            if rate:
                self.custom_currency_rate = rate

    def _get_currency_rate(self):
        """
        Por qué: Sobrescribir tipo de cambio en facturas igual que en compras
        Patrón: Mismo patrón que en purchase.order para consistencia
        """
        self.ensure_one()

        # Por qué: Si hay tipo de cambio manual, tiene prioridad
        if self.use_custom_rate and self.custom_currency_rate:
            return self.custom_currency_rate

        # Por qué: Sino, usar comportamiento estándar de Odoo
        return super()._get_currency_rate()

    @api.model
    def _get_invoice_in_payment_state(self):
        """
        Por qué: Asegurar que los pagos también respeten el tipo de cambio manual
        Patrón: Hook method para interceptar flujo de pagos
        """
        # Por qué: Inyectar tipo de cambio en contexto si existe
        if self.use_custom_rate and self.custom_currency_rate:
            self = self.with_context(custom_rate=self.custom_currency_rate)

        return super()._get_invoice_in_payment_state()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('quantity', 'price_unit', 'tax_ids', 'discount')
    def _compute_totals(self):
        """
        Por qué: Asegurar que las líneas de factura usen el tipo de cambio manual
        Patrón: Computed field override con contexto personalizado
        """
        for line in self:
            # Por qué: Heredar tipo de cambio del encabezado de factura
            if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
                line = line.with_context(
                    custom_rate=line.move_id.custom_currency_rate
                )

        return super(AccountMoveLine, self)._compute_totals()
