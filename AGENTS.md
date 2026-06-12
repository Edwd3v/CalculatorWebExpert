## Stack
- Single Django project: `freight_quote` config/app wiring, `quotes` contains nearly all business logic, views, forms, models, services, and tests.
- Runtime dependencies are only in `requirements.txt`: Django 5, Gunicorn, WhiteNoise, `dj-database-url`, `psycopg`.

## Commands
- Local setup follows `README.md`: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python manage.py migrate`.
- Health check is repo-specific and uses the venv directly: `./scripts/healthcheck.sh`. Strict deploy-style checks: `HEALTHCHECK_STRICT=1 ./scripts/healthcheck.sh`.
- Full test suite: `.venv/bin/python manage.py test`
- Focused test example that works: `.venv/bin/python manage.py test quotes.tests.test_services`
- Basic Django validation: `.venv/bin/python manage.py check`

## Execution Flow
- URL entrypoints are `freight_quote/urls.py` and `quotes/urls.py`; auth routes are Django built-ins at `/login/` and `/logout/`.
- Quote creation is in `quotes.views.new_quote`; the calculation logic stays in `quotes/services/calculation.py`, not in forms or templates.
- Admin/backoffice screens are custom Django views under `/control-panel/...`, not Django admin.

## Business Rules To Preserve
- Quote creation now depends on route-based pricing, not the older global settings rates: `new_quote` requires an active `RouteRate` for the origin/destination/transport pair and a matching active `RouteRateTier` for the total weight.
- `calculate_quote()` intentionally applies one unified tariff and chooses the charge basis by comparing total KG vs total M3. It does not use volumetric KG to decide pricing; tests lock this behavior in.
- Country selection is normalized through `quotes/services/location_mapping.py`; when no preferred or existing entry point exists, quote creation may auto-create a generated `OriginLocation` if `create_missing=True`.
- Preferred country -> entry point overrides live in `freight_quote/settings.py` under `COUNTRY_ENTRY_POINT_CODES`.

## Testing And Editing Gotchas
- The quote item formset uses the `items` prefix. POST payloads and tests must include management fields like `items-TOTAL_FORMS`.
- Non-staff users are redirected away from `/control-panel/...` with a flash message; these views do not return 403s.
- Active route rates and tiers enforce overlap/uniqueness constraints in the model layer. If you change pricing logic, run at least `quotes.tests.test_models`, `quotes.tests.test_services`, and `quotes.tests.test_views`.

## Deploy
- Render build order is fixed in `build.sh`: `pip install -r requirements.txt` -> `collectstatic --noinput` -> `migrate --noinput`.
- `build.sh` optionally creates or updates a superuser from `ADMIN_USERNAME` and `ADMIN_PASSWORD` (`ADMIN_EMAIL` optional). Do not remove this without updating deploy docs/config.

## Frontend
- For frontend work, read `docs/frontend-design-audit.md` first; it contains the current verified UX/CSS debt and explicitly says to preserve Django business logic while improving shared styling.
- Templates and user-facing copy are Spanish; keep new labels/messages consistent.
