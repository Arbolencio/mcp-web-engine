# 🚀 Guía de Onboarding Beta Pública — MCP Web Engine

> **Guía rápida de 1 página para conectar tu cliente MCP (Claude Desktop, Cursor, Windsurf, Inspector) al endpoint HTTPS público en < 3 minutos.**

---

## 🌐 Endpoint Público de Producción HTTPS

- **Endpoint MCP 2026-07-28:** `https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp`
- **Health Check:** `https://surveys-networking-titled-middle.trycloudflare.com/health`

---

## 🔑 Paso 1: Obtén tu Beta Key

Contacta con el administrador para recibir tu clave personal e independiente de acceso Beta (formato `sk_mcp_beta_...`).
Cada clave Beta cuenta con un límite de **10,000 peticiones** y una tasa máxima de **120 req/minuto**.

---

## ⚙️ Paso 2: Configura tu Cliente MCP

### A. Configuración en Cursor / Windsurf / MCP Inspector (Conexión Directa HTTPS)
1. Abre los ajustes de **MCP / Custom Tools** en tu IDE.
2. Añade un nuevo servidor con la siguiente URL:
   - **URL:** `https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp`
3. Añade la cabecera HTTP de autenticación:
   - **Header Name:** `Authorization`
   - **Header Value:** `Bearer sk_mcp_beta_TU_CLAVE_AQUÍ`

---

### B. Configuración en Claude Desktop (vía puente stdio `mcp-remote`)
Abre tu archivo `claude_desktop_config.json` y añade:

```json
{
  "mcpServers": {
    "mcp-web-engine": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://surveys-networking-titled-middle.trycloudflare.com/v1/mcp",
        "--header",
        "Authorization: Bearer sk_mcp_beta_TU_CLAVE_AQUÍ"
      ]
    }
  }
}
```

---

## 🧪 Paso 3: Prueba tu Primera Invocación MCP

Una vez conectado, pídele a tu modelo/asistente:

> *"Busca los últimos avances del protocolo MCP en 2026 y extrae un resumen en Markdown."*

Tu asistente ejecutará de forma transparente:
1. `web_search(query="MCP protocol 2026 advancements")`
2. `extract_markdown(url="https://...")`

---

## 🔒 Privacidad y Seguridad

- **Zero Tracking:** No almacenamos tus consultas de búsqueda ni el contenido descargado.
- **Protección Anti-SSRF:** La infraestructura bloquea el acceso accidental o malicioso a redes privadas locales.
