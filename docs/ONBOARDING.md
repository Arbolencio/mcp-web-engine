# 🚀 Guía de Onboarding — MCP Web Engine 1.2.0

## Conexión local recomendada (stdio)

Requiere Node >=18, Python >=3.11 y [uv](https://docs.astral.sh/uv/getting-started/installation/) en PATH. En tu cliente MCP configura:

```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "npx",
      "args": ["--yes", "mcp-web-engine@1.2.0"],
      "env": {
        "SEARXNG_URL": "http://127.0.0.1:8082/search",
        "ALLOW_DDG_FALLBACK": "false"
      }
    }
  }
}
```

La primera ejecución puede descargar dependencias. SearXNG debe estar configurado y disponible para buscar; inicializar y listar herramientas no lo requiere. Stdio usa JSON por líneas y los permisos locales del proceso, sin autenticación Bearer.

## Acceso HTTP administrado / beta

Solicita al operador la URL HTTPS vigente, una clave personal y sus límites reales. No se publica aquí un túnel temporal ni se garantiza compatibilidad automática con clientes o puentes HTTP genéricos.

El operador debe seguir [README](../README.md#http) y [operaciones](operations.md): cabecera `Authorization: Bearer <TU_CLAVE>`, TLS y red restringida. `/health` indica vida del proceso, no disponibilidad del buscador. `/v1/mcp/legacy` ofrece el flujo con inicialización; `/v1/mcp` es una extensión stateless propia con cabeceras adicionales, no una certificación de conformidad MCP. Valida los requisitos de transporte de tu cliente antes de conectarlo; SSE es limitado.

## Primera invocación

Pide al asistente buscar un tema con `web_search` y convertir una página pública con `extract_markdown`. Consulta `tools/list` para los argumentos y límites vigentes.

## Privacidad y seguridad

Las consultas llegan al SearXNG configurado y a sus buscadores upstream. DuckDuckGo fallback está desactivado salvo elección explícita del operador. El servicio mantiene contadores y telemetría por clave; el operador, proxy y proveedores pueden aplicar sus propias políticas de registro. No introduzcas secretos en consultas.

Las validaciones anti-SSRF son defensa en profundidad, no una garantía absoluta; el operador debe restringir también el tráfico saliente. Trata el contenido descargado como datos no confiables, incluidas posibles instrucciones maliciosas.
