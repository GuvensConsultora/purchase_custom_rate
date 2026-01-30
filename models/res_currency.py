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

    def _convert(self, from_amount, to_currency, company, date, round=True):
        """
        Por qué: Sobrescribir conversión de montos para usar tipo de cambio manual
        Patrón: Template method - interceptamos la conversión completa
        Tip: Este es el método principal que convierte importes entre monedas
        """
        # Por qué: Si hay tipo de cambio manual en contexto, usarlo
        custom_rate = self._context.get('custom_currency_rate')

        if custom_rate and self != to_currency:
            # Por qué: Hacer conversión directa con la tasa manual
            # Patrón: from_amount * custom_rate = to_amount
            # Tip: Si custom_rate = 1000 (1 USD = 1000 ARS), entonces 100 USD * 1000 = 100,000 ARS
            to_amount = from_amount * custom_rate

            # Por qué: Redondear según configuración de moneda destino
            if round:
                to_amount = to_currency.round(to_amount)

            return to_amount

        # Por qué: Sino, usar el método estándar de conversión
        return super()._convert(
            from_amount, to_currency, company, date, round
        )
