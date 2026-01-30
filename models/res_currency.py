# -*- coding: utf-8 -*-
from odoo import models, api


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company, date):
        """
        Por qué: Sobrescribir cálculo de tipo de cambio para priorizar el manual
        Patrón: Template method - interceptamos el cálculo base de conversión
        Tip: Este método es usado por Odoo en TODAS las conversiones de moneda
        """
        # Por qué: Si hay tipo de cambio manual en contexto, usarlo
        # Patrón: Context-aware behavior - el contexto modifica el comportamiento
        custom_rate = self._context.get('custom_currency_rate')
        if custom_rate:
            return custom_rate

        # Por qué: Sino, usar el cálculo estándar del sistema
        return super()._get_conversion_rate(
            from_currency, to_currency, company, date
        )
