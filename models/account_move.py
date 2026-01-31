# -*- coding: utf-8 -*-
from odoo import models, fields, api
from markupsafe import Markup


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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Por qué: Agregar mensaje en chatter cuando se usa tipo de cambio manual
        Patrón: Hook method - interceptamos la creación de factura
        """
        moves = super().create(vals_list)

        for move in moves:
            # Por qué: Si la factura usa tipo de cambio manual, notificar en chatter
            # Tip: Ahora aplica a facturas de compra Y venta
            if move.use_custom_rate and move.custom_currency_rate and move.move_type in ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']:
                # Por qué: Usar Markup para que Odoo renderice el HTML correctamente
                html_message = Markup(f"""
<div style="padding: 12px; background-color: #f0f9ff; border-left: 4px solid #3b82f6; border-radius: 4px; margin: 8px 0;">
    <div style="display: flex; align-items: center; margin-bottom: 8px;">
        <span style="font-size: 20px; margin-right: 8px;">💱</span>
        <strong style="color: #1e40af; font-size: 14px;">Tipo de Cambio Manual Aplicado</strong>
    </div>
    <div style="margin-left: 28px; color: #374151;">
        <div style="margin: 6px 0;">
            <span style="color: #6b7280;">Tasa:</span>
            <strong style="color: #111827; font-size: 16px; margin-left: 8px;">{move.custom_currency_rate:,.6f}</strong>
        </div>
        <div style="margin: 6px 0;">
            <span style="color: #6b7280;">Conversión:</span>
            <strong style="color: #111827; margin-left: 8px;">{move.currency_id.name} → {move.company_id.currency_id.name}</strong>
        </div>
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #dbeafe; color: #6b7280; font-size: 12px; font-style: italic;">
            Todos los apuntes contables fueron calculados con esta tasa.
        </div>
    </div>
</div>
                """)

                move.message_post(
                    body=html_message,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

        return moves

    @api.onchange('currency_id', 'invoice_date', 'use_custom_rate')
    def _onchange_currency_rate(self):
        """
        Por qué: SIEMPRE mostrar el tipo de cambio del sistema
        Patrón: Campo siempre visible con valor, readonly controla edición
        Tip: Si use_custom_rate=False → actualiza automáticamente; si True → solo carga inicial
        """
        if self.currency_id and self.invoice_date:
            rate = self.currency_id._get_conversion_rate(
                self.currency_id,
                self.company_id.currency_id,
                self.company_id,
                self.invoice_date
            )

            # Por qué: Si NO usa manual → SIEMPRE actualizar con tasa del sistema
            # Si SÍ usa manual → solo actualizar si campo vacío (primera vez o heredado)
            if not self.use_custom_rate:
                self.custom_currency_rate = rate
            elif not self.custom_currency_rate:
                self.custom_currency_rate = rate

    def _get_currency_rate(self):
        """
        Por qué: SIEMPRE usar custom_currency_rate (que ahora siempre tiene valor)
        Patrón: Campo use_custom_rate solo controla edición en vista, no lógica aquí
        Tip: Simplificación - el campo siempre contiene la tasa correcta
        """
        self.ensure_one()

        # Por qué: SIEMPRE usar custom_currency_rate (ya sea manual o automático)
        if self.custom_currency_rate:
            return self.custom_currency_rate

        # Por qué: Sino, usar comportamiento estándar de Odoo
        return super()._get_currency_rate()

    def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
        """
        Por qué: Asegurar que al recalcular líneas se use el tipo de cambio
        Patrón: Hook method - interceptamos recálculo de apuntes contables
        Tip: Este método se ejecuta cada vez que se modifican las líneas de factura
        """
        # Por qué: Inyectar tipo de cambio en contexto para conversiones
        if self.custom_currency_rate:
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
            # Por qué: Si la factura tiene tipo de cambio (manual o automático), usarlo
            if line.move_id.custom_currency_rate:
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
            # Por qué: Si hay tipo de cambio (manual o automático), usar método _convert con contexto
            if line.move_id.custom_currency_rate:
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
