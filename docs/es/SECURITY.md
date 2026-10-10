# Política de Seguridad

[EN](https://github.com/madgagarin/rxon/blob/main/SECURITY.md) | **ES** | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/SECURITY.md)

## Notificación de Vulnerabilidades

Por favor, reporte cualquier vulnerabilidad de seguridad en la biblioteca RXON a [madgagarin@gmail.com].

## Arquitectura de Seguridad

RXON establece límites de seguridad para la ejecución distribuida en redes HLN:

### Firmas Digitales y HMAC

El protocolo admite la firma de cargas útiles mediante HMAC-SHA256 (simétrica) y Ed25519 (asimétrica) en el campo `security.signature`:

- **Integridad**: los mensajes no pueden modificarse en tránsito.
- **Autenticidad**: solo los nodos que poseen claves válidas o secretos compartidos pueden emitir comandos o resultados autorizados.
- **Serialización canónica**: la codificación canónica con `orjson` garantiza secuencias de bytes idénticas para la verificación de firmas.

### Protección contra Ataques de Reproducción (Replay)

Los mensajes firmados requieren una marca de tiempo entera `timestamp`. El orquestador rechaza mensajes que:

- Superen la ventana de tiempo configurada (60 segundos por defecto).
- Contengan marcas de tiempo futuras que excedan el desfase permitido.
- Reutilicen un `event_id` o `task_id` ya procesado dentro de la ventana de validez activa.

### Identidad y Cadenas de Llamadas

Los eventos emitidos por nodos subordinados contienen `origin_worker_id` y `bubbling_chain`. La firma criptográfica cubre la carga útil y la jerarquía de llamadas, impidiendo la suplantación de identidad sin acceso a la clave secreta.

### Contratos de Interfaz y Validación de Esquemas

Los mensajes del protocolo (registro de trabajadores, heartbeats, definiciones de habilidades, cargas útiles de tareas) se validan contra esquemas JSON:

- Los esquemas de entrada y salida utilizan `additionalProperties: False` para rechazar campos no declarados y evitar inyecciones en el estado.
- Las cargas útiles inválidas se descartan antes de que comience la ejecución de la tarea.

### Modelo de Conexión Inversa

Las conexiones se establecen de forma saliente desde los trabajadores hacia el orquestador. Los trabajadores no abren puertos de escucha públicos, reduciendo la exposición ante escaneos de red externos.

### Asignación de Tareas y Plazos (Deadlines)

Los resultados solo se aceptan del trabajador asignado a la tarea. Las marcas de tiempo opcionales `deadline` imponen tiempos límite de ejecución y evitan procesar trabajos obsoletos.

### Telemetría de Recursos

El reporte periódico de uso de CPU, memoria y GPU permite a los orquestadores detectar sobrecargas y desviar tareas de nodos saturados.
