# Política de Seguridad de RXON

[EN](https://github.com/madgagarin/rxon/blob/main/SECURITY.md) | **ES** | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/SECURITY.md)

## Reportar una Vulnerabilidad

Por favor, reporte cualquier vulnerabilidad en la biblioteca del protocolo RXON a [madgagarin@gmail.com].

## Principios Fundamentales

RXON está diseñado para ser el "nervio" seguro de la red lógica jerárquica (HLN). Proporciona:

### 🛡️ Cadena de Identidad Zero Trust
Cada evento emitido por un nodo subordinado incluye un `origin_worker_id` y una `bubbling_chain`. Esto previene suplantaciones y permite al Orquestador auditar toda la ruta de una señal a través de la holarquía.

### 📝 Contratos de Interfaz Formales
Toda la comunicación (Registro, Heartbeats, Habilidades) es estrictamente validada contra esquemas JSON. Esto previene ataques de inyección y asegura que los datos mal formados sean rechazados antes de llegar al motor de ejecución.

### 🧬 Conexión Inversa (Flujo Axon)
La iniciativa siempre proviene del nodo subordinado (Worker/Shell). Esto elimina la necesidad de abrir puertos de entrada en los trabajadores, haciéndolos invisibles a los escaneos de red externos.

### ⏳ Propiedad de Tareas y Deadlines
Los resultados solo se aceptan del trabajador asignado actualmente a la tarea. Los campos integrados `deadline` previenen el procesamiento de tareas obsoletas y mitigan ataques de retraso o repetición.

### 📊 Telemetría de Recursos
El reporte granular de recursos en los Heartbeats permite a los Orquestadores detectar y mitigar el agotamiento de recursos (DoS) antes de que cause una falla en todo el sistema.
