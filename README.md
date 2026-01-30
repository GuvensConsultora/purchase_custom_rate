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

#### Posicionamiento en Vista
Los campos se posicionan **antes de `l10n_latam_document_type_id`** (Tipo de Documento) para mejor UX:

```xml
<xpath expr="//field[@name='l10n_latam_document_type_id']" position="before">
    <field name="purchase_id" invisible="1"/>  <!-- Necesario para modifiers -->
    <field name="use_custom_rate" widget="boolean_toggle"/>
    <field name="custom_currency_rate" invisible="not use_custom_rate"/>
</xpath>
```

**Por qué antes del Tipo de Documento**:
- Agrupación lógica: moneda y tipo de cambio están relacionados
- Mejor flujo visual: el usuario define moneda → tipo de cambio → documento
- Evita campos dispersos en el formulario

#### Comportamiento
1. **Herencia Automática**: Al crear una factura desde un presupuesto, hereda automáticamente la configuración de tipo de cambio
2. **Campo de Solo Lectura**: Si la factura proviene de un presupuesto, el tipo de cambio es de solo lectura (evita inconsistencias)
3. **Facturas Directas**: Permite definir tipo de cambio manual en facturas creadas directamente (sin presupuesto)
4. **Visibilidad**: Solo visible en facturas de proveedor (`in_invoice`, `in_refund`)
5. **Declaración de `purchase_id`**: Se declara invisible para poder usarlo en el modifier `readonly="purchase_id"` sin errores de permisos

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
│   ├── account_move.py              # Extensión de account.move
│   └── res_currency.py              # Extensión de res.currency (conversiones)
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

## Cálculo de Apuntes Contables

### Problema a Resolver

Cuando se crea una factura en moneda extranjera, Odoo debe generar apuntes contables (journal entries) que conviertan los importes a la moneda de la compañía. **El desafío es asegurar que esta conversión use el tipo de cambio manual, no el del sistema.**

### Arquitectura de la Solución

La solución tiene **3 capas** que trabajan juntas:

```
┌─────────────────────────────────────────────────────────┐
│  1. CAPA DE VISTA (account.move)                        │
│     - Posiciona campos antes de l10n_latam_document_type_id│
│     - Inyecta contexto en _recompute_dynamic_lines()   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  2. CAPA DE LÍNEAS (account.move.line)                  │
│     - _compute_currency_rate(): Almacena tasa manual    │
│     - _compute_debit_credit(): Calcula balance          │
│     - _compute_balance(): Consistencia debit - credit   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  3. CAPA DE CONVERSIÓN (res.currency)                   │
│     - _get_conversion_rate(): Retorna tasa manual       │
│     - _convert(): Convierte montos con tasa manual      │
└─────────────────────────────────────────────────────────┘
```

---

### Detalle de Funciones - `res_currency.py`

#### 9. `_get_conversion_rate(self, from_currency, to_currency, company, date)`

**Propósito**: Interceptar TODAS las solicitudes de tipo de cambio en Odoo.

**Funcionamiento**:
```python
def _get_conversion_rate(self, from_currency, to_currency, company, date):
    # Por qué: Verificar si hay tipo de cambio manual en el contexto
    custom_rate = self._context.get('custom_currency_rate')

    if custom_rate:
        return custom_rate  # Usar tasa manual

    # Sino, usar cálculo estándar del sistema
    return super()._get_conversion_rate(from_currency, to_currency, company, date)
```

**Integración**:
- **Contexto**: La tasa manual viaja en `self._context['custom_currency_rate']`
- **Fallback**: Si NO hay tasa manual → usa tipo de cambio del sistema ✓
- **Alcance**: Afecta a TODOS los módulos que conviertan moneda

---

#### 10. `_convert(self, from_amount, to_currency, company, date, round=True)`

**Propósito**: Convertir importes entre monedas usando la tasa manual.

**Funcionamiento**:
```python
def _convert(self, from_amount, to_currency, company, date, round=True):
    custom_rate = self._context.get('custom_currency_rate')

    if custom_rate and self != to_currency:
        # Fórmula: from_amount * custom_rate = to_amount
        # Ejemplo: 100 USD * 1000 = 100,000 ARS
        to_amount = from_amount * custom_rate

        if round:
            to_amount = to_currency.round(to_amount)

        return to_amount

    # Fallback: usar método estándar
    return super()._convert(from_amount, to_currency, company, date, round)
```

