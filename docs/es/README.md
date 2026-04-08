# Protocolo RXON (Reverse Axon)

**ES** | [EN](https://github.com/madgagarin/rxon/blob/main/README.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PyPI version](https://img.shields.io/pypi/v/rxon.svg)](https://pypi.org/project/rxon/)

**RXON** (Reverse Axon) es un protocolo de comunicación entre servicios ligero y extensible con conexión inversa, diseñado para arquitecturas **[HLN (Hierarchical Logic Network)](https://github.com/avtomatika-ai/hln)**.

Sirve como el "sistema nervioso" para sistemas multi-agente distribuidos, proporcionando una base Zero Trust estrictamente tipada para la interacción entre holones.

## 🚀 Concepto

En las redes tradicionales, los comandos suelen fluir "de arriba hacia abajo" (modelo Push). En **RXON**, la iniciativa de conexión siempre proviene del nodo subordinado (Shell) al nodo superior (Orquestador). Esta arquitectura de "Axón Inverso" permite que los trabajadores operen detrás de NAT o Firewalls sin una configuración de red compleja, manteniendo un canal de control bidireccional seguro.

## ✨ Características principales

-   **Conexión Inversa (PULL)**: Los nodos se conectan al orquestador para obtener tareas, lo que garantiza la compatibilidad con entornos de red complejos.
-   **Seguridad Zero Trust**: Soporte integrado para firmas digitales (`SecurityContext`) y cadenas de identidad. Todos los mensajes pueden ser verificados criptográficamente a través de múltiples capas de holarquía.
-   **Agnóstico y extensible**: Los modelos principales (recursos, habilidades, tareas) son totalmente extensibles mediante campos universales `metadata` y `properties`, lo que hace que el protocolo sea adecuado para IA, IoT y robótica.
-   **Telemetría Universal**: Los heartbeats incluyen métricas detalladas de CPU, RAM y cualquier dispositivo personalizado (sensores, GPUs, actuadores) a través del modelo extensible `HardwareDevice`.
-   **Sistema de Eventos Genérico**: Mecanismo unificado de señalización para actualizaciones de progreso, alertas personalizadas y disparadores en tiempo real con burbujeo jerárquico de eventos.
-   **Smart matching de recursos**: Lógica formalizada para requisitos de hardware utilizando la lógica **GE (Greater or Equal)** para números y coincidencia parcial para modelos.
-   **Almacenamiento Blob Enchufable**: Interfaz `BlobProvider` estandarizada para la descarga de datos pesados a través de S3, GCS o almacenamiento local.
-   **Fábrica Unificada**: Inicialización fácil del transporte mediante `create_transport` con soporte para esquemas `http://`, `https://`, `ws://` y `wss://`.
-   **Núcleo sin dependencias**: El núcleo del protocolo está escrito en Python 3.11+ puro. Los transportes estándar utilizan `aiohttp` y `orjson` para un rendimiento máximo.

## 🏗 Arquitectura

El protocolo se divide en dos interfaces principales:

1.  **Transport (lado del Worker)**: Para iniciar conexiones, recuperar tareas, emitir eventos y enviar resultados.
2.  **Listener (lado del Orchestrator)**: Para aceptar conexiones entrantes y enrutar mensajes al motor de orquestación.

### Lógica de Despacho Inteligente

RXON formaliza las reglas para emparejar tareas con holones:
1.  **Coincidencia de Identidad**: Coincidencia directa por ID de dispositivo.
2.  **Tipo y Modelo**: Coincidencia exacta por tipo, coincidencia parcial por cadena de modelo (insensible a mayúsculas).
3.  **Coincidencia de Propiedades (Smart Comparison)**:
    *   **Números**: Se verifica como **al menos** (Valor del Worker >= Requisito).
    *   **Otros**: Se verifica como igualdad estricta.

## 🛡️ Manejo de Errores

RXON define un conjunto de códigos de error estandarizados para garantizar un comportamiento consistente en todas las implementaciones:
-   `CONTRACT_VIOLATION_ERROR`: Los datos no coinciden con el esquema negociado.
-   `SECURITY_ERROR`: Falló la autenticación o la verificación de firma.
-   `RESOURCE_EXHAUSTED_ERROR`: Recursos físicos insuficientes (RAM, VRAM).
-   `DEPENDENCY_ERROR`: Un servicio o artefacto requerido no está disponible.

## 🧪 Inicio Rápido

```python
from rxon import create_transport
from rxon.models import Resources, HardwareDevice

# 1. Crear transporte (soporta http, https, ws, wss)
transport = create_transport("ws://api.hln.local", "worker-01", "secret-token")

# 2. Definir recursos del worker
my_res = Resources(
    cpu_cores=8,
    devices=[HardwareDevice(type="gpu", model="RTX 4090", properties={"memory_gb": 24})]
)

# 3. Lógica de Smart Matching
req = Resources(cpu_cores=4, devices=[HardwareDevice(type="gpu", properties={"memory_gb": 16})])
if my_res.matches(req):
    print("¡Este holón está listo para la tarea!")
```

## 📜 Licencia

El proyecto se distribuye bajo la licencia Mozilla Public License 2.0 (MPL 2.0).

---
*Mantra: "El RXON es el medio para el Ghost."*
