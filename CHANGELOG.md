# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Versionamiento Semántico](https://semver.org/lang/es/).

## [No publicado]

### Agregado
- Se reestructuró la app en dos páginas: Pronóstico y Calibración → Estimación de Técnicos
- Página 1 muestra serie temporal completa (Real Ene–May + Estimación Jun–Jul) con 3 líneas: real, base, +mundial
- Se agregó sección de impacto del Mundial mostrando diferencia entre estimación base y con factores
- Se agregó comparativa lado a lado por horas: fecha real (observada) vs fecha estimada (proyectada)
- Se agregó botón "Guardar Modelo" que congela la proyección y la pasa a la página de técnicos
- Página 2 toma la proyección guardada y corre la optimización ILP para asignar turnos

### Corregido
- Se corrigió `AttributeError: 'Styler' object has no attribute 'applymap'` reemplazando por `.map()`
- Se corrigió `KeyError: 'Fecha'` cambiando el separador CSV de `;` a `,` con `index_col=0`
- Se corrigió variable `st` que sobreescribía el módulo streamlit, renombrada a `row_data`
