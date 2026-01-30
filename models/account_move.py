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

    @api.depends(
        'currency_id',
        'company_id',
        'move_id.date',
        'move_id.use_custom_rate',
        'move_id.custom_currency_rate',
    )
    def _compute_currency_rate(self):
        """
        Por qué: Calcular el tipo de cambio correcto para cada línea
        Patrón: Computed field que prioriza el tipo de cambio manual
        Tip: Este método SÍ existe en Odoo 17 y es CRÍTICO para conversiones
        """
        for line in self:
            # Por qué: Si la factura tiene tipo de cambio manual, usarlo directamente
            if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
                line.currency_rate = line.move_id.custom_currency_rate
            else:
                # Por qué: Sino, delegar al cálculo estándar
                super(AccountMoveLine, line)._compute_currency_rate()

    @api.depends('amount_currency', 'currency_id', 'move_id.use_custom_rate', 'move_id.custom_currency_rate')
    def _compute_debit_credit(self):
        """
        Por qué: Recalcular débito/crédito usando el tipo de cambio manual
        Patrón: Override del método que calcula los importes en moneda de compañía
        Tip: Aquí es donde realmente se convierten los montos
        """
        for line in self:
            # Por qué: Si hay tipo de cambio manual, usar método _convert con contexto
            if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
                company_currency = line.move_id.company_id.currency_id

                if line.currency_id and line.currency_id != company_currency:
                    # Por qué: Usar método _convert con contexto para mantener consistencia
                    # Patrón: Delegamos a res.currency que ya tiene el override
                    balance = line.currency_id.with_context(
                        custom_currency_rate=line.move_id.custom_currency_rate
                    )._convert(
                        line.amount_currency,
                        company_currency,
                        line.move_id.company_id,
                        line.move_id.date or fields.Date.context_today(line),
                        round=True
                    )
                else:
                    balance = line.amount_currency

                # Por qué: Asignar a débito o crédito según el signo
                if balance > 0:
                    line.debit = balance
                    line.credit = 0
                else:
                    line.debit = 0
                    line.credit = -balance
            else:
                # Por qué: Sino, usar cálculo estándar de Odoo
                super(AccountMoveLine, line)._compute_debit_credit()

    @api.depends('debit', 'credit')
    def _compute_balance(self):
        """
        Por qué: Asegurar que balance sea consistente con debit/credit
        Patrón: Balance = debit - credit (siempre)
        """
        for line in self:
            line.balance = line.debit - line.credit