**Ejemplo Real**:
```
Factura de compra:
  - Moneda: USD
  - Monto: 100.00 USD
  - Tipo de cambio manual: 1000 (1 USD = 1000 ARS)
  - Moneda de compañía: ARS

Cálculo:
  to_amount = 100.00 * 1000 = 100,000.00 ARS

Apunte contable generado:
  Debe:  100,000.00 ARS (Gastos)
  Haber: 100,000.00 ARS (Cuentas por Pagar)
```

---

### Detalle de Funciones - Actualización de `account_move.py`

#### 11. `_recompute_dynamic_lines(self, recompute_all_taxes, recompute_tax_base_amount)`

**Propósito**: Inyectar el tipo de cambio manual en el contexto cuando se recalculan líneas.

**Cuándo se ejecuta**:
- Al guardar la factura
- Al modificar líneas
- Al calcular impuestos
- Al validar la factura

**Funcionamiento**:
```python
def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
    if self.use_custom_rate and self.custom_currency_rate:
        # Inyectar tasa en contexto para que viaje a todos los métodos
        self = self.with_context(custom_currency_rate=self.custom_currency_rate)

    return super()._recompute_dynamic_lines(
        recompute_all_taxes=recompute_all_taxes,
        recompute_tax_base_amount=recompute_tax_base_amount
    )
```

**Por qué es crítico**:
- Este método es el **punto de entrada** donde se inyecta el contexto
- De aquí se propaga a `_compute_debit_credit()` → `_convert()` → apuntes contables

---

### Detalle de Funciones - `account.move.line`

#### 12. `_compute_currency_rate(self)`

**Propósito**: Calcular y almacenar el tipo de cambio para cada línea de apunte contable.

**Decorador**:
```python
@api.depends(
    'currency_id',
    'company_id',
    'move_id.date',
    'move_id.use_custom_rate',        # Detecta cuando se activa
    'move_id.custom_currency_rate',   # Detecta cambios en la tasa
)
```

**Funcionamiento**:
```python
def _compute_currency_rate(self):
    for line in self:
        if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
            # Asignar directamente la tasa manual
            line.currency_rate = line.move_id.custom_currency_rate
        else:
            # Fallback: calcular tasa estándar del sistema
            super(AccountMoveLine, line)._compute_currency_rate()
```

**Campo `currency_rate`**:
- Es un campo **almacenado** en la base de datos
- Odoo lo usa para mostrar información y auditoría
- **No afecta** directamente el cálculo (que se hace en `_compute_debit_credit`)

---

#### 13. `_compute_debit_credit(self)` ⭐ **MÉTODO CRÍTICO**

**Propósito**: Convertir `amount_currency` (en moneda extranjera) a `debit`/`credit` (en moneda de compañía).

**Por qué es crítico**: Aquí es donde se hace la conversión REAL que genera los apuntes contables.

**Decorador**:
```python
@api.depends(
    'amount_currency',           # Monto en moneda extranjera
    'currency_id',
    'move_id.use_custom_rate',
    'move_id.custom_currency_rate'
)
```

**Funcionamiento**:
```python
def _compute_debit_credit(self):
    for line in self:
        if line.move_id.use_custom_rate and line.move_id.custom_currency_rate:
            company_currency = line.move_id.company_id.currency_id

            if line.currency_id and line.currency_id != company_currency:
                # CONVERSIÓN CON TASA MANUAL
                # Por qué: Usamos _convert() con contexto para mantener consistencia
                balance = line.currency_id.with_context(
                    custom_currency_rate=line.move_id.custom_currency_rate
                )._convert(
                    line.amount_currency,  # 100 USD
                    company_currency,      # ARS
                    line.move_id.company_id,
                    line.move_id.date,
                    round=True
                )
                # balance = 100,000 ARS (si tasa = 1000)
            else:
                balance = line.amount_currency

            # Asignar a débito o crédito según el signo
            if balance > 0:
                line.debit = balance
                line.credit = 0
            else:
                line.debit = 0
                line.credit = -balance
        else:
            # Fallback: usar cálculo estándar de Odoo
            super(AccountMoveLine, line)._compute_debit_credit()
```

**Ejemplo de Ejecución**:
```
Línea de factura:
  amount_currency = -100.00 USD (negativo porque es compra)
  custom_currency_rate = 1000

Paso 1: Llamar _convert()
  balance = currency_id._convert(-100.00, ARS, ...)

Paso 2: _convert() usa custom_rate del contexto
  balance = -100.00 * 1000 = -100,000.00 ARS

Paso 3: Asignar según signo
  balance < 0 → credit = 100,000.00 ARS, debit = 0
```

---

#### 14. `_compute_balance(self)`

**Propósito**: Calcular balance como `debit - credit`.

