

# Survey Pipeline

Pipeline modular para la investigación de publicaciones en arquitectura y sistemas informáticos. Extrae papers de DBLP por conferencia/revista, enriquece los resúmenes mediante S2/Crossref/arXiv, asigna puntuaciones basadas en palabras clave temáticas, permite revisión y etiquetado a través de una herramienta web, y finalmente sincroniza los PDF desde Zotero.

**Introducción en una frase**: Una herramienta automatizada de investigación bibliográfica que realiza extracción masiva desde DBLP → puntuación inteligente por palabras clave → extracción de contenido esencial con doble validación de IA → y genera material listo para usar en propuestas de investigación.

## Inicio Rápido

📖 **Lectura obligatoria para principiantes**: [Guía de inicio en 5 minutos (QUICKSTART.md)](QUICKSTART.md) - Configura conferencias, establece palabras clave y ejecuta con un clic

## Estado del Pipeline

| Paso | Script | Estado | Salida |
|------|------|------|------|
| 1 | `fetch_dblp.py` | ✅ | `data/db/*.csv` |
| 2 | `enrich_papers.py` | ✅ | `data/enriched/*.csv` |
| 3 | `score_papers.py` | ✅ | `data/topics/{topic}/scored.csv + top{10,50,100}.csv` |
| 3.5 | `slice_csv.py` | ✅ | Filtrado por umbral de puntuación |
| 4 | `review_server.py` + `review.html` | ✅ | Revisión web, etiquetas guardadas en CSV |
| 5 | `sync_zotero.py` | ✅ | `pdfs/` |
| 6 | `extract_papers.py` | ✅ | `corpus/draft/*.json` |
| 7 | `paper_review_pipeline.py` | ✅ | `corpus/llm/{glm5.1,gpt5.4}/*.json` |
| 8 | `corpus_reviewer.py` | ✅ | Revisión cruzada del corpus + edición manual |
| 9 | `build_graph.py` | ⬜ | Visualización del grafo de citas |

## Datos Actuales (2026-04-10)

- **14,600 publicaciones**, 103 CSV por venue×año
- **27 conferencias** + **7 revistas**, cubriendo 2022-2026
- **Cobertura de resúmenes 92%**
- Tema CPU AI: 196 publicaciones con score >= 11, 12 marcadas como keep
- **Estado del Corpus**: corpus draft generado, pipeline en ejecución

## Estructura de Directorios

```
survey/
├── configs/
│   ├── venues.yaml              # Configuración DBLP de conferencias/revistas
│   └── topic-cpu-ai.yaml        # Palabras clave por tema (término + peso)
├── data/
│   ├── db/                      # 103 CSV, datos crudos de DBLP
│   ├── enriched/                # 103 CSV, datos enriquecidos
│   └── topics/cpu-ai/           # Resultados de puntuación y filtrado
│       ├── scored.csv           # 14,600 publicaciones completas
│       ├── scored-score-gte11.csv  # 196 publicaciones
│       ├── top10/50/100.csv
│       ├── doi-list.txt         # Lista de DOI de publicaciones guardadas
│       └── corpus/              # Corpus para análisis LLM
│           ├── draft/           # Paso 6: JSON draft tras parsear PDFs
│           ├── llm/
│           │   ├── glm5.1/      # Paso 7a: Resultados de extracción GLM *.json
│           │   └── gpt5.4/      # Paso 7b: Revisión y corrección GPT
│           ├── human_review/    # Paso 8: Guardado de edición manual
│           └── paper_review_pipeline/  # Registros y estado del pipeline
├── pdfs/                        # Directorio de descarga de PDFs
│   └── cpu-ai/                  # Archivos PDF del tema CPU AI
├── extract_papers.py            # Paso 6: Parseo de PDF a JSON draft
├── paper_review_pipeline.py     # Paso 7: Pipeline de generación adversarial dual-modelo
├── corpus_reviewer.py            # Paso 8: Servicio web de revisión cruzada del corpus
├── tools/
│   ├── s2_fetch.py              # Cliente API batch S2
│   └── arxiv_fetch.py           # Cliente API arXiv
├── skill/
│   ├── claude/
│   │   └── analyze-paper-claude.md  # Skill Claude Code: análisis de papers
│   └── codex/
│       └── paper-json-review/       # Skill Codex: revisión de corpus LLM
├── fetch_dblp.py                # Paso 1: Extracción DBLP
├── enrich_papers.py             # Paso 2: Enriquecimiento S2/Crossref/arXiv
├── score_papers.py              # Paso 3: Puntuación por palabras clave
├── slice_csv.py                 # Paso 3.5: Filtrado CSV
├── review_server.py             # Paso 4: Servidor de revisión web
├── review.html                  # Paso 4: Frontend de revisión web
├── sync_zotero.py               # Paso 5: Sincronización PDF Zotero
├── export_dois.py               # Alternativa Paso 5: Exportar links DOI para descarga manual
├── requirements.txt             # Dependencias pip (PyMuPDF, pdfplumber, flask)
├── timeline.md                  # Línea de tiempo
├── doc/                         # Documentación detallada
└── plan/                        # Documentos de diseño por paso
```

