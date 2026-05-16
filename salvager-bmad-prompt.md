# Salvager Agent — BMAD Session Kickoff

## Contexto del proyecto

Quiero arrancar un proyecto open source con metodología BMAD.
El proyecto es un agente de búsqueda y compra autónoma de hardware
de segunda mano (HDDs y RAM) en Wallapop y eBay.es.

---

## Research previa: ¿existe algo así ya?

### Lo que existe (competencia/referencia)

**Scrapers de Wallapop en GitHub (ninguno con LLM ni compra autónoma):**

- **wallabot** — Python + Selenium + Telegram. Monitor básico de nuevos
  anuncios, deduplicación simple con seen_ads.txt. Sin LLM, sin compra.
  https://github.com/topics/wallapop

- **Walla-Bot** (miqueasmd) — Bot configurable via config.json con keywords,
  rango de precio, ubicación. Alertas por email. Sin LLM, sin compra.
  https://github.com/miqueasmd/Walla-Bot

- **wallapop-scraper** (Tatuck) — El más interesante de los existentes.
  Usa la API no oficial de Wallapop + Gemini 2.0 Flash para identificar
  artículos infravalorados para reventa. LLM para valoración, pero sin
  compra autónoma y sin listas de modelos específicos.
  https://github.com/Tatuck/wallapop-scraper

- **wallapop-scraper** (davertor) — Librería Python pura sobre API no
  oficial. Devuelve DataFrames. Sin LLM, sin notificaciones, sin compra.
  https://github.com/davertor/wallapop-scraper

- **Apify Wallapop Scraper** — SaaS a $0.50/1000 resultados. Sin LLM,
  sin compra autónoma. Solo extracción de datos.
  https://apify.com/seretalabs/wallapop-scraper

**Price trackers genéricos con Telegram:**
Abundan para Amazon, Flipkart, etc. Ninguno específico de segunda mano
con modelo de datos por fabricante/referencia ni con LLM.

**Investigación académica sobre agentes de compra:**
Columbia/Yale publicaron "What Is Your AI Agent Buying?" (ACES sandbox)
estudiando cómo los VLMs compran en marketplaces simulados. Research pura,
no un proyecto deployable.

**Hermes Agent skills ecosystem** (awesome-hermes-agent, 23k+ stars):
Revisado el repositorio completo. Hay skills para monitoring de
infraestructura, research agent, análisis legal, generación de novelas,
análisis blockchain... **Nada de hardware hunting ni compra autónoma
en marketplaces de segunda mano.**

### Conclusión del gap analysis

**El proyecto es genuinamente nuevo en su combinación:**
1. YAML de modelos específicos con precio máximo por referencia
2. Lógica de detectar el componente DENTRO de un equipo (NAS con HDD)
3. Hermes + TinyFish como stack de ejecución
4. Flujo de confirmación humana via Telegram antes de comprar
5. Compra autónoma real (Fase 2) — ningún proyecto existente llega aquí
6. Foco en mercado español (Wallapop + eBay.es)

Los scrapers existentes son monitores de alertas, no agentes de compra.
El Tatuck scraper es el más cercano en espíritu (LLM para valoración)
pero sin compra, sin listas de referencia y sin Hermes/TinyFish.

### Contexto de mercado que justifica el proyecto

Tom's Hardware (mayo 2026) confirma la crisis de precios:
DDR4 32GB que costaba $60-90 en octubre 2025 ahora vale $150-180.
El mercado de segunda mano español es una de las pocas salidas
para encontrar precios razonables — de ahí la urgencia del proyecto.

---

## Stack técnico decidido

**Hermes Agent** (Nous Research) corriendo en HPE DL160 Gen10
(servidor propio en colo, Valencia)
https://hermes-agent.nousresearch.com/

**TinyFish** como infraestructura web del agente
https://www.tinyfish.ai/

**Notificaciones via Telegram** (ya configurado en Hermes)

**Listas de hardware en YAML** (HDDs y RAM, <100 modelos cada una)

### Hermes tiene de serie (v0.13.0, mayo 2026)

- `web_search` + `web_extract` (backend: Firecrawl o SearXNG)
- 10 browser tools (`browser_navigate`, `browser_snapshot`, etc.)
- Scheduler con lenguaje natural (cron interno, sin límite de jobs)
- Memoria persistente entre sesiones (SQLite + FTS5)
- Skills auto-generados, auto-curados (Autonomous Curator desde v0.12.0)
- Soporte nativo de MCP servers
- `clarify` tool: pregunta al usuario con hasta 4 opciones antes de actuar
- Subagentes paralelos (hasta 8 workers concurrentes)

### TinyFish productos relevantes

