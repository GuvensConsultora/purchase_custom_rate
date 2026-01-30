# Purchase Custom Rate - Odoo 17.0

## Descripción General

Módulo para Odoo 17 Enterprise que permite definir un **tipo de cambio manual** en presupuestos de compra, independiente del tipo de cambio configurado en el sistema. Este tipo de cambio personalizado se mantiene a lo largo de todo el proceso de compra, desde el presupuesto hasta la factura.

---

## Tabla de Contenidos

1. [Funcionalidad](#funcionalidad)
2. [Casos de Uso](#casos-de-uso)
3. [Documentación Técnica](#documentación-técnica)
4. [Instalación](#instalación)
5. [Uso](#uso)
6. [Arquitectura del Módulo](#arquitectura-del-módulo)

---

## Funcionalidad

### Presupuestos de Compra (`purchase.order`)

#### Nuevos Campos
- **`use_custom_rate`** (Boolean): Checkbox para activar/desactivar el tipo de cambio manual
- **`custom_currency_rate`** (Float): Valor del tipo de cambio personalizado (6 decimales de precisión)

#### Comportamiento
1. **Pre-carga Automática**: Al seleccionar una moneda y fecha, el sistema pre-carga el tipo de cambio del sistema como sugerencia
2. **Visibilidad Condicional**: El campo de tasa solo es visible cuando se activa el checkbox
3. **Cálculos Personalizados**: Todos los montos se calculan usando la tasa manual definida
4. **Persistencia**: El tipo de cambio se mantiene durante todo el ciclo de vida del presupuesto

### Facturas de Proveedor (`account.move`)

#### Nuevos Campos
- **`use_custom_rate`** (Boolean): Heredado del presupuesto de compra
- **`custom_currency_rate`** (Float): Tasa heredada del presupuesto

#### Comportamiento
1. **Herencia Automática**: Al crear una factura desde un presupuesto, hereda automáticamente la configuración de tipo de cambio
2. **Campo de Solo Lectura**: Si la factura proviene de un presupuesto, el tipo de cambio es de solo lectura (evita inconsistencias)
3. **Facturas Directas**: Permite definir tipo de cambio manual en facturas creadas directamente (sin presupuesto)
4. **Visibilidad**: Solo visible en facturas de proveedor (`in_invoice`, `in_refund`)

---

## Casos de Uso

### Caso 1: Compra con Tipo de Cambio Acordado
**Escenario**: Un proveedor extranjero acuerda un tipo de cambio fijo para una compra.

```
1. Crear presupuesto de compra
2. Seleccionar USD como moneda
3. Activar "Usar Tipo de Cambio Manual"
4. Ingresar tasa acordada: 1.0500
5. Confirmar presupuesto
6. La factura se crea con la misma tasa (1.0500), no la del sistema
```

### Caso 2: Corrección de Tipo de Cambio
**Escenario**: El tipo de cambio del sistema no refleja el valor real de la transacción.

```
1. Presupuesto creado con tasa del sistema: 1.0480
2. Valor real de la transacción: 1.0520
3. Activar tipo de cambio manual y ajustar a 1.0520
4. Todos los cálculos se actualizan automáticamente
```

---

## Documentación Técnica

### Arquitectura del Módulo

```
purchase_custom_rate/
├── __init__.py                      # Inicialización del módulo
├── __manifest__.py                  # Metadata y dependencias
├── models/
│   ├── __init__.py
│   ├── purchase_order.py            # Extensión de purchase.order
│   └── account_move.py              # Extensión de account.move
├── views/
│   └── purchase_order_views.xml     # Vistas de interfaz
└── security/
    └── ir.model.access.csv          # Permisos de acceso
```

---

### Detalle de Funciones - `purchase_order.py`

#### 1. `_onchange_currency_rate(self)`

**Propósito**: Pre-cargar el tipo de cambio del sistema como valor inicial cuando se selecciona una moneda.

**Decorador**: `@api.onchange('currency_id', 'date_order')`

**Funcionamiento**:
```python
# Se ejecuta automáticamente cuando cambia currency_id o date_order
def _onchange_currency_rate(self):
    if self.currency_id and self.date_order:
        # Usa el método nativo _get_conversion_rate() de res.currency
        rate = self.currency_id._get_conversion_rate(
            self.currency_id,           # Moneda origen
            self.company_id.currency_id, # Moneda destino (moneda base)
            self.company_id,             # Compañía
            self.date_order              # Fecha para la tasa
        )
        if rate:
            self.custom_currency_rate = rate
```

**Integración con Odoo**:
- Utiliza el método estándar `_get_conversion_rate()` del modelo `res.currency`
- Se dispara automáticamente por el framework ORM de Odoo
- Proporciona un valor inicial sensato que el usuario puede modificar

---

#### 2. `_prepare_invoice(self)`

**Propósito**: Transferir la configuración de tipo de cambio manual del presupuesto a la factura que se crea.

**Patrón**: Template Method (sobrescribe método de clase padre)

**Funcionamiento**:
```python
def _prepare_invoice(self):
    # Primero llama al método padre para obtener valores base
    invoice_vals = super()._prepare_invoice()

    # Luego agrega/modifica valores específicos
    if self.use_custom_rate and self.custom_currency_rate:
        invoice_vals.update({
            'use_custom_rate': True,
            'custom_currency_rate': self.custom_currency_rate,
        })

    return invoice_vals
```

**Integración con Odoo**:
- `_prepare_invoice()` es un hook nativo de Odoo llamado por `action_create_invoice()`
- El método padre ya prepara ~40 campos estándar de la factura
- Nosotros solo agregamos los 2 campos adicionales sin romper la funcionalidad existente
- Este es el **patrón Template Method**: Odoo define el esqueleto del algoritmo, nosotros personalizamos pasos específicos

**Flujo Completo**:
```
Usuario hace clic en "Crear Factura"
    ↓
action_create_invoice() [método nativo de Odoo]
    ↓
_prepare_invoice() [nuestro método sobrescrito]
    ↓
super()._prepare_invoice() [llama método original]
    ↓
Agrega use_custom_rate y custom_currency_rate
    ↓
account.move.create(invoice_vals)
```

---

#### 3. `_get_currency_rate(self)`

**Propósito**: Sobrescribir el cálculo de tipo de cambio para que Odoo use nuestra tasa manual en lugar de la del sistema.

**Patrón**: Template Method + Strategy Pattern

**Funcionamiento**:
```python
def _get_currency_rate(self):
    self.ensure_one()  # Verifica que sea un solo registro

    # Si hay tipo de cambio manual activo, usarlo
    if self.use_custom_rate and self.custom_currency_rate:
        return self.custom_currency_rate

    # Sino, delegar al comportamiento estándar de Odoo
    return super()._get_currency_rate()
```

**Integración con Odoo**:
- Este método es llamado internamente por múltiples funciones de Odoo:
  - `_compute_tax_totals()`: Cálculo de impuestos
  - `_compute_amount()`: Cálculo de totales
  - Conversiones de moneda en líneas de pedido
- **No necesitamos modificar esos métodos** porque todos delegan a `_get_currency_rate()`
- Este es el **patrón Strategy**: cambiamos la estrategia de cálculo sin modificar los algoritmos que la usan

**Ejemplo de Uso Interno**:
```python
# En purchase.order.line._compute_amount() [método nativo de Odoo]
def _compute_amount(self):
    for line in self:
        # Odoo internamente llama a _get_currency_rate()
        rate = line.order_id._get_currency_rate()
        # Usa ese rate para convertir monedas
        price_in_base_currency = line.price_unit * rate
```

---

### Detalle de Funciones - `account_move.py`

#### 4. `_onchange_currency_rate(self)` (Account Move)

**Propósito**: Similar a purchase.order, pre-carga tipo de cambio en facturas directas.

**Diferencia clave**:
```python
# Solo pre-carga si NO viene de un presupuesto
if self.currency_id and self.invoice_date and not self.custom_currency_rate:
    rate = self.currency_id._get_conversion_rate(...)
    if rate:
        self.custom_currency_rate = rate
```

**Razón**: Si la factura viene de un presupuesto, `custom_currency_rate` ya está asignado por `_prepare_invoice()`. Solo queremos pre-cargar en facturas creadas manualmente.

---

#### 5. `_get_currency_rate(self)` (Account Move)

**Propósito**: Idéntico al de purchase.order, asegura que las facturas usen la tasa manual.

**Integración con Odoo**:
- Llamado por métodos nativos como:
  - `_compute_amount()`: Cálculo de líneas de factura
  - `_recompute_dynamic_lines()`: Recalculo de líneas dinámicas (impuestos, pagos)
  - `_compute_payments_widget_to_reconcile_info()`: Información de pagos

---

#### 6. `_get_invoice_in_payment_state(self)`

**Propósito**: Asegurar que los pagos también respeten el tipo de cambio manual.

**Funcionamiento**:
```python
def _get_invoice_in_payment_state(self):
    # Inyectar tipo de cambio en contexto si existe
    if self.use_custom_rate and self.custom_currency_rate:
        self = self.with_context(custom_rate=self.custom_currency_rate)

    return super()._get_invoice_in_payment_state()
```

**Integración con Odoo**:
- `with_context()` es un método del ORM de Odoo que crea una copia del recordset con contexto adicional
- El contexto es un diccionario que viaja a través de las llamadas de métodos
- Los métodos de pago pueden leer `self.env.context.get('custom_rate')` si lo necesitan

---

### Detalle de Funciones - Líneas (`purchase.order.line` y `account.move.line`)

#### 7. `_compute_amount(self)` (Purchase Order Line)

**Propósito**: Asegurar que los cálculos de líneas de presupuesto usen el tipo de cambio manual.

**Funcionamiento**:
```python
@api.depends('product_qty', 'price_unit', 'taxes_id')
def _compute_amount(self):
    for line in self:
        # Inyectar tipo de cambio manual en el contexto
        if line.order_id.use_custom_rate and line.order_id.custom_currency_rate:
            line = line.with_context(
                custom_rate=line.order_id.custom_currency_rate
            )

    return super(PurchaseOrderLine, self)._compute_amount()
```

**Integración con Odoo**:
- `@api.depends()` marca este campo como computed (calculado)
- Odoo automáticamente recalcula cuando cambian los campos dependientes
- El contexto viaja a través de la cadena de llamadas de `super()`

---

#### 8. `_compute_totals(self)` (Account Move Line)

**Propósito**: Idéntico al anterior, pero para líneas de factura.

**Patrón**: Decorator Pattern (envolvemos funcionalidad existente con contexto adicional)

---

## Integración con el ORM de Odoo

### Flujo de Datos Completo

```
1. Usuario crea presupuesto y activa tipo de cambio manual
   ↓
2. Campo use_custom_rate = True
   ↓
3. Al agregar líneas, _compute_amount() usa _get_currency_rate()
   ↓
4. _get_currency_rate() retorna custom_currency_rate
   ↓
5. Todos los cálculos usan la tasa manual
   ↓
6. Usuario confirma presupuesto
   ↓
7. Usuario crea factura
   ↓
8. action_create_invoice() llama _prepare_invoice()
   ↓
9. _prepare_invoice() copia use_custom_rate y custom_currency_rate
   ↓
10. Factura se crea con los mismos valores
   ↓
11. Cálculos de factura usan _get_currency_rate() de account.move
   ↓
12. Todo el proceso usa la tasa manual consistentemente
```

---

## Métodos Nativos de Odoo Utilizados

### `res.currency._get_conversion_rate()`
- **Propósito**: Obtener tipo de cambio entre dos monedas en una fecha específica
- **Uso**: Pre-cargar valor inicial del tipo de cambio

### `purchase.order._prepare_invoice()`
- **Propósito**: Preparar diccionario de valores para crear factura
- **Uso**: Hook para heredar tipo de cambio del presupuesto a la factura

### `purchase.order._get_currency_rate()`
- **Propósito**: Obtener tipo de cambio a usar en cálculos
- **Uso**: Sobrescrito para retornar tasa manual

### `account.move._get_invoice_in_payment_state()`
- **Propósito**: Calcular estado de pago de factura
- **Uso**: Inyectar contexto de tipo de cambio manual

### ORM Methods Utilizados
- `@api.onchange()`: Detectar cambios en campos y ejecutar lógica
- `@api.depends()`: Marcar campos calculados y sus dependencias
- `with_context()`: Inyectar datos en el contexto de ejecución
- `ensure_one()`: Verificar que se trabaja con un solo registro
- `super()`: Llamar método de clase padre

---

## Instalación

### Requisitos
- Odoo 17.0 Enterprise
- Módulos base: `purchase`, `account`

### Pasos

1. **Clonar el repositorio**:
```bash
cd /ruta/a/odoo/addons
git clone https://github.com/GuvensConsultora/purchase_custom_rate.git
```

2. **Reiniciar servicio de Odoo**:
```bash
sudo systemctl restart odoo
```

3. **Actualizar lista de aplicaciones**:
- Ir a Aplicaciones
- Quitar filtro "Aplicaciones"
- Actualizar lista de aplicaciones

4. **Instalar módulo**:
- Buscar "Purchase Custom Rate"
- Hacer clic en "Instalar"

---

## Uso

### Configurar Tipo de Cambio en Presupuesto

1. Ir a **Compras > Pedidos > Presupuestos**
2. Crear nuevo presupuesto
3. Seleccionar proveedor y moneda
4. Activar checkbox **"Tipo de Cambio Manual"**
5. El campo **"Tasa"** aparecerá con el tipo de cambio del sistema pre-cargado
6. Modificar la tasa según sea necesario
7. Agregar líneas de producto

**Nota**: Todos los cálculos (subtotales, impuestos, total) usarán la tasa manual definida.

### Verificar Herencia en Factura

1. Confirmar el presupuesto
2. Hacer clic en **"Crear Factura"**
3. Verificar que:
   - El checkbox **"Tipo de Cambio Manual"** está activado
   - El campo **"Tasa"** muestra el mismo valor del presupuesto
   - El campo está en **solo lectura** (readonly)

### Factura Directa con Tipo de Cambio Manual

1. Ir a **Contabilidad > Proveedores > Facturas**
2. Crear nueva factura
3. Activar **"Tipo de Cambio Manual"**
4. Definir la tasa deseada
5. Agregar líneas

---

## Patrones de Diseño Utilizados

### Template Method Pattern
- **Dónde**: `_prepare_invoice()`, `_get_currency_rate()`
- **Por qué**: Permite modificar pasos específicos del algoritmo sin reescribir todo el flujo

### Strategy Pattern
- **Dónde**: `_get_currency_rate()`
- **Por qué**: Cambia la estrategia de cálculo de tipo de cambio dinámicamente

### Decorator Pattern
- **Dónde**: `_compute_amount()`, `_compute_totals()`
- **Por qué**: Envuelve funcionalidad existente agregando contexto adicional

### Hook Pattern
- **Dónde**: Todos los métodos sobrescritos
- **Por qué**: Odoo está diseñado con hooks para permitir extensiones sin modificar código base

---

## Ventajas Técnicas

1. **No Invasivo**: No modifica código base de Odoo, solo extiende
2. **Compatible**: Usa hooks nativos de Odoo, alta compatibilidad con otros módulos
3. **Mantenible**: Código claro con comentarios explicativos
4. **Escalable**: Fácil de extender para otros modelos (ej. ventas)
5. **Robusto**: Validaciones y valores por defecto seguros

---

## Limitaciones Conocidas

1. **Conversiones Múltiples**: Si hay múltiples monedas en un mismo presupuesto, solo aplica un tipo de cambio
2. **Reportes Personalizados**: Reportes custom pueden necesitar adaptación para respetar el tipo de cambio manual
3. **Integraciones**: Módulos de terceros que hagan sus propios cálculos de moneda pueden no respetar la tasa manual

---

## Soporte y Contribuciones

**Repositorio**: https://github.com/GuvensConsultora/purchase_custom_rate

Para reportar bugs o solicitar features, crear un issue en GitHub.

---

## Licencia

LGPL-3

---

## Autor

**Surtecnica**

Desarrollado con asistencia de Claude Sonnet 4.5