## Inicio Rápido

```bash
# Paso 1: Extraer lista de publicaciones desde DBLP
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/

# Paso 2: Enriquecer resúmenes y citas (S2 batch → Crossref → arXiv)
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# Paso 3: Puntuar por palabras clave temáticas
python3 score_papers.py --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

# Paso 3.5: Filtrar conjunto de alta puntuación
python3 slice_csv.py --input data/topics/cpu-ai/scored.csv --min-score 11

# Paso 4: Iniciar revisión web (abrir http://localhost:8088 en el navegador)
python3 review_server.py \
    --csv data/topics/cpu-ai/scored-score-gte11.csv \
    --topic configs/topic-cpu-ai.yaml

# Paso 5: Sincronizar PDFs desde Zotero (requiere Zotero local ejecutándose)
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/

# Alternativa Paso 5: Exportar enlaces DOI para descarga manual (cuando Zotero no está disponible)
python3 export_dois.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output pdfs/cpu-ai/doi-list.txt

# Paso 6: Generar corpus draft JSON desde PDFs
python3 extract_papers.py \
    pdfs/cpu-ai/ \
    data/topics/cpu-ai/scored-score-gte11.csv \
    -o data/topics/cpu-ai/corpus/draft/

# Paso 7: Ejecutar pipeline de generación adversarial dual-modelo
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# Paso 8: Iniciar revisión cruzada del corpus (abrir http://localhost:5000 en el navegador)
python3 corpus_reviewer.py --topic cpu-ai
# O especificar otro tema / puerto
python3 corpus_reviewer.py --topic another-topic --port 8080
```

## Flujo de Datos

```
configs/venues.yaml
      ↓
fetch_dblp.py → data/db/{venue}-{year}.csv
      ↓
enrich_papers.py → data/enriched/{venue}-{year}.csv
      ↓                          (S2 batch + Crossref + arXiv)
score_papers.py + configs/topic-*.yaml
      ↓
data/topics/{topic}/scored.csv
      ↓
slice_csv.py → scored-score-gte{N}.csv
      ↓
review_server.py → Etiquetado de revisión web (keep/core/skip)
      ↓
sync_zotero.py → pdfs/  (Extrae PDFs desde API local de Zotero)
      ↓
extract_papers.py → corpus/draft/*.json  (Parseo PDF + metadatos CSV)
      ↓
paper_review_pipeline.py → corpus/llm/{glm5.1,gpt5.4}/*.json
                           (Generación adversarial dual-modelo: extracción GLM → revisión GPT)
      ↓
corpus_reviewer.py → Revisión cruzada del corpus + edición manual (http://localhost:5000)
```

El parámetro `--topic` corresponde al nombre del subdirectorio bajo `data/topics/`, y también está vinculado a los archivos PDF bajo `pdfs/{topic}/`.

## Descripción de la Configuración

### venues.yaml

```yaml
venues:
  - id: ISCA
    dblp_key: conf/isca          # Conferencia
  - id: IPDPS
    dblp_key: conf/ipps          # La clave y el nombre de la página difieren
    dblp_abbr: ipdps
  - id: IEEE-TC
    dblp_key: journals/tc        # Revista (volumen analizado automáticamente del índice)
date_range:
  start: 2022
  end: 2026
```

