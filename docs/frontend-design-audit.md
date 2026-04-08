# Auditoria De Diseno Frontend

Fecha: 2026-04-08
Contexto: auditoria visual y de UX del proyecto Django actual, enfocada en consistencia visual, jerarquia, responsive, accesibilidad y mantenibilidad del frontend.

## Alcance

Pantallas revisadas:

- `templates/base.html`
- `templates/quotes/new_quote.html`
- `templates/quotes/result.html`
- `templates/quotes/admin_panel.html`
- `templates/quotes/admin_history.html`
- `templates/quotes/admin_users.html`

## Diagnostico General

La aplicacion ya tiene una intencion visual real: hay tipografias elegidas con criterio, varios layouts tienen mejor acabado que un CRUD tipico y existe una separacion perceptible entre experiencia comercial y administrativa.

El problema principal no es la ausencia de diseno, sino la falta de sistema. Cada pantalla resuelve su propia identidad visual y redefine componentes base, lo que produce una experiencia fragmentada y complica cualquier mejora futura.

## Hallazgos Priorizados

### 1. Falta de sistema visual unificado

La base define una identidad calida y editorial, pero varias paginas se separan de ella y adoptan otros lenguajes visuales.

Consecuencia:

- el producto se siente inconsistente
- la percepcion de calidad baja aunque cada pantalla individual tenga trabajo
- el mantenimiento del frontend se vuelve mas costoso

Referencias:

- `templates/base.html:9`
- `templates/quotes/new_quote.html:5`
- `templates/quotes/admin_panel.html:121`
- `templates/quotes/admin_history.html:45`
- `templates/quotes/admin_users.html:12`

### 2. CSS demasiado acoplado por template

Cada template incluye grandes bloques `<style>` y sobreescribe reglas estructurales como `body`, `main`, `.card`, `.btn`, `input`, `table` y `.page-title`.

Consecuencia:

- los cambios globales son fragiles
- se repiten patrones de estilos
- es facil introducir regresiones visuales
- accesibilidad y responsive deben resolverse varias veces

Referencias:

- `templates/base.html:73`
- `templates/quotes/new_quote.html:5`
- `templates/quotes/result.html:121`
- `templates/quotes/admin_history.html:136`
- `templates/quotes/admin_users.html:214`

### 3. Responsive incompleto en tablas administrativas

Los layouts tienen media queries para grids y filtros, pero no hay una solucion clara para tablas anchas en vistas administrativas.

Consecuencia:

- riesgo alto de overflow horizontal en movil
- columnas comprimidas y peor legibilidad
- peor experiencia en analisis operativo desde pantallas pequenas

Referencias:

- `templates/quotes/admin_history.html:170`
- `templates/quotes/admin_history.html:239`
- `templates/quotes/admin_users.html:164`
- `templates/quotes/admin_users.html:234`

### 4. Navegacion sin estado activo ni jerarquia fuerte

La navegacion superior muestra accesos importantes, pero no marca la seccion activa ni diferencia con suficiente claridad entre navegacion principal y accion de salir.

Consecuencia:

- menor orientacion espacial dentro del producto
- mas friccion al alternar entre cotizador, historial y panel admin

Referencias:

- `templates/base.html:51`
- `templates/base.html:176`

### 5. Flujo de `new_quote` con buena base pero jerarquia operativa mejorable

La pantalla esta mejor resuelta que el resto y ya estructura el flujo en bloques claros, pero todavia falta una guia mas fuerte para la tarea principal cuando la cotizacion crece en complejidad.

Consecuencia:

- el usuario puede perder foco cuando hay muchas piezas
- falta una sensacion de progreso o estado del flujo
- la accion principal no domina toda la experiencia

Referencias:

- `templates/quotes/new_quote.html:181`
- `templates/quotes/new_quote.html:244`

### 6. `result` comunica el total pero no maximiza confianza ni accion siguiente

La pantalla destaca bien el total, pero buena parte del contexto util queda escondido en un bloque desplegable.

Consecuencia:

- validacion operativa mas lenta
- menor transparencia inmediata sobre base de cobro, tramo y piezas
- la pantalla no conduce con claridad a la siguiente accion

Referencias:

- `templates/quotes/result.html:175`
- `templates/quotes/result.html:190`

### 7. Legibilidad y contraste mejorables

Hay bastante uso de grises suaves, labels pequenos y captions de 11 a 12 px sobre fondos claros.

Consecuencia:

- menor accesibilidad visual
- peor lectura en movil
- menor claridad en vistas con alta densidad de informacion

Referencias:

- `templates/base.html:95`
- `templates/quotes/result.html:12`
- `templates/quotes/admin_panel.html:28`
- `templates/quotes/admin_history.html:21`
- `templates/quotes/admin_users.html:23`

### 8. Posible desalineacion entre reglas visuales y validacion real en `admin_users`

La UI de seguridad de contrasena es interesante, pero puede prometer reglas que no coinciden exactamente con las validaciones reales de Django configuradas en backend.

Consecuencia:

- deuda de confianza
- posibles mensajes contradictorios entre interfaz y validacion del servidor

Referencias:

- `templates/quotes/admin_users.html:300`
- `freight_quote/settings.py:102`

## Fortalezas Actuales

- buena eleccion tipografica base con `IBM Plex Sans` y `Space Grotesk`
- `new_quote` tiene una estructura funcional y moderna
- `admin_panel` ya intenta modularizar la entrada a tareas administrativas
- `result` prioriza correctamente el numero principal
- hay intencion visual diferenciada entre modulos

## Conclusiones

El proyecto no necesita "mas decoracion". Necesita consolidar un sistema de diseno ligero pero coherente.

La oportunidad principal es:

- unificar tokens
- extraer componentes base reutilizables
- normalizar patrones de formularios, tablas, cards y navegacion
- resolver responsive administrativo
- reforzar jerarquia operativa en `new_quote` y `result`

## Orden Recomendado De Ejecucion

### Fase 1. Fundaciones

- consolidar tokens visuales globales
- definir estilos base de botones, inputs, tablas, cards y estados
- reducir sobreescrituras por template

### Fase 2. Estructura Y Navegacion

- mejorar header y estado activo
- diferenciar con mas claridad experiencia operativa vs administrativa
- alinear espaciado, anchos maximos y contenedores

### Fase 3. Flujo Comercial

- rediseñar `new_quote`
- reforzar jerarquia de accion, resumen y progresion del flujo
- mejorar `result` para lectura inmediata y confianza

### Fase 4. Backoffice

- normalizar `admin_panel`, `admin_history`, `admin_users` y `admin_rates`
- resolver tablas en movil
- mejorar densidad, filtros y acciones

### Fase 5. Accesibilidad Y Pulido

- revisar contrastes
- subir legibilidad de labels y textos secundarios
- homogeneizar focus states, hover states y feedback

## Instruccion Para Futuro Agente O Skill

Si se usa una skill o agente especializado en frontend, debe:

1. Leer este archivo completo antes de proponer cambios.
2. Traducir este diagnostico a un plan de accion concreto por fases.
3. Priorizar sistema visual y arquitectura CSS antes de cambios cosmeticos aislados.
4. Mantener intacta la logica de negocio Django.
5. Implementar primero fundaciones compartidas y despues pantallas individuales.
