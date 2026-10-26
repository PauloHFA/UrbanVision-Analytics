import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Text, Table
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

# Tabela de associação Ocorrência Única <-> Detecções Brutas
ocorrencia_deteccao = Table(
    "ocorrencia_deteccao",
    Base.metadata,
    Column("ocorrencia_id", String, ForeignKey("ocorrencias.id", ondelete="CASCADE"), primary_key=True),
    Column("deteccao_id", String, ForeignKey("deteccoes.id", ondelete="CASCADE"), primary_key=True),
)

class Campanha(Base):
    __tablename__ = "campanhas"

    id = Column(String, primary_key=True, default=lambda: generate_id("cpg"))
    organizacao = Column(String, default="Prefeitura Municipal")
    municipio = Column(String, nullable=False)
    periodo = Column(String, nullable=False)  # Ex: "2026-Q4" ou "Outubro/2026"
    area_alvo_geojson = Column(Text, nullable=True)
    status = Column(String, default="ativa")  # ativa, concluida, arquivada
    responsavel = Column(String, nullable=False)
    malha_versao = Column(String, default="v1.0")
    protocolo = Column(String, default="Padrao_Carro_Urbano_1080p")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lotes = relationship("Lote", back_populates="campanha", cascade="all, delete-orphan")
    ocorrencias = relationship("Ocorrencia", back_populates="campanha")
    indicadores = relationship("IndicadorIDU", back_populates="campanha")
    relatorios = relationship("Relatorio", back_populates="campanha")


class Lote(Base):
    __tablename__ = "lotes"

    id = Column(String, primary_key=True, default=lambda: generate_id("lot"))
    campanha_id = Column(String, ForeignKey("campanhas.id"), nullable=False)
    status = Column(String, default="recebido")  # recebido, validando, pronto, processando, concluido, parcial, falhou, cancelado
    total_imagens = Column(Integer, default=0)
    total_validas = Column(Integer, default=0)
    total_rejeitadas = Column(Integer, default=0)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campanha = relationship("Campanha", back_populates="lotes")
    midias = relationship("Midia", back_populates="lote", cascade="all, delete-orphan")
    execucoes = relationship("Execucao", back_populates="lote", cascade="all, delete-orphan")


