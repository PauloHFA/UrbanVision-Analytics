# UrbanVision Analytics
**Sistema de Auditoria Automática de Infraestrutura Urbana e Severidade Viária**
*Implementação em conformidade com o Documento de Requisitos e Arquitetura de Referência (Requisitos v1.0, 25/10/2026).*

---

## 🎯 Escopo do MVP (P0)

1. **Ingestão e Qualidade (RF-01 a RF-04, AT-01)**:
   - Ingestão de JPEG/PNG, cálculo de SHA-256 e deduplicação de imagens exatas.
   - Extração de metadados EXIF (GPS Latitude, Longitude, Altitude e Timestamp UTC).
   - Verificação técnica de exposição (sub/superexposição) e nitidez (variância de Laplaciano).
2. **Detecção e Taxonomia RDD2022 (RF-05, RF-06, RD-01, RD-04)**:
   - Suporte canônico às 4 classes: `D00` (Trinca Longitudinal), `D10` (Trinca Transversal), `D20` (Trinca Jacaré/Malha), `D40` (Buraco/Pothole).
   - Armazenamento separado de predições brutas, recortes (crops) e metadados de inferência.
3. **Agrupamento e Deduplicação Espaço-Temporal (RF-09, RN-06, AT-05)**:
   - Agrupamento em raio de 10 metros para fundir múltiplos frames do mesmo defeito em uma Ocorrência Única auditável.
4. **Associação Territorial e Georreferenciamento (RF-10, RN-01 a RN-07)**:
   - Cálculo geodésico rigoroso WGS84 (método de Haversine) sem interpretar graus como metros.
   - Cálculo da extensão única inspecionada ($L_{obs}$) evitando sobrecontagem em passagens repetidas na mesma via.
   - Registro de incerteza da captura e restrição de atribuição fora de tolerância.
5. **Cálculo do IDU-Pavimento (RF-15, Seção 08, AT-06)**:
   - Fórmulas exatas:
     $$\text{Cobertura } C = \frac{L_{obs}}{L_{eleg}}, \quad \text{Densidade } D = \frac{N}{L_{obs}}, \quad \text{Carga } S = \frac{\sum w \cdot s}{L_{obs}}, \quad IDU = 100 \cdot \min\left(1, \frac{S}{S_{ref}}\right)$$
   - Elegibilidade: Cobertura $\ge 60\%$ e $L_{obs} \ge 1,0$ km.
   - Faixas de severidade: $[0, 25)$ Baixa, $[25, 50)$ Moderada, $[50, 75)$ Alta, $[75, 100]$ Muito alta.
   - Comparação municipal agregada ponderada: $\sum N / \sum L_{obs}$ dos territórios elegíveis.
6. **Revisão Técnica com Concorrência Otimista (RF-08, AT-07)**:
   - Trilha de auditoria (revisor, data/hora UTC, decisão, valores anteriores e novos, justificativa).
   - Versionamento de ocorrências: retorno de `HTTP 409 Conflict` em caso de edição concorrente.
7. **Relatórios e Exportações (RF-16 a RF-18, AT-08)**:
   - Geração de conclusões textuais determinísticas por regras, sem inferir custos ou causas físicas sem laudo de engenharia.
   - Relatório Executivo profissional em PDF emitido via ReportLab com Hash SHA-256 e tabela comparativa.
   - Exportação em CSV e GeoJSON WGS84.
8. **Interface Web Operacional (Seção 04)**:
   - Dashboard completo com abas: Visão Geral, Campanhas & Lotes, Importações, Fila de Revisão de Evidências, Mapa Operacional (Leaflet.js com camadas interativas e círculos de incerteza), Indicadores & IDU e Relatórios.

---

## 🚀 Como Executar o Sistema

### 1. Pré-requisitos
- Python 3.11+ instalado (gerenciado com [uv](https://github.com/astral-sh/uv))

### 2. Executar os Testes Automatizados (Critérios de Aceite AT-01 a AT-08)
```powershell
uv run pytest -v
```

### 3. Popular Dados do Piloto (Opcional)
```powershell
uv run python sample_data/seed_pilot.py
```

### 4. Iniciar o Servidor Web e API
```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Acesse o sistema no navegador:
- **Interface Operacional / Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Documentação Swagger OpenAPI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Documentação ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 Contratos de API Implementados (`/v1`)

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/v1/campanhas` | Cadastrar campanha territorial com município, período e responsável |
| `GET` | `/v1/campanhas` | Listar campanhas cadastradas |
| `POST` | `/v1/lotes` | Criar lote para envio de mídias |
| `POST` | `/v1/lotes/{id}/imagens` | Upload de imagens com validação EXIF, SHA-256 e qualidade |
| `POST` | `/v1/lotes/{id}/execucoes` | Executar inferência e agrupamento em ocorrências únicas |
| `GET` | `/v1/execucoes/{id}` | Status e progresso da execução |
| `GET` | `/v1/ocorrencias` | Listar e filtrar ocorrências (por campanha, classe, status, bairro) |
| `PATCH`| `/v1/ocorrencias/{id}` | Revisão técnica com versionamento otimista (`HTTP 409` em conflito) |
| `GET` | `/v1/indicadores` | Obter e recalcular IDU-Pavimento e métricas por território |
| `POST` | `/v1/relatorios` | Gerar Relatório Executivo PDF com SHA-256 e conclusões determinísticas |
| `GET` | `/v1/relatorios/{id}/download` | Download do relatório PDF gerado |
| `GET` | `/v1/export/csv` | Exportar ocorrências em CSV estruturado |
| `GET` | `/v1/export/geojson` | Exportar ocorrências em GeoJSON WGS84 |