### topic-cpu-ai.yaml

```yaml
topic: "Aceleración de IA para CPU"
keywords:
  - term: "AMX"
    weight: 10          # Palabra clave principal, puntuación alta
  - term: "tensor"
    weight: 3
  - term: "AI"
    weight: 1           # Término genérico, puntuación baja para ampliar recuperación
```

**Umbrales de puntuación:** Alta (>=10) / Media (>=5) / Baja (>=1) / Ninguna (0)

## Herramienta de Revisión Web

`review_server.py` + `review.html` proporcionan una interfaz web local de revisión:

- **Cuadrícula 2x2**: Muestra 4 publicaciones simultáneamente
- **Resaltado dorado de palabras clave**: Gradiente dorado de oscuro a claro según el peso
- **Etiquetas personalizadas**: keep / core / related / skip + entrada libre
- **Atajos de teclado**: `1234`=keep, `qwer`=skip, `←→`=páginas, `Ctrl+S`=guardar
- **Persistencia**: Etiquetas escritas en las columnas keep/notes del CSV

## Herramienta de Revisión Cruzada del Corpus

`corpus_reviewer.py` proporciona una interfaz web de dos columnas para visualizar comparativamente el corpus analizado por LLM y los PDF originales, con soporte para edición manual. Es la herramienta central del Paso 8.

### Inicio

```bash
pip install flask
python3 corpus_reviewer.py --topic <topic-name>
```

`--topic` especifica el nombre del directorio de tema bajo `data/topics/` (por defecto `cpu-ai`), el servidor leerá el corpus `corpus/llm/` correspondiente y los PDF bajo `pdfs/<topic>/`. `--port` permite especificar el puerto (por defecto 5000).

### Disposición

- **Mitad izquierda**: Área de visualización / edición JSON estructurado
- **Mitad derecha**: Visor de PDF

### Cuatro Vistas

Cambia entre vistas usando `↑` `↓` o `1` `2` `3` `4`:

| Vista | Fuente de datos | Descripción |
|------|--------|------|
| **GPT Review** | `corpus/llm/gpt5.4/*.review.json` | Revisión de GPT sobre los resultados de extracción de GLM (veredicto, verificaciones, revisiones por campo, problemas) |
| **GLM Extraction** | `corpus/llm/glm5.1/*.json` | Extracción original de GLM sobre el paper (info del paper, abstract, metadatos) |
| **GPT Revised** | `corpus/llm/gpt5.4/*.revised.json` | Análisis estructurado corregido por GPT (investigación, contribuciones, lagunas) |
| **Human Edit** | Basado en GPT Revised, guarda en `corpus/human_review/` | Formulario editable, modifica directamente los resultados de GPT y guarda |

### Flujo de Trabajo de Edición Manual

1. Revisar primero **GPT Review** para conocer las opiniones de revisión y los problemas
2. Consultar **GLM Extraction** para ver la extracción original
3. Ver **GPT Revised** para obtener la versión corregida
4. Realizar la edición final en **Human Edit** y guardar

### Atajos de Teclado

| Tecla | Función |
|------|------|
| `←` `→` | Cambiar al paper anterior/siguiente |
| `↑` `↓` | Cambiar de vista (cíclico) |
| `1` `2` `3` `4` | Ir directamente a la vista correspondiente |
| `Ctrl+S` | Guardar en la vista Human Edit |

Al escribir en el cuadro de edición, las teclas de dirección y numéricas no activan la navegación. La barra superior muestra el estado saved/unsaved.

## Paso 6: extract_papers.py — Parseo de PDF y Generación de Corpus Draft

### Funcionalidad

Extrae el texto principal de los archivos PDF y combina los metadatos del CSV para generar el JSON del corpus draft.

### Características

