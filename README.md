# UrbanVision Analytics
**Sistema Integrado de Auditoria Automática de Infraestrutura Urbana e Severidade Viária**  
*Implementação em estrita conformidade com o Caderno de Requisitos e Arquitetura de Referência (Requisitos v1.0 e Expansão P1).*

---

## 📋 Sumário Executivo

O **UrbanVision Analytics** é uma plataforma corporativa para prefeituras, concessionárias e órgãos de infraestrutura urbana destinada à triagem, detecção automática e mensuração da severidade da malha viária utilizando visão computacional, telemetria GPS e inteligência geoespacial.

A plataforma automatiza todo o fluxo desde a coleta de imagens/vídeos de campo até o cálculo do **Índice de Degradação Urbana (IDU-Pavimento)**, emissão de **Relatórios Executivos Oficiais em PDF** com hash de integridade criptográfica (SHA-256) e gestão de ordens de serviço municipais.

---

## 🎯 Arquitetura de Funcionalidades Implementadas

```
┌────────────────────────────────────────────────────────────────────────┐
│                        URBANVISION ANALYTICS                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
  ┌─────────────────┬──────────────┼──────────────┬──────────────────┐
  ▼                 ▼              ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────────┐ ┌───────────────┐
│ 1. Ingestão  │ │ 2. Visão IA  │ │ 3. Espacial│ │ 4. IDU      │ │ 5. Auditoria  │
│ & Telemetria │ │ & Taxonomia  │ │ & Deduplic.│ │ & Métricas  │ │ & Relatórios  │
└──────────────┘ └──────────────┘ └────────────┘ └─────────────┘ └───────────────┘
```

### 1. Ingestão de Dados e Controle de Qualidade (RF-01 a RF-04, AT-01)
* **Deduplicação por Conteúdo (SHA-256):** Cálculo de hash criptográfico na entrada de imagens, impedindo duplicatas exatas dentro do mesmo lote.
* **Extração Automática de EXIF:** Leitura nativa de Latitude, Longitude, Altitude e Timestamp UTC.
* **Suporte a Manifesto CSV:** Ingestão de telemetria externa para câmeras veiculares sem sensor GPS embutido.
* **Inspeção Técnica de Qualidade de Imagem:**
  * **Nitidez (Blur):** Aferição de foco por variância do operador de Laplaciano ($\sigma^2 < 100 \implies$ rejeição por desfoque);
  * **Exposição:** Detecção de subexposição e superexposição severa por histograma de luminância.
* **Processamento de Vídeos e Telemetria Temporal (`app/services/video.py`):**
  * Extração automatizada de quadros com amostragem configurável de FPS;
  * Interpolação temporal geodésica contínua de coordenadas GPS entre marcos de coleta.

### 2. Detecção Automatizada e Taxonomia RDD2022 + Ativos P1 (RF-05, RF-06, RD-01 a RD-04)
* **Taxonomia Canônica RDD2022 (Pavimento):**
  * `D00`: Trinca Longitudinal
  * `D10`: Trinca Transversal
  * `D20`: Trinca tipo Malha / Jacaré (fadiga de base)
  * `D40`: Buraco (*Pothole* / cavidade com risco estrutural)
* **Expansão de Ativos Urbanos (P1):**
  * `M01`: Sinalização Horizontal Desgastada (faixas de pedestre e bordos)
  * `S01`: Placa de Sinalização Vertical Deteriorada ou Ilegível
* **Catálogo e Versionamento de Modelos de IA (`/v1/modelos`):**
  * Registro de modelos de inferência, versões de pesos (`weights_hash`) e metadados de execução.
  * Preservação integral de predições brutas, recortes (*crops*) e bounding boxes para auditoria técnica.

### 3. Inteligência Geoespacial e Deduplicação Espaço-Temporal (RF-09, RF-10, RN-01 a RN-07, AT-05)
* **Cálculo Geodésico Rigoroso WGS84:**
  * Utilização da fórmula de Haversine para distâncias na superfície terrestre, eliminando distorções de conversão planar direta de graus para metros.
* **Deduplicação em Raio de 10 Metros:**
  * Algoritmo de agrupamento espacial que consolida múltiplos frames do mesmo defeito em uma **Ocorrência Única Auditável**.
* **União e Separação Manual de Ocorrências (Refinamentos RF-09):**
  * Endpoints para unir múltiplos agrupamentos ou separar ocorrências manualmente, mantendo o histórico de todas as detecções originais.
* **Associação Territorial e Viária Automática:**
  * *Point-in-Polygon* (Shapely) para enquadramento no polígono do bairro;
  * Proximidade ao eixo da via (tolerância geodésica de 25m) com sinalização de ambiguidade em bifurcações.
