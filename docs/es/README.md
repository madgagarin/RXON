# Protocolo RXON (Reverse Axon)

[EN](https://github.com/madgagarin/rxon/blob/main/README.md) | **ES** | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Typing: Typed](https://img.shields.io/badge/Typing-Typed-brightgreen.svg)](https://peps.python.org/pep-0561/)

**RXON** (Reverse Axon) es un protocolo de comunicación entre servicios de conexión inversa y ligero, diseñado para la arquitectura **[HLN (Hierarchical Logic Network)](https://github.com/avtomatika-ai/hln)**.

Sirve como el "sistema nervioso" para sistemas multi-agente distribuidos, conectando nodos autónomos (Holones) en una única red jerárquica.

## 🧬 La Metáfora Biológica

El nombre **RXON** deriva del término biológico *Axón* (la fibra nerviosa). En las redes clásicas, los comandos suelen fluir de "arriba hacia abajo" (modelo Push). En RXON, la iniciativa de conexión siempre proviene del nodo subordinado (Worker/Shell) hacia el nodo superior (Orquestador/Ghost). Este es un "Axón Inverso" que crece de abajo hacia arriba, creando un canal a través del cual descienden los comandos posteriormente.

## ✨ Características Principales

-   **Transportes Modulares**: Abstracción total de la capa de red. Soporte para HTTP, WebSocket, gRPC o Tor.
-   **Sistema de Eventos Genéricos**: Mecanismo unificado para actualizaciones de progreso, alertas personalizadas y señales en tiempo real.
-   **Cadena de Identidad Zero Trust**: Soporte nativo para el "bubbling" de eventos con `origin_worker_id` y `bubbling_chain` para prevenir suplantaciones en holarquías de múltiples capas.
-   **Telemetría Detallada de Recursos**: Los heartbeats incluyen métricas granulares de CPU, RAM y dispositivos de hardware especializados (GPU, TPU, NPU), incluyendo temperatura y niveles de memoria.
-   **Priorización y Deadlines de Tareas**: Soporte integrado para `priority` y `deadline` (timestamp) de ejecución, permitiendo programación local inteligente y autocancelación de tareas obsoletas.
-   **Core sin Dependencias**: El núcleo no tiene dependencias externas (los transportes estándar usan `aiohttp` y `orjson`).
-   **Contratos Estrictos**: Todos los mensajes (tareas, resultados, heartbeats) definen sus estructuras de datos a través de esquemas JSON, permitiendo validación automática y despacho inteligente.
-   **Nativo para Blobs**: Soporte integrado para la descarga de datos pesados a través de almacenamiento compatible con S3 (`rxon.blob`).

## 🏗 Arquitectura

El protocolo se divide en dos interfaces principales:

1.  **Transport (lado del Trabajador)**: Interfaz para iniciar conexiones, recuperar tareas, emitir eventos y enviar resultados.
2.  **Listener (lado del Orquestador)**: Interfaz para aceptar conexiones entrantes y enrutar mensajes al motor de orquestación.

### Telemetría de Alta Señal (Heartbeats)

Los Heartbeats de RXON proporcionan al Orquestador una visión detallada de la salud del Holón:
-   `ResourcesUsage`: Consumo en tiempo real de CPU y RAM.
-   `DeviceUsage`: Carga por dispositivo, memoria y temperatura para aceleradores.
-   `hot_cache`: Lista de artefactos/modelos cargados actualmente en memoria.

### Contratos de Habilidades

Cada habilidad declarada en RXON puede incluir ahora:
-   `input_schema`: Esquema JSON para parámetros.
-   `output_schema`: Esquema JSON para resultados.
-   `events_schema`: Mapeo de nombres de eventos a sus esquemas JSON.
-   `output_statuses`: Lista de resultados lógicos válidos (ej. `success`, `retry_later`).

## 🛡️ Error Handling

RXON utiliza una jerarquía de excepciones dedicada basada en `RxonError`. También define códigos de error estandarizados para los resultados de las tareas:
-   `CONTRACT_VIOLATION_ERROR`: La salida del trabajador no coincide con su esquema declarado.
-   `DEPENDENCY_MISSING_ERROR`: Falta una dependencia requerida (artefacto, archivo, servicio).
-   `RESOURCE_EXHAUSTED_ERROR`: Recursos físicos (RAM, VRAM, CPU) agotados.
-   `LIMIT_EXCEEDED_ERROR`: Límites lógicos (Cuotas, ventanas de contexto) excedidos.
-   `TIMEOUT_ERROR`: El trabajador no pudo terminar a tiempo (o el plazo ha expirado).
-   `LATE_RESULT`: (Respuesta) El orquestador rechazó el resultado porque el plazo ha expirado.

## 🧪 Pruebas

La biblioteca incluye un `MockTransport` para simplificar las pruebas de los Workers en aislamiento sin ejecutar un Orquestador real.

```python
from rxon.testing import MockTransport

# Usar el esquema mock:// en la factoría estándar
transport = create_transport("mock://", "test-worker", "token")
await transport.connect()

# Inyectar tareas directamente
transport.push_task(my_task_payload)
```

## 📜 Licencia

El proyecto se distribuye bajo la Mozilla Public License 2.0 (MPL 2.0).

---
*Mantra: "The RXON is the medium for the Ghost."*