- **Extracción de texto principal**: Utiliza PyMuPDF (fitz) o pdfplumber para extraer el cuerpo del PDF, deteniéndose en la sección de Referencias
- **Limpieza de ruido**: Elimina automáticamente encabezados, pies de página, declaraciones de copyright, líneas DOI, etc.
- **Fusión de metadatos**: Lee metadatos como title, authors, year, venue, doi, abstract, citation_count desde el CSV
- **Procesamiento por lotes**: Soporta procesamiento masivo de todo un directorio de PDFs, generando archivos JSON individuales

### Modo de Uso

```bash
python3 extract_papers.py \
    pdfs/cpu-ai/ \
    data/topics/cpu-ai/scored-score-gte11.csv \
    -o data/topics/cpu-ai/corpus/draft/
```

### Formato de Salida

Cada PDF genera un archivo JSON:

```json
{
  "file": "A-Heterogeneous-CNN-Compilation-Framework-for-RISC-V-CPU-and-NPU-Integration-Bas.pdf",
  "title": "A Heterogeneous CNN Compilation Framework for RISC-V CPU and NPU Integration",
  "authors": "Author1, Author2",
  "year": 2024,
  "venue": "Conference Name",
  "doi": "10.xxx/xxxx",
  "url": "https://...",
  "abstract": "Contenido del resumen",
  "citation_count": "10",
  "relevance_score": "15",
  "relevance": "Alta",
  "matched_keywords": "RISC-V, CNN, NPU",
  "body_text": "Contenido del texto principal extraído del PDF...",
  "text_length": 15000,
  "csv_matched": true,
  "extraction_status": "éxito"
}
```

### ¿Por qué se necesita un Draft Estructurado?

1. **Entrada estandarizada**: Proporciona un formato de datos unificado para el análisis posterior por LLM
2. **Metadatos enriquecidos**: Los metadatos estructurados del CSV (citas, puntuación de relevancia) ayudan al LLM a comprender la importancia del paper
3. **Texto principal limpio**: Texto principal tras la limpieza de ruido, reduciendo interferencias en el procesamiento del LLM
4. **Rastreabilidad**: Conserva el estado de extracción (success/failed), facilitando la depuración de problemas

## Paso 7: paper_review_pipeline.py — Generación Adversarial Dual-Modelo

### Funcionalidad

Pipeline asíncrono productor-consumidor que automatiza el procesamiento en dos fases: análisis con Claude y revisión con Codex.

### Diseño de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    paper_review_pipeline.py                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │   Productor      │         │   Consumidor     │          │
│  │   (Claude)       │   ──→   │   (Codex)        │          │
│  │                  │  Cola   │                  │          │
│  │  • Leer draft     │         │  • Leer análisis │          │
│  │  • Llamar Claude  │         │  • Llamar Codex  │          │
│  │  • Guardar GLM    │         │  • Guardar review │          │
│  │    analysis.json │         │   + revised.json │          │
│  └──────────────────┘         └──────────────────┘          │
│         ↓                            ↓                      │
│  corpus/llm/glm5.1/           corpus/llm/gpt5.4/            │
└─────────────────────────────────────────────────────────────┘
```

### Modo de Uso

```bash
# Uso básico: procesar todo el corpus
python3 paper_review_pipeline.py --topic cpu-ai

# Limitar cantidad a procesar
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# Especificar papers concretos
python3 paper_review_pipeline.py --topic cpu-ai \
    --papers data/topics/cpu-ai/corpus/draft/paper1.json \
            data/topics/cpu-ai/corpus/draft/paper2.json

# Reintentar papers fallidos
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/summary.json

# Modo serial estricto (sin solapamiento de pipeline)
python3 paper_review_pipeline.py --topic cpu-ai --strict-serial

