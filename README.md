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

## Roles y permisos

- Usuario normal:
  - Puede crear cotizaciones.
  - Puede ver solo su propio historial y detalles.
- Admin (`is_staff=True`):
  - Puede acceder al panel de control.
  - Puede crear usuarios.
  - Puede editar tarifas globales (aerea, maritima y factor volumetrico).
  - Puede ver el historial completo de todos los usuarios.

## Configuracion de tarifas y factor volumetrico

En `freight_quote/settings.py`:

- `AIR_RATE_USD_PER_KG`
- `SEA_RATE_USD_PER_M3`
- `AIR_VOLUMETRIC_FACTOR`

## Tests

```bash
python manage.py test
```