class Midia(Base):
    __tablename__ = "midias"

    id = Column(String, primary_key=True, default=lambda: generate_id("med"))
    lote_id = Column(String, ForeignKey("lotes.id"), nullable=False)
    uri_privada = Column(String, nullable=False)
    hash_sha256 = Column(String, nullable=False, index=True)
    formato = Column(String, nullable=False)
    largura = Column(Integer, nullable=False)
    altura = Column(Integer, nullable=False)
    timestamp_utc = Column(DateTime, nullable=True)
    fuso_original = Column(String, default="UTC")
    latitude = Column(Float, nullable=True, index=True)
    longitude = Column(Float, nullable=True, index=True)
    altitude = Column(Float, nullable=True)
    precisao_gps = Column(Float, nullable=True)
    status_qualidade = Column(String, default="valida")  # valida, descarte_nitidez, descarte_exposicao, descarte_sem_gps
    motivo_descarte = Column(String, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lote = relationship("Lote", back_populates="midias")
    deteccoes = relationship("Deteccao", back_populates="midia")


class Modelo(Base):
    __tablename__ = "modelos"

    id = Column(String, primary_key=True, default=lambda: generate_id("mdl"))
    nome = Column(String, nullable=False)
    versao = Column(String, nullable=False)
    hash_pesos = Column(String, nullable=False)
    dataset_referencia = Column(String, default="RDD2022")
    metricas_json = Column(Text, default="{}")
    status = Column(String, default="ativo")  # experimental, avaliado, aprovado, ativo, descontinuado
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    execucoes = relationship("Execucao", back_populates="modelo")


class Execucao(Base):
    __tablename__ = "execucoes"

    id = Column(String, primary_key=True, default=lambda: generate_id("exe"))
    modelo_id = Column(String, ForeignKey("modelos.id"), nullable=False)
    lote_id = Column(String, ForeignKey("lotes.id"), nullable=False)
    status = Column(String, default="iniciada")  # iniciada, processando, concluida, falhou
    parametros_json = Column(Text, default="{}")
    versao_preprocessamento = Column(String, default="v1.0")
    progresso_pct = Column(Float, default=0.0)
    total_processado = Column(Integer, default=0)
    total_deteccoes = Column(Integer, default=0)
    erros_json = Column(Text, default="[]")
    data_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    data_fim = Column(DateTime, nullable=True)

    modelo = relationship("Modelo", back_populates="execucoes")
    lote = relationship("Lote", back_populates="execucoes")
    deteccoes = relationship("Deteccao", back_populates="execucao")


class Deteccao(Base):
    __tablename__ = "deteccoes"

    id = Column(String, primary_key=True, default=lambda: generate_id("det"))
    execucao_id = Column(String, ForeignKey("execucoes.id"), nullable=False)
    midia_id = Column(String, ForeignKey("midias.id"), nullable=False)
    classe = Column(String, nullable=False)  # D00, D10, D20, D40
    confianca = Column(Float, nullable=False)
    bbox_xmin = Column(Float, nullable=False)
    bbox_ymin = Column(Float, nullable=False)
    bbox_xmax = Column(Float, nullable=False)
    bbox_ymax = Column(Float, nullable=False)
    recorte_uri = Column(String, nullable=True)
    mascara_json = Column(Text, nullable=True)

    execucao = relationship("Execucao", back_populates="deteccoes")
    midia = relationship("Midia", back_populates="deteccoes")
    ocorrencias = relationship("Ocorrencia", secondary=ocorrencia_deteccao, back_populates="deteccoes")


class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id = Column(String, primary_key=True, default=lambda: generate_id("occ"))
    campanha_id = Column(String, ForeignKey("campanhas.id"), nullable=False)
    classe = Column(String, nullable=False)  # D00, D10, D20, D40
    confianca = Column(Float, default=1.0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    incerteza_metros = Column(Float, default=5.0)
    status = Column(String, default="candidata")  # candidata, em_revisao, confirmada, rejeitada, resolvida
    via_nome = Column(String, default="Via Não Atribuída")
    bairro_nome = Column(String, default="Bairro Não Atribuído")
    versao = Column(Integer, default=1)  # Controle de concorrência otimista (PATCH 409 em caso de conflito)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campanha = relationship("Campanha", back_populates="ocorrencias")
    deteccoes = relationship("Deteccao", secondary=ocorrencia_deteccao, back_populates="ocorrencias")
    revisoes = relationship("Revisao", back_populates="ocorrencia", cascade="all, delete-orphan")


class Revisao(Base):
    __tablename__ = "revisoes"

    id = Column(String, primary_key=True, default=lambda: generate_id("rev"))
    ocorrencia_id = Column(String, ForeignKey("ocorrencias.id"), nullable=False)
    autor = Column(String, nullable=False)
    data_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    decisao = Column(String, nullable=False)  # confirmada, rejeitada, corrigida, reclassificada
    classe_anterior = Column(String, nullable=True)
    classe_nova = Column(String, nullable=True)
    status_anterior = Column(String, nullable=True)
    status_novo = Column(String, nullable=True)
    motivo = Column(Text, nullable=False)

    ocorrencia = relationship("Ocorrencia", back_populates="revisoes")


class Bairro(Base):
    __tablename__ = "bairros"

    id = Column(String, primary_key=True, default=lambda: generate_id("brr"))
    municipio = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    geometria_geojson = Column(Text, nullable=False)
    malha_elegivel_km = Column(Float, default=0.0)


class ViaTrecho(Base):
    __tablename__ = "vias_trechos"

    id = Column(String, primary_key=True, default=lambda: generate_id("via"))
    bairro_nome = Column(String, nullable=False)
    nome_via = Column(String, nullable=False)
    geometria_geojson = Column(Text, nullable=False)
    extensao_km = Column(Float, default=0.1)
    elegivel = Column(Boolean, default=True)


class IndicadorIDU(Base):
    __tablename__ = "indicadores_idu"

    id = Column(String, primary_key=True, default=lambda: generate_id("idu"))
    campanha_id = Column(String, ForeignKey("campanhas.id"), nullable=False)
    bairro_nome = Column(String, nullable=False)
    janela = Column(String, nullable=False)
    L_obs = Column(Float, nullable=False)
    L_eleg = Column(Float, nullable=False)
    cobertura_pct = Column(Float, nullable=False)
    N_confirmadas = Column(Integer, nullable=False)
    densidade = Column(Float, nullable=False)
    carga = Column(Float, nullable=False)
    idu_score = Column(Float, nullable=False)
    s_ref = Column(Float, nullable=False)
    faixa = Column(String, nullable=False)  # baixa, moderada, alta, muito alta
    elegivel = Column(Boolean, default=True)
    motivo_inelegivel = Column(String, nullable=True)
    versao_metodologia = Column(String, default="1.0")
    data_calculo = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campanha = relationship("Campanha", back_populates="indicadores")


class Relatorio(Base):
    __tablename__ = "relatorios"

    id = Column(String, primary_key=True, default=lambda: generate_id("rel"))
    campanha_id = Column(String, ForeignKey("campanhas.id"), nullable=False)
    versao = Column(String, default="1.0")
    autor = Column(String, nullable=False)
    data_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    uri_pdf = Column(String, nullable=False)
    hash_pdf = Column(String, nullable=False)
    snapshot_filtros_json = Column(Text, default="{}")
    texto_conclusao = Column(Text, nullable=True)

    campanha = relationship("Campanha", back_populates="relatorios")