**Por qué existe**: Odoo usa `balance` en reportes y consultas. Debe ser consistente con debit/credit.

**Funcionamiento**:
```python
@api.depends('debit', 'credit')
def _compute_balance(self):
    for line in self:
        line.balance = line.debit - line.credit
```

**Invariante**: Siempre `balance = debit - credit` (regla contable universal)

---

### Flujo Completo de Conversión

```
1. Usuario guarda factura de 100 USD con tasa manual = 1000
   ↓
2. _recompute_dynamic_lines() inyecta contexto:
   self._context = {'custom_currency_rate': 1000}
   ↓
3. Por cada línea de factura, Odoo ejecuta _compute_debit_credit()
   ↓
4. _compute_debit_credit() llama:
   currency_id._convert(100, ARS, ..., context={'custom_currency_rate': 1000})
   ↓
5. res.currency._convert() detecta custom_rate en contexto:
   balance = 100 * 1000 = 100,000 ARS
   ↓
6. Se asigna a debit/credit según signo
   ↓
7. _compute_balance() calcula balance = debit - credit
   ↓
8. Apuntes contables guardados con tipo de cambio manual ✓
```

---

### Garantía de Fallback al Sistema

**Pregunta**: ¿Qué pasa si NO se define tipo de cambio manual?

**Respuesta**: Todos los métodos tienen fallback al sistema:

```python
# res_currency.py
if custom_rate:
    return custom_rate
else:
    return super()._get_conversion_rate(...)  # ← SISTEMA

# account_move_line.py
if line.move_id.use_custom_rate:
    # usar manual
else:
    super()._compute_debit_credit()  # ← SISTEMA
```

**Comportamiento**:
- `use_custom_rate = False` → Usa tipo de cambio del sistema ✓
- `use_custom_rate = True` → Usa `custom_currency_rate` ✓
- Compatibilidad total con facturas normales ✓

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

### Métodos de Conversión de Moneda

#### `res.currency._get_conversion_rate(from_currency, to_currency, company, date)`
- **Propósito**: Obtener tipo de cambio entre dos monedas en una fecha específica
- **Uso**: Sobrescrito para retornar tasa manual si está en contexto
- **Fallback**: Si no hay tasa manual, usa tasas del sistema

#### `res.currency._convert(from_amount, to_currency, company, date, round=True)`
- **Propósito**: Convertir un importe de una moneda a otra
- **Uso**: Sobrescrito para hacer conversión con tasa manual
- **Fórmula**: `to_amount = from_amount * custom_rate`

### Métodos de Presupuestos

#### `purchase.order._prepare_invoice()`
- **Propósito**: Preparar diccionario de valores para crear factura
- **Uso**: Hook para heredar tipo de cambio del presupuesto a la factura

#### `purchase.order._get_currency_rate()`
- **Propósito**: Obtener tipo de cambio a usar en cálculos
- **Uso**: Sobrescrito para retornar tasa manual

### Métodos de Facturas

#### `account.move._recompute_dynamic_lines(recompute_all_taxes, recompute_tax_base_amount)`
- **Propósito**: Recalcular líneas dinámicas (impuestos, totales, apuntes contables)
- **Uso**: Inyectar contexto con tipo de cambio manual antes de recalcular
- **Crítico**: Punto de entrada donde se propaga el contexto

#### `account.move._get_currency_rate()`
- **Propósito**: Obtener tipo de cambio de la factura
- **Uso**: Sobrescrito para retornar tasa manual

### Métodos de Apuntes Contables

#### `account.move.line._compute_currency_rate()`
- **Propósito**: Calcular y almacenar tipo de cambio en cada línea
- **Uso**: Sobrescrito para asignar tasa manual directamente

#### `account.move.line._compute_debit_credit()` ⭐
- **Propósito**: Convertir `amount_currency` a `debit`/`credit` en moneda de compañía
- **Uso**: Sobrescrito para usar `_convert()` con contexto de tasa manual
- **Crítico**: Aquí se genera el balance real de los apuntes contables

#### `account.move.line._compute_balance()`
- **Propósito**: Calcular balance como debit - credit
- **Uso**: Sobrescrito para mantener consistencia contable

### ORM Methods Utilizados
- `@api.onchange()`: Detectar cambios en campos y ejecutar lógica
- `@api.depends()`: Marcar campos calculados y sus dependencias
- `with_context()`: Inyectar datos en el contexto de ejecución
- `ensure_one()`: Verificar que se trabaja con un solo registro
- `super()`: Llamar método de clase padre
- `fields.Date.context_today()`: Obtener fecha actual del contexto

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
