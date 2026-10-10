# Protocolo RXON (Reverse Axon)

[EN](https://github.com/madgagarin/rxon/blob/main/README.md) | **ES** | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PyPI version](https://img.shields.io/pypi/v/rxon.svg)](https://pypi.org/project/rxon/)

**RXON** (Reverse Axon) es un protocolo ligero para conexiones inversas, distribución de tareas y comunicación tipificada entre servicios en arquitecturas **[HLN (Holarchical Logic Network)](https://github.com/madgagarin/hln)**.

Proporciona modelos de mensajes estrictamente tipificados y verificación Zero Trust para entornos de agentes distribuidos.

## Concepto

En las arquitecturas cliente-servidor convencionales, el plano de control envía solicitudes hacia los nodos de trabajo (Push). En **RXON**, el nodo subordinado (shell / trabajador) inicia conexiones salientes hacia el orquestador para consultar tareas (Pull). Este patrón de conexión inversa permite que los trabajadores operen detrás de cortafuegos y NAT sin redirección de puertos entrantes, manteniendo un canal de comunicación bidireccional.

## Características Principales

- **Conexión inversa (modelo Pull)**: los nodos de trabajo inician conexiones salientes al orquestador para recibir tareas, facilitando despliegues tras NAT y cortafuegos.
- **Verificación Zero Trust**: firma de mensajes con HMAC-SHA256 (simétrica) y Ed25519 (asimétrica), verificación en tiempo constante, seguimiento de cadenas de llamadas (`bubbling_chain`) y firma de tareas (`sig`).
- **Contexto de políticas y telemetría**: soporte para restricciones de ejecución (`policy`), profundidad en la holarquía (`depth`), contador de pasos de ejecución (`step`), enlace criptográfico con evento primario (`parent_hash`), informe de costos (`costs`), niveles de riesgo (`risk`) y permisos requeridos (`permissions`).
- **Comprobantes de ejecución (`ExecutionReceipt`)**: esquema para registrar decisiones de enrutamiento consultivo, candidatos evaluados, activación de alternativas (fallback) y latencia de decisión.
- **Inferencia y validación de esquemas**: genera esquemas JSON a partir de firmas de funciones Python (`msgspec.Struct`, `dataclass`, modelos compatibles con `model_json_schema`, tipos primitivos). Caché LRU segura para hilos con límite de tamaño (hasta 2048 entradas).
- **Serialización determinista**: `to_dict` normaliza números de coma flotante (`1.0` -> `1`), descarta valores `None` y ordena claves mediante `orjson` para garantizar hashes criptográficos reproducibles.
- **Conversión de modelos**: utilidad `from_dict` basada en `msgspec` para convertir diccionarios en estructuras tipificadas (`Struct`, `dataclass`, `Enum`, `UUID`, `datetime`).
- **Coincidencia de recursos**: empareja dispositivos de hardware y recursos de trabajadores con los requisitos de la tarea mediante reglas de comparación numérica («mayor o igual») e inclusión/intersección de conjuntos.
- **Transporte resiliente**: clientes WebSocket y sondeo HTTP con renovación de tokens, retroceso exponencial y manejo de HTTP 429 (`Retry-After`).

## Ecosistema

RXON es el protocolo base para la pila de automatización multi-agente distribuida:

- **[HLN (Holarchical Logic Network)](https://github.com/madgagarin/hln)**: arquitectura y especificación para holarquías autosimilares.
- **[Shellspirit](https://github.com/madgagarin/shellspirit)**: orquestador basado en máquinas de estados para flujos de trabajo de IA distribuidos.
- **[Shellnode](https://github.com/madgagarin/shellnode)**: SDK de Python para construir trabajadores autónomos (holones) conectados a orquestadores por RXON.

## Arquitectura y Lógica

### Integridad de Datos y Validación

1. **Estabilidad de serialización**: `orjson` genera JSON canónico: los números de coma flotante enteros se normalizan (`10.0` -> `10`), las claves de diccionario se ordenan y se convierten en cadenas. Esto asegura que cargas útiles equivalentes generen hashes idénticos.
2. **Soporte de tipos**: soporte directo para `msgspec.Struct`, bibliotecas estándar `dataclass`, `datetime`, `UUID`, `Enum` y modelos que implementen `model_json_schema()` o `schema()`.
3. **Límite de profundidad de recursión**: el recorrido recursivo está acotado a 30 niveles para proteger contra desbordamientos de pila en estructuras cíclicas o excesivamente anidadas.
4. **Validación de esquemas**: los esquemas JSON se compilan y conservan en memoria. Antes de ejecutar una tarea, los parámetros pueden validarse contra el esquema de entrada de la habilidad para rechazar anomalías tempranamente.

### Coincidencia de Recursos

RXON define reglas declarativas de asignación de tareas a trabajadores:

1. **Dispositivos de hardware**: evalúa propiedades en `HardwareDevice`. Las propiedades numéricas usan la lógica «mayor o igual» (ej. `vram_gb: 16` coincide con `vram_gb >= 16`).
2. **Propiedades generales**: atributos escalares en el diccionario `properties` usan la misma regla numérica.
3. **Conjuntos de capacidades**: cuando los requisitos especifican una colección de valores admitidos (ej. `["linux", "darwin"]`), se comprueba pertenencia o intersección no vacía de conjuntos.

### Contexto de Ejecución y Gobernanza

- **Restricciones de política (`policy`)**: diccionario con directivas de ejecución (habilidades permitidas, límites de tokens, presupuesto).
- **Jerarquía de llamadas (`depth`, `step`, `parent_hash`)**: registra profundidad de llamadas (`depth`), número de paso en el flujo (`step`) y hash del evento primario (`parent_hash`).
- **Firma de tarea (`sig`)**: firma HMAC-SHA256 generada por el orquestador con `ORCHESTRATOR_SECRET_KEY` y validada por el trabajador antes de ejecutar.
- **Marca de tiempo (`timestamp`)**: marca de tiempo Unix entera en segundos (`int`) para evitar discrepancias de precisión flotante.
- **Informe de costos (`costs`)**: campo `TaskResult.costs` para reportar métricas de recursos consumidos (tokens, tiempo de cómputo, importe).

## Códigos de Error Estándar

- `CONTRACT_VIOLATION_ERROR`: los datos no se ajustan al esquema esperado.
- `SECURITY_ERROR`: fallo de autenticación, token expirado o firma incorrecta.
- `RESOURCE_EXHAUSTED_ERROR`: recursos de cómputo, memoria o GPU insuficientes.
- `DEPENDENCY_ERROR`: un servicio, trabajador o artefacto necesario no está disponible.

## Inicio Rápido

### Lado del Trabajador (Pull)

```python
from rxon import create_transport
from rxon.models import HardwareDevice, Resources

# 1. Inicializar transporte (soporta http, https, ws, wss)
transport = create_transport("ws://api.hln.local", "worker-01", "secret-token")

# 2. Declarar recursos del trabajador
my_res = Resources(
    properties={"ram_gb": 64, "cpu_cores": 16},
    devices=[HardwareDevice(type="gpu", model="RTX 4090", properties={"vram_gb": 24})],
)

# 3. Comprobar requisitos de la tarea (ej. GPU con al menos 16GB VRAM)
req = Resources(devices=[HardwareDevice(type="gpu", properties={"vram_gb": 16})])
if my_res.matches(req):
    print("El trabajador cumple con los requisitos")
```

### Lado del Orquestador (Servidor)

```python
from aiohttp import web
from rxon import HttpListener

app = web.Application()
listener = HttpListener(app)

# Registrar rutas RXON antes de iniciar la aplicación
listener.setup_routes()


async def my_handler(action, payload, context):
    if action == "poll":
        return {"job_id": "j-1", "task_id": "t-1", "type": "echo"}
    return {"status": "ok"}


await listener.start(handler=my_handler)
```

## Licencia

Este proyecto se distribuye bajo la licencia Mozilla Public License 2.0 (MPL 2.0).

---

_Mantra: "The RXON is the medium for the Ghost."_
