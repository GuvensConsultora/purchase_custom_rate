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

    def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
        """
        Por qué: Asegurar que al recalcular líneas se use el tipo de cambio manual
        Patrón: Hook method - interceptamos recálculo de apuntes contables
        Tip: Este método se ejecuta cada vez que se modifican las líneas de factura
        """
        # Por qué: Inyectar tipo de cambio manual en contexto para conversiones
        if self.use_custom_rate and self.custom_currency_rate:
            self = self.with_context(
                custom_currency_rate=self.custom_currency_rate
            )

        return super()._recompute_dynamic_lines(
            recompute_all_taxes=recompute_all_taxes,
            recompute_tax_base_amount=recompute_tax_base_amount
        )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('currency_id', 'company_id', 'move_id.date')
    def _compute_currency_rate(self):
        """
        Por qué: Calcular y almacenar el tipo de cambio para cada línea
        Patrón: Computed field que prioriza el tipo de cambio manual
        Tip: Este campo es usado por Odoo para conversiones de moneda
        """
        for line in self:
            # Por qué: Si la factura tiene tipo de cambio manual, usarlo
            if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
                line.currency_rate = line.move_id.custom_currency_rate
            else:
                # Por qué: Sino, calcular tipo de cambio estándar
                super(AccountMoveLine, line)._compute_currency_rate()

    def _get_fields_onchange_balance_model(
        self, quantity, discount, amount_currency, move_type, currency, taxes, price_subtotal_before_discount, force_computation=False
    ):
        """
        Por qué: Sobrescribir cálculo de balance para usar tipo de cambio manual
        Patrón: Hook method - interceptamos conversión de moneda en apuntes contables
        Tip: Este método es llamado cuando se calculan los importes en moneda de la compañía
        """
        # Por qué: Si hay tipo de cambio manual, inyectarlo en el contexto
        if self.move_id.use_custom_rate and self.move_id.custom_currency_rate:
            self = self.with_context(
                custom_currency_rate=self.move_id.custom_currency_rate
            )

        return super()._get_fields_onchange_balance_model(
            quantity, discount, amount_currency, move_type, currency, taxes,
            price_subtotal_before_discount, force_computation
        )