# Dry run (solo imprimir comandos, no ejecutar)
python3 paper_review_pipeline.py --topic cpu-ai --dry-run
```

### Parámetros Clave

| Parámetro | Descripción | Valor por defecto |
|------|------|--------|
| `--topic` | Nombre del directorio de tema | `cpu-ai` |
| `--limit` | Límite de papers a procesar | `null` (todos) |
| `--papers` | Especificar explícitamente rutas JSON de papers | - |
| `--queue-size` | Tamaño de la cola del pipeline | 1 |
| `--strict-serial` | Deshabilitar solapamiento del pipeline | `false` |
| `--skip-existing` | Omitir resultados existentes | `false` |
| `--dry-run` | Solo imprimir comandos sin ejecutar | `false` |
| `--retry-failed-from` | Reintentar desde registro de fallos anterior | - |
| `--claude-timeout-sec` | Tiempo de espera para Claude | 1800 |
| `--codex-timeout-sec` | Tiempo de espera para Codex | 3600 |

### Estructura de Salida

```
corpus/
├── paper_review_pipeline/
│   ├── claude/
│   │   ├── {stem}.cmd.txt       # Comando de línea
│   │   ├── {stem}.stdout.log    # Salida estándar
│   │   └── {stem}.stderr.log    # Salida de errores
│   ├── codex/
│   │   ├── {stem}.cmd.txt
│   │   ├── {stem}.stdout.log
│   │   └── {stem}.stderr.log
│   ├── status/
│   │   ├── {stem}.claude.status.json  # Estado en tiempo real
│   │   └── {stem}.codex.status.json
│   └── runs/
│       └── latest/
│           ├── summary.json           # Resumen de ejecución
│           ├── failed_papers.json     # Lista de papers fallidos
│           └── failed_papers.txt      # Lista de papers fallidos (texto plano)
└── llm/
    ├── glm5.1/
    │   └── {stem}.json           # Generado por Claude
    └── gpt5.4/
        ├── {stem}.review.json     # Revisión Codex
        └── {stem}.revised.json    # Corrección Codex
