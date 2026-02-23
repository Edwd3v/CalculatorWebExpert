# Cotizador de Fletes - Django MVP

Aplicacion web interna para estimar fletes internacionales (aereo y maritimo) cotizando en USD.

## Requisitos

- Python 3.11+
- pip

## Configuracion local

1. Crear entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecutar migraciones:

```bash
python manage.py migrate
```

4. Crear superusuario:

```bash
python manage.py createsuperuser
```

5. Ejecutar health check:

```bash
./scripts/healthcheck.sh
```

Modo estricto (checks de seguridad para despliegue):

```bash
HEALTHCHECK_STRICT=1 ./scripts/healthcheck.sh
```

6. Ejecutar servidor:

```bash
python manage.py runserver
```

7. Acceder:

- Login: http://127.0.0.1:8000/login/
- Admin: http://127.0.0.1:8000/admin/
- Panel de control (usuario admin/staff): http://127.0.0.1:8000/control-panel/
  - Tarifas: http://127.0.0.1:8000/control-panel/tarifas/
  - Usuarios: http://127.0.0.1:8000/control-panel/usuarios/
  - Historial operativo: http://127.0.0.1:8000/control-panel/historial/

## Roles y permisos

- Usuario normal:
  - Puede crear cotizaciones.
  - Puede ver solo su propio historial y detalles.
- Admin (`is_staff=True`):
  - Puede acceder al panel de control.
  - Puede crear usuarios.
  - Puede asignar tarifas por pais para aereo y maritimo.
  - Puede ver el historial completo de todos los usuarios.

## Tarifas por pais y vigencia

- El panel de tarifas incluye un catalogo de 249 paises (ISO 3166) listo para usar.
- Cada cotizacion usa la tarifa vigente del pais de origen segun el tipo de transporte.
- La vigencia inicia al crear la tarifa y termina automaticamente cuando se registra una nueva tarifa para el mismo pais y tipo de transporte.
- Regla de cobro para aereo y maritimo:
  - Compara `peso_total_kg` vs `volumen_total_m3`.
  - Cobra la dimension mayor usando la misma tarifa unica.

## Cotizacion por pais (interfaz comercial)

- En la pantalla de cotizacion, el usuario selecciona solo `Pais de origen` y `Pais de destino`.
- El sistema mapea internamente cada pais al aeropuerto/puerto principal segun el tipo de transporte.
- El mapeo preferido se puede definir en `COUNTRY_ENTRY_POINT_CODES` dentro de `freight_quote/settings.py`.
- Si un pais no tiene mapeo explicito, se genera automaticamente un punto interno tecnico.

## Configuracion base

En `freight_quote/settings.py`:

- `AIR_VOLUMETRIC_FACTOR`

## Tests

```bash
python manage.py test
```
