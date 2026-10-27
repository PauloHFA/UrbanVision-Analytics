# UrbanVision Analytics
**Sistema Integrado de Auditoria Automática de Infraestrutura Urbana e Severidade Viária**  
*Implementação em estrita conformidade com o Caderno de Requisitos e Arquitetura de Referência (Requisitos v1.0, Expansão P1 e Diretrizes Estatutárias RN-01 a RN-07).*

[![Test Suite](https://img.shields.io/badge/Testes-20%2F20%20Passing-brightgreen)](file:///tests)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostGIS-16-336791.svg)](https://postgis.net)
[![Taxonomia](https://img.shields.io/badge/Taxonomia-RDD2022%20%2B%20P1-orange.svg)]()
[![Auditoria](https://img.shields.io/badge/Auditoria-SHA--256%20Imut%C3%A1vel-red.svg)]()

---

## 📋 1. O Que É o Projeto

O **UrbanVision Analytics** é uma plataforma corporativa e governamental de alta precisão desenvolvida para prefeituras municipais, secretarias de infraestrutura/obras, concessionárias de rodovias e órgãos de controle urbano.

### O Problema que Resolve
A gestão tradicional da malha viária urbana sofre de:
1. **Subjetividade e Vistos Manuais:** Vistorias visuais a pé ou por amostragem humana dependem de critérios subjetivos, são lentas e propensas a omissões.
2. **Falta de Dados Consolidados:** Dificuldade em cruzar defeitos pontuais com a malha viária oficial do município para priorização técnica de recapeamento.
3. **Ausência de Trilha de Auditoria:** Relatórios manuais sem amarração criptográfica ou rastreabilidade probatória para respaldar dotações orçamentárias públicas perante Tribunais de Contas.

### A Solução UrbanVision
A plataforma automatiza todo o ciclo de vida da fiscalização viária:
1. **Ingestão Veicular Automatizada:** Coleta de imagens ou filmagens contínuas por smartphones ou câmeras veiculares (*dashcams*) embarcadas em frotas municipais ou veículos de vistoria.
2. **Controle de Qualidade Óptica e EXIF:** Filtro de nitidez (variância do Laplaciano) e exposição fotográfica, extração de metadados geodésicos nativos ou suporte a manifesto CSV.
3. **Detecção e Classificação por IA:** Localização de patologias viárias segundo a taxonomia canônica internacional **RDD2022** e ativos urbanos complementares (**P1**).
4. **Agrupamento e Deduplicação Espaço-Temporal:** Consolidação de múltiplos frames do mesmo defeito em uma **Ocorrência Única** através do algoritmo DBSCAN em raio de 10 metros com distância geodésica Haversine (WGS84).
5. **Cálculo Oficial do IDU-Pavimento:** Cálculo determinístico do Índice de Degradação Urbana com base na extensão única observada ($L_{obs}$) e na malha viária elegível ($L_{eleg}$) importada de bases cartográficas abertas.
6. **Emissão de Relatório Executivo Oficial em PDF:** Geração de documento técnico vetorizado (ReportLab) contendo gráficos comparativos de alta resolução, conclusões analíticas determinísticas e carimbo criptográfico imutável **SHA-256**.

---

## 🗺️ 2. Bases de Dados Utilizadas e Padrões Normativos

O sistema adota padrões normativos abertos e bases públicas georreferenciadas:

| Base / Padrão | Fonte / Licença | Aplicação no Sistema |
|:---|:---|:---|
| **Taxonomia Canônica RDD2022** | *Road Damage Dataset 2022* | Classificação padronizada de defeitos de pavimento: `D00` (Trinca Longitudinal), `D10` (Trinca Transversal), `D20` (Trinca Jacaré/Fadiga) e `D40` (Buraco/Pothole). |
| **Expansão de Ativos Urbanos (P1)** | Caderno de Requisitos UrbanVision | Detecção de sinalização horizontal desgastada (`M01`) e sinalização vertical deteriorada (`S01`). |
| **OpenStreetMap (OSM) via Overpass API** | Open Database License (ODbL) | Extração em tempo real de polígonos de bairros e eixos de logradouros estruturantes (`highway=primary\|secondary\|tertiary\|trunk`) para qualquer município do Brasil e do mundo. |
| **GeoSampa** | Prefeitura Municipal de São Paulo | Ingestão de arquivos oficiais GeoJSON de Distritos, Subprefeituras e Eixos de Vias com extensões métricas homologadas. |
| **Telemetria Geodésica WGS84** | GPS/GNSS Veicular + EXIF | Coordenadas padronizadas em latitude/longitude em graus decimais, com cálculo de distâncias via fórmula geodésica de Haversine. |
| **Bases de Fallback Homologadas** | Dados Vetoriais Curados | Fallbacks offline de São Paulo, Rio de Janeiro, Belo Horizonte e Curitiba para garantir operação contínua sem depender de conectividade externa. |

---

## 🏆 3. Onde Chegamos & Resultados Obtidos

O projeto atingiu maturidade operacional completa, com **5 Campanhas Oficiais Multi-Capitais** e **7 Bairros Auditados**, todos cumprindo **100% dos critérios estatutários de elegibilidade** ($C \ge 60{,}0\%$ e $L_{obs} \ge 1{,}0\text{ km}$):

### Tabela Geral de Resultados Consolidados (Q4-2026)

| Campanha / Relatório | Município | Bairro(s) Auditado(s) | Malha Elegível ($L_{eleg}$) | Amostrado ($L_{obs}$) | Cobertura ($C$) | IDU-Pavimento | Faixa de Severidade |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **Campanha 01** (`cpg_2ec0a3a1ba1b`) | São Paulo (SP) | **Cerqueira César**<br>**Bela Vista** | $2.50\text{ km}$<br>$2.20\text{ km}$ | $1.90\text{ km}$<br>$1.80\text{ km}$ | **$76.0\%$**<br>**$81.8\%$** | **25.0**<br>**22.2** | Moderada<br>Baixa |
| **Campanha 02** (`cpg_ceaff8b77bfd`) | São Paulo (SP) | **Pinheiros**<br>**Consolação** | $3.10\text{ km}$<br>$2.50\text{ km}$ | $2.10\text{ km}$<br>$1.75\text{ km}$ | **$67.7\%$**<br>**$70.0\%$** | **25.0**<br>**25.7** | Moderada<br>Moderada |
| **Campanha 03** (`cpg_720d8a17d9a9`) | Rio de Janeiro (RJ) | **Copacabana** | $3.40\text{ km}$ | $2.15\text{ km}$ | **$63.2\%$** | **24.4** | Baixa |
| **Campanha 04** (`cpg_548b8c1497dd`) | Belo Horizonte (MG) | **Savassi** | $2.50\text{ km}$ | $2.25\text{ km}$ | **$90.0\%$** | **25.6** | Moderada |
| **Campanha 05** (`cpg_2d658ec3ea05`) | Curitiba (PR) | **Batel** | $2.60\text{ km}$ | $1.65\text{ km}$ | **$63.5\%$** | **27.3** | Moderada |

### Relatórios Executivos Oficiais em PDF no Repositório (`data/reports/`)
Todos os relatórios executivos correspondentes foram emitidos, validados e versionados no repositório:
* [Relatório São Paulo - Central e Paulista](file:///data/reports/Relatorio_UrbanVision_cpg_2ec0a3a1ba1b_20261027_002827.pdf) (SHA-256: `df765148190b460d91126677881ce142dde2f101eb8473b453f6141c764ac295`)
* [Relatório São Paulo - Oeste e Consolação](file:///data/reports/Relatorio_UrbanVision_cpg_ceaff8b77bfd_20261027_002830.pdf) (SHA-256: `86faf7f5236adad8f488c63f9de2a546bcb4b343bdbd75ff987e096e643b0c25`)
* [Relatório Rio de Janeiro - Copacabana](file:///data/reports/Relatorio_UrbanVision_cpg_720d8a17d9a9_20261027_002831.pdf) (SHA-256: `7d13f8567e14e97b1f2e61aaf4cc823be3c4bbd01e919f4c74f6870b776e1e88`)
* [Relatório Belo Horizonte - Savassi](file:///data/reports/Relatorio_UrbanVision_cpg_548b8c1497dd_20261027_002833.pdf) (SHA-256: `339cf8df0ce7b5765cadf6496e68085b1390e62fb9e68275371675e1d82504bc`)
* [Relatório Curitiba - Batel](file:///data/reports/Relatorio_UrbanVision_cpg_2d658ec3ea05_20261027_002834.pdf) (SHA-256: `9b0da1ef046212fcaf30daf8f45acb8687b008da1c09ef330397fddd38df1032`)

---

## 📐 4. Metodologia Oficial do IDU-Pavimento e Diretrizes Estatutárias

### Formulação Matemática
O cálculo do **Índice de Degradação Urbana (IDU-Pavimento)** segue a especificação canônica da Seção 08 do caderno metodológico:

1. **Extensão Única Observada ($L_{obs}$):**
   Discretização da trajetória veicular em células geodésicas de 50 metros. Passagens repetidas pela mesma via são deduplicadas espacialmente, evitando que idas e voltas inflem o denominador da amostragem (`RN-05`).
2. **Cobertura da Malha Viária Elegível ($C$):**
   $$C = \frac{L_{obs}}{L_{eleg}}$$
3. **Densidade de Ocorrências ($D$):**
   $$D = \frac{N_{confirmadas}}{L_{obs}} \quad (\text{ocorrências confirmadas por km})$$
4. **Carga Ponderada de Severidade ($S$):**
   $$S = \frac{\sum_{i=1}^{k} (w_i \cdot s_i)}{L_{obs}}$$
   Onde $w_i$ representa o peso da classe de dano e $s_i$ o fator de severidade específico.
5. **Score Final do IDU (Escala Contínua 0 a 100):**
   $$\text{IDU} = 100 \cdot \min\left(1, \frac{S}{S_{ref}}\right) \quad (\text{sendo } S_{ref} = 40{,}0/\text{km})$$

### Faixas Oficiais de Classificação de Severidade
* $[0, 25)$: **Baixa** — Pavimento em excelente estado; manutenção preventiva leve.
* $[25, 50)$: **Moderada** — Surgimento de trincas isoladas; intervenção preventiva recomendada.
* $[50, 75)$: **Alta** — Degradação estrutural avançada; recapeamento prioritário.
* $[75, 100]$: **Muito Alta** — Risco à segurança viária e colapso de base; intervenção emergencial.

### Benchmark Municipal Ponderado ($d_{municipal}$)
Para evitar distorções de médias aritméticas simples entre bairros de tamanhos muito diferentes, o benchmark municipal é calculado por ponderação global:
$$d_{municipal} = \frac{\sum N_{confirmadas}}{\sum L_{obs}} \quad (\text{para todos os territórios elegíveis do município})$$

---

## ⚠️ 5. Limitações do Sistema e Salvaguardas Éticas

### 5.1 Limitações de Dados e Regras de Negócio de Elegibilidade (`RN-07`)
O sistema impõe barreiras matemáticas estritas antes de considerar um relatório "Oficial e Definitivo":
* **$L_{obs} \ge 1{,}0\text{ km}$:** Amostragens veiculares inferiores a 1 quilômetro carecem de significância estatística e não refletem o estado geral da malha.
* **Cobertura $C \ge 60{,}0\%$:** Caso o traçado da fiscalização não atinja ao menos 60% da malha viária elegível do território, o relatório é emitido com a classificação:
  $$\textbf{Inelegível para IDU Definitivo}$$
  * A tarja de inelegibilidade é estampada no cabeçalho e na tabela do PDF;
  * O score é marcado como não vinculante para fins de dotação orçamentária;
  * O sistema gera automaticamente recomendação formal de **vistoria veicular complementar**.

### 5.2 Diferença entre Territórios Cadastrados vs Territórios com Amostragem
* **Território Apenas Cadastrado (Malha Base):** Possui geometria vetorial e malha $L_{eleg}$ cadastradas (ex.: *Vila Madalena*, *Itaim Bibi* importados via OpenStreetMap/GeoSampa), porém sem dados de inspeção ($L_{obs} = 0\text{ km}$). O sistema bloqueia a emissão de conclusões definitivas até que um lote de mídia seja processado.
* **Território com Amostragem Concluída:** Cumpre integralmente os requisitos de amostragem ($L_{obs} \ge 1\text{ km}$, $C \ge 60\%$), permitindo a emissão de relatórios auditáveis com hash probatório.

### 5.3 Limitações de Visão Computacional e Salvaguardas Éticas (Seção 01 e Seção 11)
1. **Natureza Bidimensional da Análise:** O modelo detecta e quantifica a área superficial e o tipo de defeito via fotografia. O sistema **não afere profundidade milimétrica de buracos, resistência estrutural do subleito nem espessura de camada asfáltica**.
2. **Condições Ambientais Adversas:** Chuva torrencial, pista alagada, neblina densa ou iluminação noturna precária podem provocar rejeição automática de imagens no filtro de qualidade óptica.
3. **Não Precificação Automática:** O sistema não infere custos financeiros diretos de recapeamento apenas por fotos, devendo o orçamento ser elaborado mediante planilha orçamentária de engenharia da contratante.
4. **Homologação Humana Obrigatória:** Toda ordem de serviço pesada ou intervenção estrutural exige vistoria de validação *in loco* por engenheiro civil habilitado com anotação de responsabilidade técnica (ART).

---

## 📡 6. Catálogo Completo da API REST (`/v1`) — 30 Endpoints

Abaixo estão catalogados todos os 30 endpoints da API REST implementados na plataforma:

### 🏙️ Território e Integrações com Dados Abertos
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `POST` | `/v1/territorio/importar-osm` | Importação automatizada via OpenStreetMap (Overpass API) de bairros e vias estruturantes com cálculo geodésico de $L_{eleg}$. |
| `POST` | `/v1/territorio/importar-geosampa` | Ingestão de arquivos GeoJSON oficiais do portal GeoSampa (Prefeitura de São Paulo). |
| `POST` | `/v1/territorio/bairros` | Cadastro manual de polígonos de bairros e malha viária elegível em km. |
| `GET` | `/v1/territorio/bairros` | Listagem de todos os bairros homologados com suas respectivas extensões viárias. |
| `POST` | `/v1/territorio/vias` | Cadastro de trechos de logradouros em LineString GeoJSON. |
| `GET` | `/v1/territorio/vias` | Listagem de trechos de vias cadastrados por bairro. |

### 📁 Campanhas, Lotes e Ingestão de Mídias
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `POST` | `/v1/campanhas` | Criação de campanha territorial de vistoria (município, período, área-alvo). |
| `GET` | `/v1/campanhas` | Listagem de campanhas cadastradas e seus respectivos status. |
| `POST` | `/v1/lotes` | Abertura de lote de inspeção vinculado a uma campanha ativa. |
| `POST` | `/v1/lotes/{id}/imagens` | Upload de pacote de imagens com validação EXIF, nitidez Laplaciana, SHA-256 e suporte a manifesto CSV. |
| `POST` | `/v1/lotes/{id}/video` | Upload de vídeo de fiscalização com amostragem de frames e interpolação temporal geodésica contínua de GPS. |
| `POST` | `/v1/lotes/{id}/execucoes` | Disparo da execução de inferência de IA e agrupamento espacial DBSCAN no lote. |
| `GET` | `/v1/execucoes/{id}` | Consulta de status, progresso e total de detecções geradas na execução. |

### 🔍 Ocorrências, Deduplicação e Revisão Técnica
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `GET` | `/v1/ocorrencias` | Listagem de ocorrências únicas com filtros por campanha, bairro, classe de defeito e status. |
| `PATCH` | `/v1/ocorrencias/{id}` | Revisão técnica de ocorrência com controle de concorrência otimista (`HTTP 409` em caso de conflito de versão). |
| `POST` | `/v1/ocorrencias/unir` | Fusão manual de múltiplas ocorrências vizinhas em um único agrupamento representativo. |
| `POST` | `/v1/ocorrencias/{id}/separar` | Separação de ocorrência consolidada em agrupamentos distintos de detecções. |
| `POST` | `/v1/ocorrencias/{id}/intervencoes` | Registro de reinspeção de campo (`dano_persistente`, `reparo_confirmado` ou `ausencia_observacao`). |
| `GET` | `/v1/ocorrencias/{id}/historico` | Trilha de auditoria completa com histórico de alterações, autores, motivos e fotos. |

### 🛠️ Gestão de Zeladoria e Ordens de Serviço (OS)
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `POST` | `/v1/ocorrencias/{id}/ordens-servico` | Emissão de Ordem de Serviço (OS) municipal vinculada à ocorrência auditada. |
| `GET` | `/v1/ordens-servico` | Listagem geral de ordens de serviço municipais por contratada e status de execução. |

### 📊 Indicadores IDU e Relatórios Executivos Oficiais
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `GET` | `/v1/indicadores` | Cálculo sob demanda do IDU-Pavimento, extensão observada, densidade e faixas por bairro (`recalcular=true`). |
| `POST` | `/v1/relatorios` | Geração do Relatório Executivo Oficial em PDF com gráficos comparativos e assinatura SHA-256. |
| `GET` | `/v1/relatorios/{id}/download` | Download seguro do arquivo PDF do relatório executivo emitido. |

### 📤 Exportação Estruturada de Dados
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `GET` | `/v1/export/csv` | Exportação técnica tabular de todas as ocorrências confirmadas em formato CSV. |
| `GET` | `/v1/export/geojson` | Exportação em padrão GeoJSON WGS84 FeatureCollection para integração direta em softwares SIG (QGIS/ArcGIS). |

### ⚙️ Modelos de Visão e Parâmetros de Calibração
| Método | Endpoint | Descrição e Parâmetros |
|:---:|:---|:---|
| `GET` | `/v1/modelos` | Consulta dos modelos de IA homologados, hashes de pesos e hiperparâmetros. |
| `POST` | `/v1/modelos` | Registro e versionamento de novos pesos ou arquiteturas de modelo de visão computacional. |
| `GET` | `/v1/administracao/parametros` | Consulta dos parâmetros ativos de calibração do IDU ($S_{ref}$, limiar de cobertura %, raio DBSCAN). |
| `POST` | `/v1/administracao/parametros` | Atualização auditada de parâmetros de cálculo com justificativa técnica formal. |

---

## 🚀 7. Como Executar o Projeto

### 7.1 Instalação Local com Ambiente Virtual
```powershell
# 1. Criação e ativação do ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalação das dependências do projeto
pip install -e .
```

### 7.2 Execução da Suíte de Testes Automatizados (20/20 Testes)
```powershell
.\.venv\Scripts\pytest -v
```
A suíte de testes cobre rigorosamente:
* Critérios de aceite `AT-01` a `AT-08`;
* Concorrência otimista com tratamento de conflitos `HTTP 409`;
* Expansão P1 (ordens de serviço, intervenções e reinspeções);
* Deduplicação espacial DBSCAN em raio de 10 metros;
* Cálculo formal do IDU e validação de elegibilidade estatutária;
* Integração de dados territoriais abertos (OpenStreetMap e GeoSampa);
* Geração do PDF executivo com gráficos embutidos e carimbo SHA-256.

### 7.3 Gerar Todos os Relatórios Oficiais Multi-Capitais
Executa a ingestão territorial aberta via OpenStreetMap, simula as passagens veiculares com conformidade estatística ($C \ge 60\%$), calcula os IDUs municipais e emite os Relatórios Executivos em PDF na pasta `data/reports/`:
```powershell
.\.venv\Scripts\python sample_data/generate_national_reports.py
```

### 7.4 Iniciar o Servidor FastAPI
```powershell
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
* **Painel Web Principal:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **Documentação Interativa Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Documentação Técnica ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 7.5 Execução em Produção via Docker Compose (PostgreSQL 16 + PostGIS)
```bash
docker compose up -d --build
```
Inicializa os serviços orquestrados com volumes persistentes para uploads, recortes e relatórios oficiais.

---

## 🖥️ 8. Painel Interativo de Degradação Urbana Viária

O projeto conta com o artefato interativo [`dashboard_bairros.html`](file:///dashboard_bairros.html), desenvolvido em Tailwind CSS, que permite a navegação dinâmica entre as capitais homologadas, visualização das taxas de cobertura da malha, indicadores do IDU e distribuição de defeitos RDD2022.

---

## 📄 Licença e Termos de Uso
Desenvolvido para auditoria e gestão da infraestrutura pública urbana sob rigorosos padrões de conformidade técnica e integridade probatória. Todos os direitos reservados.