* **Extensão Única Observada ($L_{obs}$) sem Sobrecontagem (RN-05):**
  * Discretização espacial em células geodésicas únicas de 50 metros, garantindo que passagens repetidas na mesma via não inflem o denominador da inspeção.

### 4. Metodologia Oficial do IDU-Pavimento e Limitações de Dados (RF-15, RN-07, Seção 08, AT-06)
* **Fórmulas Matemáticas de Cálculo:**
  * **Cobertura da Malha Viária:**
    $$C = \frac{L_{obs}}{L_{eleg}}$$
  * **Densidade de Ocorrências:**
    $$D = \frac{N}{L_{obs}} \quad (\text{ocorrências confirmadas por km})$$
  * **Carga Ponderada de Severidade de Defeitos:**
    $$S = \frac{\sum (w_i \cdot s_i)}{L_{obs}}$$
  * **Score do IDU-Pavimento (0 a 100):**
    $$\text{IDU} = 100 \cdot \min\left(1, \frac{S}{S_{ref}}\right) \quad (\text{com } S_{ref} = 40{,}0/\text{km})$$
* **Critérios Estritos de Elegibilidade Estatística e Limitações Amostrais (RN-07):**
  A emissão de relatórios oficiais e a validação do IDU estão sujeitas a critérios matemáticos que evitam indução a erros de planejamento:
  * **Extensão Mínima Amostrada:** $L_{obs} \ge 1{,}0\text{ km}$. Campanhas com extensão inferior carecem de significância estatística sobre o estado da malha.
  * **Cobertura Mínima da Malha Elegível:** $C = \frac{L_{obs}}{L_{eleg}} \ge 60{,}0\%$. Traçados que não percorram pelo menos 60% das vias estruturantes do território são classificados como estatisticamente não representativos.
  * **Tratamento de Inelegibilidade pelo Sistema:**
    * O bairro/campanha é registrado com `elegivel = False` e anotação técnica detalhada em `motivo_inelegivel` (ex: *"Amostragem insuficiente: cobertura de 45.2% inferior ao limiar estatutário de 60.0%"*);
    * O PDF Executivo estampa tarja e selo de advertência informando que os índices **não possuem validade para fins de dotação orçamentária definitiva**;
    * A conclusão automatizada suprime rankings de prioridade e gera recomendação de vistoria complementar para suprir a lacuna amostral.
* **Diferenciação entre Territórios Cadastrados vs Territórios com Amostragem Ativa:**
  * **Território Apenas Cadastrado (Malha Base):** Possui polígono vetorial e malha elegível ($L_{eleg}$) homologados no banco (via OSM Overpass ou GeoSampa), mas sem passagens veiculares cadastradas ($L_{obs} = 0\text{ km}$, ex: *Vila Madalena*, *Itaim Bibi*). O sistema impede a emissão de IDU definitivo até que haja coleta.
  * **Território com Campanha Completa e Elegível:** Possui telemetria GPS e lotes de vídeo/foto processados que cumprem simultaneamente $L_{obs} \ge 1\text{ km}$ e $C \ge 60\%$.
* **Inventário de Capacidade de Emissão Atual:**
  * **4 Relatórios Executivos Oficiais por Município:** São Paulo ($68.8\%$), Rio de Janeiro ($63.2\%$), Belo Horizonte ($90.0\%$) e Curitiba ($63.5\%$);
  * **7 Relatórios Monográficos Independentes por Bairro:** Cerqueira César ($74.0\%$), Bela Vista ($63.6\%$), Pinheiros ($67.7\%$), Consolação ($70.0\%$), Copacabana ($63.2\%$), Savassi ($90.0\%$) e Batel ($63.5\%$).
* **Como Superar a Limitação de Amostragem em Novos Municípios:**
  1. Ingestão territorial instantânea via `POST /v1/territorio/importar-osm` (OpenStreetMap global) ou `POST /v1/territorio/importar-geosampa`;
  2. Coleta veicular embarcada (câmeras de celulares ou gravadores veiculares dashcam) em traçado contínuo;
  3. Ingestão de vídeo via `app/services/video.py` ou manifesto CSV com interpolação geodésica temporal de GPS para cobrir $\ge 60\%$ das vias.
* **Faixas Oficiais de Severidade:**
  * $[0, 25)$: **Baixa**
  * $[25, 50)$: **Moderada**
  * $[50, 75)$: **Alta**
  * $[75, 100]$: **Muito Alta**
* **Comparativo Municipal Agregado Ponderado:**
  * $\sum N / \sum L_{obs}$ dos territórios elegíveis (evitando distorções de médias aritméticas simples de bairros).
* **Parâmetros Parametrizáveis e Versionados (`/v1/parametros`):**
  * Configuração de $S_{ref}$, limiar de cobertura, raio de agrupamento e pesos por classe com justificativa e trilha de auditoria.

