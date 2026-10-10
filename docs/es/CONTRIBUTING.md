# Cómo contribuir a RXON

[EN](https://github.com/madgagarin/rxon/blob/main/CONTRIBUTING.md) | **ES** | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/CONTRIBUTING.md)

Como capa de protocolo compartida, los cambios en este repositorio afectan a las bibliotecas dependientes.

## Configuración

1. Clone el repositorio y navegue al directorio del proyecto.
2. Instale en modo editable con dependencias de desarrollo:
   ```bash
   pip install -e .[dev]
   ```

## Pruebas y Análisis Estático

Ejecute la suite de pruebas, el linter y el comprobador de tipos:

```bash
pytest tests/
ruff check .
mypy src tests
```

## Directrices

- **Compatibilidad**: los cambios en `rxon.models` pueden romper la compatibilidad a nivel de protocolo de red. Consulte los cambios propuestos antes de enviarlos.
- **Dependencias**: mantenga el núcleo ligero y sin dependencias externas innecesarias.
- **Tipado**: el tipado estático estricto es obligatorio en todos los modelos e interfaces públicas.
