# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Por qué: Permitir definir tipo de cambio manual en ventas
    # Patrón: Misma funcionalidad que en purchase.order para consistencia
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

    @api.onchange('currency_id', 'date_order', 'use_custom_rate')
    def _onchange_currency_rate(self):
        """
        Por qué: SIEMPRE mostrar el tipo de cambio del sistema
        Patrón: Campo siempre visible con valor, readonly controla edición
        Tip: Si use_custom_rate=False → actualiza automáticamente; si True → solo carga inicial
        """
        if self.currency_id and self.date_order:
            # Por qué: Obtener tasa actual del sistema
            rate = self.currency_id._get_conversion_rate(
                self.currency_id,
                self.company_id.currency_id,
                self.company_id,
                self.date_order
            )

            # Por qué: Si NO usa manual → SIEMPRE actualizar con tasa del sistema
            # Si SÍ usa manual → solo actualizar si campo vacío (primera vez)
            if not self.use_custom_rate:
                self.custom_currency_rate = rate
            elif not self.custom_currency_rate:
                self.custom_currency_rate = rate

    def _prepare_invoice(self):
        """
        Por qué: Heredar tipo de cambio manual a la factura de cliente
        Patrón: Hook method - interceptamos la creación de factura
        """
        invoice_vals = super()._prepare_invoice()

        # Por qué: Transferir configuración de tipo de cambio a factura
        if self.use_custom_rate and self.custom_currency_rate:
            invoice_vals.update({
                'use_custom_rate': True,
                'custom_currency_rate': self.custom_currency_rate,
            })

        return invoice_vals

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

        # Por qué: Fallback al comportamiento estándar solo si no hay valor
        return super()._get_currency_rate()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_uom_qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Por qué: Asegurar que los cálculos usen el tipo de cambio (manual o automático)
        Patrón: Computed field override para inyectar contexto
        Tip: Ya no verificamos use_custom_rate, siempre usamos custom_currency_rate
        """
        for line in self:
            # Por qué: Inyectar tipo de cambio en el contexto de cálculo
            if line.order_id.custom_currency_rate:
                # Tip: with_context crea una copia temporal con datos extra
                line = line.with_context(
                    custom_rate=line.order_id.custom_currency_rate
                )

        return super(SaleOrderLine, self)._compute_amount()
