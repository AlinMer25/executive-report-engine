# Política de anonimización

Versión 1.0 — 27 de octubre de 2026

## 1. Procedencia de los datos

Los datos de este repositorio provienen de un canal de venta real que gestioné
entre 2025 y 2026 en una empresa argentina de retail multimarketplace. Los
valores monetarios están indexados y los proveedores pseudonimizados por
confidencialidad comercial. La empresa no se nombra en ningún archivo.

Se declara la procedencia en lugar de presentar los datos como ficticios: el
valor analítico del proyecto depende de que el caso sea real, y la
confidencialidad se resuelve por transformación, no por simulación.

## 2. Invariante monetario

**Ningún archivo de este repositorio contiene un valor monetario absoluto.**

Es la única regla no negociable del proyecto y no depende del criterio del
autor al momento de publicar: se verifica por código. El test del invariante
escanea los outputs generados y falla si encuentra un monto en moneda.

## 3. Estándar por categoría

| Categoría | Tratamiento |
|---|---|
| Márgenes (bruto, neto) y variación en pp | Reales, sin transformar |
| Toda variación % y participación % | Reales |
| Operaciones, unidades vendidas | Reales |
| Facturación, ganancia bruta/neta, ticket promedio | Índice base 100 (abril 2026 = 100) |
| Costo de estructura | Solo como ratio sobre ganancia neta. Jamás en moneda |
| Proveedores | Pseudónimo con rubro: "Proveedor A (línea blanca)" |
| Operadores | "Operador 1" / "Operador 2" |
| Plataformas | Reales — son marketplaces públicos |
| Productos destacados | Nombre real, sin costo de compra |

## 4. Pseudonimización

El mapeo nombre real → pseudónimo vive en `config/pseudonyms_private.json`,
que está en `.gitignore` y nunca se commitea.

- Los pseudónimos son estables entre informes: el Proveedor A de abril es el
  Proveedor A de septiembre.
- Se conserva el rubro porque es lo que da sentido analítico a la
  comparación. Un proveedor sin rubro es una letra sin información.

## 5. Qué nunca entra al repositorio

- Sueldos o remuneraciones, en cualquier formato
- Datos de clientes, en cualquier formato
- Costos de compra por SKU
- Datos de contacto de proveedores
- Razón social o nombre comercial de la empresa

## 6. Dataset público

`data/sample/` contiene un dataset sintético generado por código. Reproduce la
estructura de columnas y los órdenes de magnitud relativos del dataset real,
no sus valores. Cualquier persona puede clonar el repositorio y ejecutar el
pipeline completo sin acceso a datos confidenciales.

## 7. Procedimiento ante duda

Si un dato no encaja claramente en una categoría de la sección 3, no se
publica hasta que la decisión se tome y quede registrada en
`docs/05-decisiones.md`. Ante la duda, no se publica.