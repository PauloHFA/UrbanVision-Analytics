from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Campanhas ---
class CampanhaCreate(BaseModel):
    municipio: str
    periodo: str
    responsavel: str
    organizacao: str | None = "Prefeitura Municipal"
    area_alvo_geojson: str | None = None
    malha_versao: str | None = "v1.0"
    protocolo: str | None = "Padrao_Carro_Urbano_1080p"

class CampanhaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    municipio: str
    periodo: str
    responsavel: str
    organizacao: str
    status: str
    malha_versao: str
    protocolo: str
    criado_em: datetime

# --- Lotes ---
class LoteCreate(BaseModel):
    campanha_id: str

class LoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campanha_id: str
    status: str
    total_imagens: int
    total_validas: int
    total_rejeitadas: int
    criado_em: datetime

# --- Execuções ---
class ExecucaoCreate(BaseModel):
    modelo_id: str | None = None
    parametros: dict[str, Any] | None = None

class ExecucaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    modelo_id: str
    lote_id: str
    status: str
    progresso_pct: float
    total_processado: int
    total_deteccoes: int
    data_inicio: datetime
    data_fim: datetime | None = None

# --- Ocorrências ---
class RevisaoHistorico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    autor: str
    data_utc: datetime
    decisao: str
    classe_anterior: str | None = None
    classe_nova: str | None = None
    status_anterior: str | None = None
    status_novo: str | None = None
    motivo: str

class DeteccaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    classe: str
    confianca: float
    bbox: list[float]
    recorte_uri: str | None = None
    midia_id: str

class OcorrenciaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campanha_id: str
    classe: str
    confianca: float
    latitude: float
    longitude: float
    incerteza_metros: float
    status: str
    via_nome: str
    bairro_nome: str
    versao: int
    criado_em: datetime
    atualizado_em: datetime
    deteccoes: list[DeteccaoItem] = []
    revisoes: list[RevisaoHistorico] = []

class OcorrenciaUpdate(BaseModel):
    versao_esperada: int = Field(..., description="Versão atual para detecção de concorrência otimista")
    revisor: str
    motivo: str
    classe: str | None = None
    status: str | None = None  # confirmada, rejeitada, resolvida
    latitude: float | None = None
    longitude: float | None = None

# --- Indicadores IDU ---
class IndicadorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campanha_id: str
    bairro_nome: str
    janela: str
    L_obs: float
    L_eleg: float
    cobertura_pct: float
    N_confirmadas: int
    densidade: float
    carga: float
    idu_score: float
    s_ref: float
    faixa: str
    elegivel: bool
    motivo_inelegivel: str | None = None
    versao_metodologia: str
    data_calculo: datetime

# --- Relatório ---
class RelatorioCreate(BaseModel):
    campanha_id: str
    autor: str
    s_ref: float | None = 40.0

class RelatorioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campanha_id: str
    versao: str
    autor: str
    data_utc: datetime
    uri_pdf: str
    hash_pdf: str
    texto_conclusao: str | None = None



# --- Unir e Separar Ocorrências (RF-09) ---
class OcorrenciasUnirRequest(BaseModel):
    ocorrencias_ids: list[str]
    revisor: str
    motivo: str

class OcorrenciaSepararRequest(BaseModel):
    revisor: str
    motivo: str

# --- Modelos de IA ---
class ModeloCreate(BaseModel):
    nome: str
    versao: str
    hash_pesos: str
    dataset_referencia: str | None = "RDD2022"
    metricas: dict[str, Any] | None = None
    status: str | None = "avaliado"

class ModeloResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    versao: str
    hash_pesos: str
    dataset_referencia: str
    metricas_json: str
    status: str
    criado_em: datetime

# --- Administração de Parâmetros (RF-19) ---
class ParametrosCreate(BaseModel):
    versao: str
    s_ref: float | None = 40.0
    min_cobertura_pct: float | None = 60.0
    min_l_obs_km: float | None = 1.0
    raio_agrupamento_m: float | None = 10.0
    pesos_classes: dict[str, float] | None = None
    autor: str
    justificativa: str

class ParametrosResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    versao: str
    s_ref: float
    min_cobertura_pct: float
    min_l_obs_km: float
    raio_agrupamento_m: float
    pesos_classes_json: str
    ativo: bool
    autor: str
    justificativa: str
    criado_em: datetime


# --- Histórico de Intervenções e Re-inspeções (RF-14) ---
class IntervencaoCreate(BaseModel):
    tipo: str = Field(..., description="dano_persistente, reparo_confirmado ou ausencia_observacao")
    descricao: str
    autor: str
    data_inspecao: datetime | None = None
    evidencia_foto_uri: str | None = None

class IntervencaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ocorrencia_id: str
    tipo: str
    descricao: str
    autor: str
    data_inspecao: datetime
    evidencia_foto_uri: str | None = None
    criado_em: datetime

# --- Integrações com Ordens de Serviço Municipais (RF-20) ---
class OrdemServicoCreate(BaseModel):
    numero_os: str
    orgao_responsavel: str | None = "Secretaria de Obras e Infraestrutura Urbana"
    status_os: str | None = "aberta"
    observacoes: str | None = None

class OrdemServicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ocorrencia_id: str
    numero_os: str
    orgao_responsavel: str
    status_os: str
    data_abertura: datetime
    data_conclusao: datetime | None = None
    observacoes: str | None = None
    criado_em: datetime

# --- Linha do Tempo e Histórico Completo da Ocorrência (RF-14) ---
class HistoricoOcorrenciaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ocorrencia_id: str
    classe: str
    status: str
    latitude: float
    longitude: float
    via_nome: str
    bairro_nome: str
    deteccoes: list[DeteccaoItem] = []
    revisoes: list[RevisaoHistorico] = []
    intervencoes: list[IntervencaoResponse] = []
    ordens_servico: list[OrdemServicoResponse] = []

# --- Gestão Territorial e Integrações Abertas (OSM / GeoSampa) ---
class BairroCreate(BaseModel):
    municipio: str = "São Paulo"
    nome: str
    geometria_geojson: str
    malha_elegivel_km: float | None = 0.0

class BairroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    municipio: str
    nome: str
    geometria_geojson: str
    malha_elegivel_km: float

class ViaCreate(BaseModel):
    bairro_nome: str
    nome_via: str
    geometria_geojson: str
    extensao_km: float | None = 0.1
    elegivel: bool | None = True

class ViaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bairro_nome: str
    nome_via: str
    geometria_geojson: str
    extensao_km: float
    elegivel: bool

class ImportacaoTerritorioOSMRequest(BaseModel):
    municipio: str = "São Paulo"
    bairro_nome: str
    incluir_vias: bool | None = True
    tipos_vias: list[str] | None = ["primary", "secondary", "tertiary", "residential"]
    overpass_url: str | None = "https://overpass-api.de/api/interpreter"

class ImportacaoGeoSampaRequest(BaseModel):
    municipio: str = "São Paulo"
    bairro_feature: dict[str, Any]
    vias_features: list[dict[str, Any]] | None = None

class ImportacaoTerritorioResponse(BaseModel):
    bairro_id: str
    nome: str
    municipio: str
    malha_elegivel_km: float
    total_vias_importadas: int
    fonte_origem: str
    mensagem: str