### 5. Revisão Técnica, Trilha de Auditoria e Ordens de Serviço (RF-08, RF-14, RF-20, AT-07)
* **Concorrência Otimista (Optimistic Locking):**
  * Controle de versão de ocorrências (`version`). Retorna `HTTP 409 Conflict` em caso de edições concorrentes simultâneas por múltiplos engenheiros.
* **Trilha de Auditoria Completa:**
  * Histórico de todas as alterações com identificador do autor, timestamp UTC, decisão, campos anteriores/novos e justificativa técnica.
* **Gestão de Reinspeções e Intervenções de Campo (RF-14):**
  * Diferenciação obrigatória entre:
    * `dano_persistente`: defeito ainda presente em vistoria de retorno;
    * `reparo_confirmado`: defeito corrigido pela equipe de obras (exige foto-evidência para resolução);
    * `ausencia_observacao`: passagem rápida onde a IA não captou o dano (não permite marcar como resolvida).
* **Ordens de Serviço Municipais Integradas (RF-20):**
  * Vínculo de ocorrências a Ordens de Serviço (OS) com controle de número, contratada, prazo e status de execução.

### 6. Relatórios Executivos e Exportações (RF-16 a RF-18, Seção 10, AT-08)
* **Relatório Executivo Oficial em PDF (ReportLab):**
  * Tabela de indicadores calculados ($L_{obs}$, $L_{eleg}$, Cobertura %, Densidade e Faixa IDU);
  * **Análise Gráfica Comparativa Integrada:** Gráficos coloridos de barras de severidade e distribuição percentual de falhas RDD2022 embutidos diretamente no PDF;
  * Conclusões determinísticas por regras sem especulações físicas ou financeiras não homologadas;
  * Amostra auditável de ocorrências prioritárias com coordenadas e via;
  * Declaração de salvaguardas éticas e limitações do modelo de visão;
  * **Carimbo Criptográfico:** Hash SHA-256 gerado e registrado no banco para auditoria jurídica e controle de imutabilidade.
* **Exportação Aberta Estruturada:**
  * CSV técnico (`/v1/export/csv`);
  * GeoJSON WGS84 FeatureCollection (`/v1/export/geojson`).
* **Painel Interativo de Degradação Urbana Viária:**
  * Dashboard web responsivo (`dashboard_bairros.html`) com filtros por território, réguas de cobertura viária e gráficos dinâmicos de taxonomia.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Propósito |
|---|---|---|
| **Linguagem & Runtime** | Python 3.11+ | Performance e tipagem estática moderna |
| **Framework Web & API** | FastAPI + Pydantic v2 + Uvicorn | API REST assíncrona, OpenAPI / Swagger automático |
| **Banco de Dados** | PostgreSQL 16 + PostGIS / SQLite | Persistência relacional com suporte espacial corporativo |
| **ORM** | SQLAlchemy 2.0 | Mapeamento relacional e controle de concorrência |
| **Geometria & Espacial** | Shapely 2.0 + Fórmulas Geodésicas WGS84 | Operações geométricas (*Point-in-Polygon*, Haversine) |
| **Visão Computacional** | OpenCV (Headless) + Pillow | Pré-processamento, métricas de exposição/foco e crops |
| **Geração de PDF** | ReportLab 5.1 | Geração determinística de relatórios executivos vetorizados |
| **Testes Automatizados** | Pytest 9.1 + AnyIO + HTTPX | Testes unitários, de regressão e de critérios de aceite |
| **Containerização** | Docker & Docker Compose | Implantação isolada e orquestração de banco espacial |

---

## 🚀 Como Executar o Projeto

### 1. Instalação Local com Ambiente Virtual

```powershell
# Criação e ativação do ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalação das dependências
pip install -e .
```

### 2. Executar a Suíte de Testes Automatizados (20/20 Testes)
```powershell
.\.venv\Scripts\pytest -v
```
*Testa rigorosamente: critérios de aceite AT-01 a AT-08, concorrência otimista 409, expansão P1 (intervenções e OS), deduplicação 10m, cálculo matemático do IDU, persistência de gráficos e integração de dados abertos (OSM e GeoSampa).*

### 3. Gerar Campanhas Nacionais Multi-Capitais (São Paulo, Rio, BH e Curitiba)
Executa a ingestão territorial aberta via OpenStreetMap, simula as passagens veiculares com conformidade estatística ($C \ge 60\%$), calcula os IDUs municipais e emite 4 Relatórios Executivos em PDF com gráficos comparativos e hashes SHA-256:
```powershell
.\.venv\Scripts\python sample_data/generate_national_reports.py
```