```

### ¿Por qué usar Generación Adversarial Dual-Modelo?

1. **Reducción del riesgo de alucinaciones**: El primer modelo (Claude) se encarga de la generación, el segundo (GPT) de la revisión
2. **Complementariedad especializada**: Claude destaca en análisis de texto largo y salida estructurada, GPT en revisión y corrección
3. **Rastreabilidad**: Conserva la generación original, opiniones de revisión y versión corregida para auditoría manual
4. **Garantía de calidad**: El formato estructurado de revisión obliga al segundo modelo a verificar dimensiones específicas

### Tolerancia a Fallos y Reintentos

El pipeline cuenta con mecanismos robustos de tolerancia a fallos:

- **Reintentos automáticos**: Reintenta automáticamente errores reintentables (límite de tasa, tiempo de espera)
- **Clasificación de fallos**: Diferencia entre fallos reintentables y fallos críticos
- **Protección ante fallos consecutivos**: Se detiene automáticamente tras N fallos consecutivos de Codex
- **Persistencia de estado**: El estado de cada tarea se escribe en JSON en tiempo real, permitiendo reanudación desde el punto de interrupción

### Ejemplo de Archivo de Estado por Fase

```json
{
  "stage": "claude",
  "job_name": "paper.json",
  "state": "running",
  "pid": 12345,
  "started_at_unix": 1712746800,
  "elapsed_sec": 45.2,
  "timeout_sec": 1800,
  "cwd": "/root/opencute",
  "command": ["claude", "-p", "/analyze-paper-claude ..."]
}
```

## Restricciones de Datos Estructurados e Intervención Manual

### ¿Por qué usar Datos Estructurados?

1. **Verificabilidad**: JSON Schema puede validar automáticamente el formato, evitando salidas inválidas
2. **Analizabilidad**: Los programas pueden leer y procesar directamente sin necesidad de reparseo
3. **Rastreabilidad**: Cada campo tiene un origen y significado claros
4. **Escalabilidad**: Permite agregar nuevos campos flexiblemente sin romper el flujo existente

### Implementación de Restricciones Estructuradas

1. **Restricciones de entrada** (JSON draft)
   - Nombres y tipos de campo fijos
   - Validación de campos obligatorios
   - Restricciones de valores enumerados (ej. theme_primary, workstream_fit)

2. **Restricciones de salida** (JSON analysis)
   - Definición JSON Schema
   - Límites de longitud de campo
   - Requisitos de formato de citas

3. **Restricciones de revisión** (JSON review)
   - Ítems de verificación predefinidos
   - Clasificación estandarizada de gravedad
   - Informes de problemas estructurados

### Intervención Manual en Nodos Clave

1. **Revisión Web** (Paso 4)
   - Filtrado manual de papers de alta relevancia
   - Etiquetado de papers centrales y relacionados
   - Adición de notas personales

2. **Revisión Cruzada del Corpus** (Paso 8)
   - Visualización comparativa del análisis LLM con el texto original
   - Corrección de extracciones erróneas
   - Complementación de puntos omitidos
   - Etiquetado de contenido incierto

3. **Scripts de Pre-Verificación**
   - Verificación automática de cumplimiento estructural
   - Validación de existencia de citas
   - Comprobación de validez de valores enumerados

### Valor de la Intervención Manual

1. **Control de calidad**: Los LLM pueden generar alucinaciones o inferencias excesivas
2. **Conocimiento del dominio**: El humano puede identificar detalles técnicos que el LLM no comprende
3. **Comprensión contextual**: El humano puede juzgar la relevancia según los objetivos de investigación
4. **Atribución de responsabilidad**: Las decisiones clave requieren confirmación humana

## Directorio Skill

`skill/` almacena las definiciones de skill para herramientas LLM auxiliares, utilizadas en análisis de papers y revisión de corpus.

### Skill Claude Code: Analyze Paper

| Archivo | Descripción |
|------|------|
| `skill/claude/analyze-paper-claude.md` | Análisis inicial del paper |

Invocado a través de la CLI de Claude Code, lee el `abstract` y `body_text` del paper, generando un JSON dossier estructurado (objetivo de investigación, contribuciones, clasificación temática, detalles técnicos y argumentos para proposal), destinado a la redacción de propuestas.

### Skill Codex: Paper JSON Review

| Archivo | Descripción |
|------|------|
| `skill/codex/paper-json-review/SKILL.md` | Definición de entrada del Skill |
| `skill/codex/paper-json-review/references/analysis-contract.md` | Convención de formato de salida Dossier |
| `skill/codex/paper-json-review/references/review-schema.md` | Convención de formato de salida Review |
| `skill/codex/paper-json-review/references/review-output.schema.json` | JSON Schema |
| `skill/codex/paper-json-review/scripts/preflight_review.py` | Script de pre-verificación determinista |
| `skill/codex/paper-json-review/scripts/run_codex_review.sh` | Entrada de revisión con un clic |

**Funcionalidad**: Realiza una segunda revisión del dossier generado por LLM, verificando cumplimiento estructural, precisión de citas y credibilidad semántica, generando un JSON de review y un JSON revised corregido.

**Flujo de uso**:

1. Instalar el skill en `$CODEX_HOME/skills/`:
   ```bash
   bash skill/codex/paper-json-review/scripts/install_workspace_codex_home.sh
   ```

2. Invocar a través de la CLI de Codex:
   ```bash
   bash skill/codex/paper-json-review/scripts/run_codex_review.sh \
       <path-to-dossier-json>
   ```

3. O ejecutar el script de pre-verificación por separado:
   ```bash
   python skill/codex/paper-json-review/scripts/preflight_review.py \
       --analysis-json <dossier.json> \
       --paper-json <paper.json> \
       --pretty
   ```

**Salida**: JSON que contiene `review` (informe de revisión estructurado) y `revised_analysis` (dossier corregido), guardado en `corpus/llm/gpt5.4/`.

## API de Corpus Reviewer

| Ruta | Método | Descripción |
|------|------|------|
| `/api/papers` | GET | Lista de papers (con archivos disponibles por modelo) |
| `/api/json/<model>/<file>` | GET | Obtener JSON generado por LLM |
| `/api/human/<basename>` | GET | Obtener JSON editado manualmente (null si no existe) |
| `/api/human/<basename>` | PUT | Guardar JSON editado manualmente |
| `/pdf/<filename>` | GET | Obtener archivo PDF |

## Lectura Adicional

- Línea de tiempo: [timeline.md](timeline.md)
- Plan general: [plan/README.md](plan/README.md)
- Documentación detallada: [doc/README.md](doc/README.md)
- Documentación antigua: [doc/survey-crawler.md](doc/survey-crawler.md) (obsoleta, solo para referencia)
