from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Campanhas ---
class CampanhaCreate(BaseModel):
    municipio: str
    periodo: str
    responsavel: str
    organizacao: Optional[str] = "Prefeitura Municipal"
    area_alvo_geojson: Optional[str] = None
    malha_versao: Optional[str] = "v1.0"
    protocolo: Optional[str] = "Padrao_Carro_Urbano_1080p"

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
    modelo_id: Optional[str] = None
    parametros: Optional[Dict[str, Any]] = None

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
    data_fim: Optional[datetime] = None

# --- Ocorrências ---
class RevisaoHistorico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    autor: str
    data_utc: datetime
    decisao: str
    classe_anterior: Optional[str] = None
    classe_nova: Optional[str] = None
    status_anterior: Optional[str] = None
    status_novo: Optional[str] = None
    motivo: str

class DeteccaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    classe: str
    confianca: float
    bbox: List[float]
    recorte_uri: Optional[str] = None
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
    deteccoes: List[DeteccaoItem] = []
    revisoes: List[RevisaoHistorico] = []

class OcorrenciaUpdate(BaseModel):
    versao_esperada: int = Field(..., description="Versão atual para detecção de concorrência otimista")
    revisor: str
    motivo: str
    classe: Optional[str] = None
    status: Optional[str] = None  # confirmada, rejeitada, resolvida
    latitude: Optional[float] = None
    longitude: Optional[float] = None

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
    motivo_inelegivel: Optional[str] = None
    versao_metodologia: str
    data_calculo: datetime

# --- Relatório ---
class RelatorioCreate(BaseModel):
    campanha_id: str
    autor: str
    s_ref: Optional[float] = 40.0

class RelatorioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campanha_id: str
    versao: str
    autor: str
    data_utc: datetime
    uri_pdf: str
    hash_pdf: str
    texto_conclusao: Optional[str] = None



# --- Unir e Separar Ocorrências (RF-09) ---
class OcorrenciasUnirRequest(BaseModel):
    ocorrencias_ids: List[str]
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
    dataset_referencia: Optional[str] = "RDD2022"
    metricas: Optional[Dict[str, Any]] = None
    status: Optional[str] = "avaliado"

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
    s_ref: Optional[float] = 40.0
    min_cobertura_pct: Optional[float] = 60.0
    min_l_obs_km: Optional[float] = 1.0
    raio_agrupamento_m: Optional[float] = 10.0
    pesos_classes: Optional[Dict[str, float]] = None
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
    data_inspecao: Optional[datetime] = None
    evidencia_foto_uri: Optional[str] = None

class IntervencaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ocorrencia_id: str
    tipo: str
    descricao: str
    autor: str
    data_inspecao: datetime
    evidencia_foto_uri: Optional[str] = None
    criado_em: datetime

# --- Integrações com Ordens de Serviço Municipais (RF-20) ---
class OrdemServicoCreate(BaseModel):
    numero_os: str
    orgao_responsavel: Optional[str] = "Secretaria de Obras e Infraestrutura Urbana"
    status_os: Optional[str] = "aberta"
    observacoes: Optional[str] = None

class OrdemServicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ocorrencia_id: str
    numero_os: str
    orgao_responsavel: str
    status_os: str
    data_abertura: datetime
    data_conclusao: Optional[datetime] = None
    observacoes: Optional[str] = None
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
    deteccoes: List[DeteccaoItem] = []
    revisoes: List[RevisaoHistorico] = []
    intervencoes: List[IntervencaoResponse] = []
    ordens_servico: List[OrdemServicoResponse] = []