### 4. Popular Dados da Campanha Piloto Original (São Paulo)
Gera trilhas GPS contínuas nos bairros **Cerqueira César**, **Bela Vista** e **Pinheiros**:
```powershell
.\.venv\Scripts\python sample_data/seed_pilot.py
```

### 5. Iniciar o Servidor FastAPI
```powershell
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
* Acesse a interface web: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* Documentação interativa Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* Documentação técnica ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 6. Execução em Produção via Docker Compose (PostgreSQL 16 + PostGIS)
```bash
docker compose up -d --build
```
Inicializa o contêiner `urbanvision_db` (PostGIS com healthcheck) e `urbanvision_web` (FastAPI) com volumes persistentes para uploads, crops e relatórios.

---

## 📡 Catálogo Completo da API REST (`/v1`)

### Campanhas e Lotes
* `POST /v1/campanhas` — Criar campanha territorial de auditoria
* `GET /v1/campanhas` — Listar campanhas cadastradas
* `POST /v1/lotes` — Abrir lote para ingestão de dados
* `POST /v1/lotes/{id}/imagens` — Upload de imagens com validação EXIF, SHA-256 e nitidez
* `POST /v1/lotes/{id}/execucoes` — Executar inferência do modelo e agrupamento de ocorrências
* `GET /v1/execucoes/{id}` — Consultar progresso e estatísticas de processamento do lote

### Ocorrências e Revisão Técnica
* `GET /v1/ocorrencias` — Listar ocorrências únicas com filtros (campanha, bairro, classe, status)
* `GET /v1/ocorrencias/{id}` — Detalhes da ocorrência com histórico de detecções e fotos
* `PATCH /v1/ocorrencias/{id}` — Revisão técnica com concorrência otimista (`HTTP 409` em conflito)
* `POST /v1/ocorrencias/unir` — Fusão manual de múltiplas ocorrências vizinhas
* `POST /v1/ocorrencias/{id}/separar` — Separação de ocorrência em agrupamentos distintos
* `POST /v1/ocorrencias/{id}/intervencoes` — Registrar reinspeção (`dano_persistente`, `reparo_confirmado`, `ausencia_observacao`)
* `GET /v1/ocorrencias/{id}/historico` — Trilha completa de auditoria e intervenções

### Ordens de Serviço (OS)
* `POST /v1/ordens-servico` — Vincular ocorrência homologada a uma Ordem de Serviço municipal
* `GET /v1/ordens-servico` — Listar ordens de serviço ativas e concluídas

### Indicadores IDU e Relatórios Oficiais
* `GET /v1/indicadores` — Calcular/obter IDU-Pavimento, extensão observada e cobertura por bairro
* `POST /v1/relatorios` — Gerar Relatório Executivo Oficial em PDF com gráficos e hash SHA-256
* `GET /v1/relatorios/{id}/download` — Baixar arquivo PDF do relatório gerado
* `GET /v1/export/csv` — Exportar ocorrências em CSV estruturado
* `GET /v1/export/geojson` — Exportar ocorrências em padrão GeoJSON WGS84

### Território e Integrações com Dados Abertos (OSM & GeoSampa)
* `POST /v1/territorio/importar-osm` — Importação automatizada via OpenStreetMap (Overpass API) com cálculo geodésico da malha elegível ($L_{eleg}$) e cadastro de vias estruturantes
* `POST /v1/territorio/importar-geosampa` — Ingestão de arquivos oficiais GeoJSON do GeoSampa (Prefeitura de São Paulo)
* `POST /v1/territorio/bairros` | `GET /v1/territorio/bairros` — Cadastro manual e listagem de bairros e malhas elegíveis
* `POST /v1/territorio/vias` | `GET /v1/territorio/vias` — Cadastro e consulta de eixos viários e trechos elegíveis
* `POST /v1/modelos` | `GET /v1/modelos` — Catálogo e versionamento de pesos de modelos de IA
* `POST /v1/parametros` | `GET /v1/parametros` — Gestão e versionamento de parâmetros de calibração do IDU

---

## 🔒 Salvaguardas Éticas e Limitações Técnicas

Conforme o princípio da **Seção 01 e Seção 11 do caderno de requisitos**:
1. O **UrbanVision Analytics** apoia a triagem técnica, priorização de vistorias e planejamento de manutenção viária.
2. O sistema **não estima profundidade milimétrica de buracos, resistência estrutural de subleito, causa raiz de falhas nem custos de engenharia apenas por fotografia**.
3. Toda e qualquer ordem de serviço de recapeamento ou intervenção pesada requer homologação *in loco* por engenheiro civil habilitado.

---

## 📄 Licença
Projeto desenvolvido para auditoria e gestão da infraestrutura pública urbana. Todos os direitos reservados.