| Producto | Coste | Rate limit | Uso en este proyecto |
|---|---|---|---|
| Search | **GRATIS** | 5 req/min | Buscar en Wallapop/eBay.es |
| Fetch | **GRATIS** | 25 URLs/min | Extraer precio/desc de listings |
| Browser | Créditos | — | Compra autónoma (Fase 2) |
| Agent | Créditos | — | Flujos complejos Fase 2 |

TinyFish expone MCP en: `https://agent.tinyfish.ai/mcp`
Integración: se añade como MCP server en `config.yaml` de Hermes.
Hermes obtiene `tinyfish_search`, `tinyfish_fetch`, `tinyfish_browser`
automáticamente. Sin código de integración.

**Nota importante:** TinyFish tiene integración oficial con Hermes Agent
documentada en su blog y en el awesome-hermes-agent.

---

## Arquitectura por fases

### FASE 1 — Inteligencia (MVP)

```
Hermes (DL160)
├── Carga hdds.yaml + ram.yaml
├── Genera variantes de keywords por modelo/referencia
├── TinyFish Search (gratis) → listings en Wallapop y eBay.es
├── TinyFish Fetch (gratis) → extrae precio/descripción del listing
├── Evaluación LLM:
│   ├── ¿Componente solo? → comparar con max_price_solo
│   └── ¿Componente en equipo? (NAS, workstation) → max_price_in_device
├── Deduplicación: memoria de URLs ya vistas (no spam)
├── Notificación Telegram con formato rico
└── Cron: ejecutar diariamente
```

### FASE 2 — Compra autónoma

```
Hermes detecta oportunidad
    ↓
Telegram: "🟢 WD Red 4TB · 48€ (max: 55€) · Valencia
           ¿Compro? [✅ Sí] [❌ No] [👁 Ver]"  ← clarify tool
    ↓ usuario aprueba
TinyFish Browser (sesión autenticada, stealth Chromium)
├── Wallapop: login → chat vendedor → Wallapop Pay
└── eBay.es: login → "Cómpralo ya" → checkout
    ↓
Telegram: "✅ Comprado. [screenshot de confirmación]"

EXCEPCIÓN: si vendedor pide Bizum/transferencia → escalar a usuario
```

---

## Estructura de datos (YAML)

```yaml
# hdds.yaml — ejemplo de entrada
- manufacturer: Western Digital
  model: WD Red Plus 4TB
  ref: WD40EFPX
  max_price_solo: 55        # €, componente solo
  max_price_in_device: 90   # €, si viene en NAS/servidor
  type: hdd
  keywords:
    - "WD Red 4TB"
    - "WD40EFPX"
    - "disco NAS 4TB WD"
  container_keywords:
    - "NAS Synology 4TB"
    - "NAS QNAP 4TB"
    - "servidor NAS 4 bahias"
```

```yaml
# ram.yaml — ejemplo de entrada
- manufacturer: Kingston
  model: KVR26N19S8/16
  spec: DDR4-2666 16GB
  max_price_solo: 25
  max_price_in_device: 60
  type: ram
  keywords:
    - "Kingston DDR4 16GB"
    - "KVR26N19S8"
  container_keywords:
    - "mini PC DDR4 segunda mano"
    - "NUC Intel 16GB"
```

---

## Plataformas objetivo

**Wallapop** (es.wallapop.com) — prioridad, mercado español
- Tiene anti-bot agresivo → TinyFish Browser stealth para Fase 2
- Para búsqueda: TinyFish Search con `site:wallapop.com ...` funciona
- API no oficial documentada: `api.wallapop.com/api/v3/general/search`
  (usada en proyectos existentes como davertor/wallapop-scraper)

**eBay.es** (ebay.es) — secundario, más estructurado
- Flujo de compra más lineal ("Cómpralo ya")
- Mejor candidato para automatizar primero en Fase 2

---

## Open Source

- Proyecto a liberar como OSS (licencia por decidir: MIT o Apache 2.0)
- README completo en inglés y español
- Configuración por variables de entorno (.env), nunca credenciales en repo
- Las listas YAML van como ejemplos, el usuario pone las suyas
- Reproducible por cualquiera con Hermes + cuenta TinyFish
- Compatible con el estándar agentskills.io (ecosistema Hermes)

---

## Dudas abiertas para resolver en BMAD

> **Nota:** Las dudas sobre legalidad están resueltas — ver sección
> "Análisis legal" más arriba. El disclaimer del README ya está redactado.


