# 📋 Pendências e Próximos Passos — UrbanVision-Analytics

> Documento de rastreabilidade do status técnico, validações automatizadas e pendências operacionais do **UrbanVision Analytics** (auditoria automática de infraestrutura urbana e severidade viária).

---

## ✅ 1. O que já está Concluído e Validado

- **API & Pipeline Core (`app/` — FastAPI + SQLAlchemy):**
  - Endpoints `/v1` completos para campanhas, lotes, upload de mídias com checagem óptica/EXIF/manifesto CSV e deduplicação SHA-256, execuções, união/separação manual de ocorrências, versionamento de parâmetros/modelos, intervenções, ordens de serviço e relatórios.
  - Deduplicação espaço-temporal DBSCAN (raio geodésico de 10 m via Haversine WGS84).
  - Cálculo determinístico do **IDU-Pavimento**, elegibilidade estatutária (`RN-07`: $C \ge 60\%$ e $L_{obs} \ge 1{,}0\text{ km}$) e extensões únicas em células de 50 m (`RN-05`).
- **Ingestão Territorial & Relatórios (`app/services/`):**
  - Integração OpenStreetMap (Overpass API) + GeoSampa (GeoJSON prefeitura) com base offline curada multi-capitais (SP, RJ, BH, Curitiba).
  - Emissão de relatórios executivos PDF (ReportLab) com carimbo SHA-256 e exportação CSV/GeoJSON.
- **Testes & Qualidade (`.github/workflows/ci.yml`):**
  - **20/20 testes** (`pytest -v`) validando critérios de aceite, fluxo API/concorrência, expansão P1 e integração territorial.
  - Linter **Ruff** configurado em `pyproject.toml` e validado com 0 erros.

---

## 🚀 2. Melhorias Futuras Opcionais (Backlog de Engenharia)
- [ ] **Migrations Formais (Alembic):** Substituir `Base.metadata.create_all` por controle versionado de schema via Alembic para ambientes PostgreSQL/PostGIS de produção.
- [ ] **Autenticação & RBAC na API:** Adicionar JWT/OAuth2 e controle de perfis (Inspetor, Auditor, Gestor Municipal) nas rotas administrativas e de revisão de ocorrências.
- [ ] **Fila Assíncrona de Vídeo/Lote:** Desacoplar extração de frames e inferência pesada em worker assíncrono (Celery/RQ + Redis) para lotes de milhares de imagens.

---

## 🛠️ 3. Dependências Externas (Ambiente de Produção)
- [ ] **Pesos YOLO Treinados (RDD2022 + P1 `M01`/`S01`):** Fornecer arquivo `.pt` em `weights_path` com `ultralytics` instalado em produção (na ausência de pesos externos, `DamageDetector` utiliza o baseline determinístico de demonstração).
- [ ] **Infraestrutura Docker / PostGIS 16 (`docker-compose.yml`):** Subir instância PostgreSQL 16 + PostGIS em homologação/produção configurando `DATABASE_URL` via `.env`.
- [ ] **Lotes Reais de Campo:** Submeter vídeos/imagens georreferenciadas de vistoria municipal real para auditar novos municípios além das 5 campanhas de demonstração.
