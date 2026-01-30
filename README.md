# Purchase Custom Rate

## Descripción
Módulo para Odoo 17 Enterprise que permite definir un tipo de cambio manual en presupuestos de compra, independiente del tipo de cambio configurado en el sistema.

## Funcionalidad

### Presupuestos de Compra
- Campo `Usar Tipo de Cambio Manual`: Checkbox para activar la función
- Campo `Tasa`: Tipo de cambio manual (visible solo si está activado)
- Pre-carga automática del tipo de cambio del sistema como sugerencia
- El tipo de cambio manual se usa en todos los cálculos del presupuesto

### Facturas de Proveedor
- Hereda automáticamente el tipo de cambio del presupuesto de compra
- Campo de solo lectura si viene de un presupuesto (para evitar inconsistencias)
- Permite definir tipo de cambio manual en facturas directas

## Instalación
1. Copiar el módulo en la carpeta de addons de Odoo
2. Actualizar lista de aplicaciones
3. Instalar "Purchase Custom Rate"

## Uso
1. Crear un presupuesto de compra
2. Seleccionar la moneda
3. Activar "Tipo de Cambio Manual"
4. Ingresar la tasa deseada
5. Confirmar el presupuesto
6. Al crear la factura, heredará automáticamente el tipo de cambio manual

## Notas Técnicas
- Sobrescribe `_get_currency_rate()` en purchase.order y account.move
- Utiliza `_prepare_invoice()` para heredar valores
- Compatible con flujo estándar de Odoo