1. **Nombre del proyecto** — pendiente de decidir
2. **Licencia OSS** — MIT vs Apache 2.0
3. **Owner del repo** — ¿bajo HackNodes Lab org o personal?
4. **Wallapop login en Fase 2** — ¿sesión persistente via cookies
   o TinyFish Browser gestiona login cada vez?
5. **Fallback si TinyFish Browser falla en Wallapop** — ¿notificar
   al usuario con el link directo para que compre manualmente?
6. **Rate limiting** — ¿cuántas búsquedas por ejecución sin
   disparar anti-bot de Wallapop? (referencia: scraper de Tatuck
   usa paginación y sleep entre requests)
7. **Contenedor en equipo: criterio de decisión** — ¿el agente
   decide solo si un NAS "vale la pena" o siempre pregunta?
8. **Web backend de Hermes** — ¿Firecrawl (500 créditos/mes gratis)
   o SearXNG self-hosted en el DL160? TinyFish cubre búsqueda/fetch
   gratis así que SearXNG puede ser redundante para este proyecto.
9. **API no oficial de Wallapop** — ¿la usamos directamente via
   TinyFish Fetch o confiamos solo en búsqueda por Google index?
   (La API no oficial es más fiable pero puede romperse)
10. **Publicación como Hermes skill** — ¿el proyecto se publica también
    en agentskills.io para el ecosistema Hermes? Daría visibilidad.

---

## Referencias útiles para el Architect

- Wallapop API no oficial: `https://api.wallapop.com/api/v3/general/search`
  Params: `keywords`, `max_sale_price`, `latitude`, `longitude`, `distance`
- TinyFish docs: https://docs.tinyfish.ai/
- TinyFish MCP: `https://agent.tinyfish.ai/mcp`
- TinyFish Search rate limit free tier: 5 req/min
- TinyFish Fetch rate limit free tier: 25 URLs/min
- Hermes skill estándar: https://agentskills.io
- Hermes tools reference: https://hermes-agent.nousresearch.com/docs/reference/tools-reference
- Hermes cron docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- Proyecto de referencia más cercano: https://github.com/Tatuck/wallapop-scraper
- awesome-hermes-agent: https://github.com/0xNyk/awesome-hermes-agent

---

## Análisis legal (España) — duda resuelta

### Conclusión por capa

| Capa | Situación | Riesgo |
|---|---|---|
| Web scraping en España | Legal (STS 572/2012, Ryanair vs. Atrápalo) | Ninguno |
| Base de datos Wallapop (LPI) | Zona gris, pero consultas puntuales no extraen "parte sustancial" | Muy bajo para uso personal |
| RGPD | Solo procesa precio/título/descripción, no datos personales de vendedores | Ninguno |
| Términos de Servicio Wallapop/eBay | Automatización viola los ToS — consecuencia: baneo de cuenta, no sanción legal | Baneo de cuenta (mitigable con stealth) |
| Compra autónoma (Fase 2) | Actúas con tus propias credenciales y tu dinero | Ninguno legal |
| DAC7 / Hacienda | Solo afecta a vendedores >30 ops o >2.000€/año. Eres comprador | Ninguno |

**Conclusión:** no existe ninguna restricción legal que impida este proyecto en España.
El único riesgo real y concreto es el baneo de cuenta en Wallapop/eBay en Fase 2,
no una infracción penal ni administrativa. En la práctica, servicios como ZebraBot
llevan más de 10 años ofreciendo automatización de Wallapop abiertamente en España
sin consecuencias legales.

### Texto de disclaimer para el README (ya redactado)

```markdown
## Legal disclaimer

This tool is for **personal use only** — finding hardware deals for your
own purchase, not for commercial resale or bulk data extraction.

1. **Scraping**: Reading publicly available listings is legal in Spain
   (Tribunal Supremo, STS 572/2012). No data is stored beyond seen-listing
   deduplication. No personal data of sellers is processed.

2. **Terms of Service**: Automated access may violate Wallapop's and eBay's
   ToS. Risk is account suspension, not legal prosecution. Use at your own
   discretion and with rate-limited, human-like request patterns.

3. **Autonomous purchase (Phase 2)**: You act on your own behalf with your
   own credentials and funds. The mandatory human confirmation step via
   Telegram before any purchase is intentional and non-bypassable by design.

The authors accept no liability for account suspensions or any consequences
arising from use of this tool against platform terms of service.
```

---

## Lo que quiero que hagas ahora

Arranca el flujo BMAD completo:
1. Genera el Project Brief a partir de todo este contexto
2. Luego PRD con el PM
3. Luego Architecture Document con el Architect
4. Luego divide en Epics e Historias de usuario
5. Implementa historia a historia

Empieza por el Project Brief y pregúntame las dudas abiertas
que necesites resolver antes de continuar.
