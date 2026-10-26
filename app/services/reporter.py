import io
import csv
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.config import REPORTS_DIR, settings

def generate_automated_conclusion(
    bairro_res: Dict[str, Any], 
    d_municipal: Optional[float], 
    class_distribution: Dict[str, int]
) -> str:
    """
    Gera texto determinístico de conclusão baseado exclusivamente em métricas verificadas (RF-16).
    Evita afirmações de causa ou custos de obras sem estudo de engenharia.
    """
    if not bairro_res.get("elegivel"):
        motivo = bairro_res.get("motivo_inelegivel", "dados insuficientes")
        return (
            f"Para o bairro {bairro_res.get('bairro_nome')}, não foi possível gerar conclusão automatizada "
            f"definitiva devido a: {motivo}. Recomenda-se campanha de coleta complementar."
        )

    bairro_nome = bairro_res["bairro_nome"]
    densidade = bairro_res["densidade"]
    cobertura = bairro_res["cobertura_pct"]
    n_conf = bairro_res["N_confirmadas"]

    razao_str = ""
    if d_municipal and d_municipal > 0:
        razao = round(densidade / d_municipal, 1)
        razao_str = f", contra {d_municipal:.1f} no conjunto de comparação municipal: razão de {razao}"
    
    top_classe_str = ""
    if class_distribution and n_conf > 0:
        top_cls = max(class_distribution.items(), key=lambda x: x[1])
        cls_nome = settings.TAXONOMY.get(top_cls[0], top_cls[0])
        top_classe_str = f" Entre {n_conf} ocorrências classificadas, {top_cls[1]} foram {cls_nome.lower()}."

    texto = (
        f"Na campanha de referência, o bairro {bairro_nome} apresentou {densidade:.1f} ocorrências confirmadas "
        f"por km inspecionado{razao_str}. A cobertura foi de {cobertura:.1f}% da malha elegível.{top_classe_str} "
        f"Recomenda-se inspeção técnica para definir intervenções."
    )
    return texto

def export_occurrences_csv(occurrences: List[Dict[str, Any]]) -> str:
    """Exporta lista de ocorrências em formato CSV estruturado (RF-18)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "campanha_id", "classe", "descricao_classe", "confianca", 
        "latitude", "longitude", "incerteza_m", "status", "bairro", "via"
    ])
    for occ in occurrences:
        cls_desc = settings.TAXONOMY.get(occ.get("classe", ""), "")
        writer.writerow([
            occ.get("id"),
            occ.get("campanha_id"),
            occ.get("classe"),
            cls_desc,
            occ.get("confianca"),
            occ.get("latitude"),
            occ.get("longitude"),
            occ.get("incerteza_metros"),
            occ.get("status"),
            occ.get("bairro_nome"),
            occ.get("via_nome")
        ])
    return output.getvalue()

def export_occurrences_geojson(occurrences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Exporta lista de ocorrências em padrão GeoJSON WGS84 FeatureCollection (RF-18)."""
    features = []
    for occ in occurrences:
        feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [occ.get("longitude"), occ.get("latitude")]
            },
            "properties": {
                "id": occ.get("id"),
                "campanha_id": occ.get("campanha_id"),
                "classe": occ.get("classe"),
                "descricao_classe": settings.TAXONOMY.get(occ.get("classe", ""), ""),
                "confianca": occ.get("confianca"),
                "incerteza_metros": occ.get("incerteza_metros"),
                "status": occ.get("status"),
                "bairro": occ.get("bairro_nome"),
                "via": occ.get("via_nome")
            }
        }
        features.append(feat)

    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }

def generate_executive_pdf(
    campanha: Dict[str, Any],
    indicadores: List[Dict[str, Any]],
    d_municipal: Optional[float],
    ocorrencias: List[Dict[str, Any]],
    conclusoes: List[str],
    autor: str
) -> Tuple[Path, str]:
    """
    Gera Relatório Executivo em PDF com ReportLab conforme RF-17.
    Retorna o caminho do arquivo e o hash SHA-256.
    """
    report_filename = f"Relatorio_UrbanVision_{campanha.get('id', 'cpg')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    file_path = REPORTS_DIR / report_filename

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        spaceAfter=14
    )
    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Italic'],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#64748B')
    )

    elements = []

    # Cabeçalho
    elements.append(Paragraph("URBANVISION ANALYTICS", title_style))
    elements.append(Paragraph("Relatório Executivo de Auditoria Viária e Degradação Urbana", subtitle_style))
    elements.append(Paragraph(
        f"<b>Município:</b> {campanha.get('municipio')} | "
        f"<b>Campanha:</b> {campanha.get('id')} | "
        f"<b>Período:</b> {campanha.get('periodo')} | "
        f"<b>Responsável Técnico:</b> {autor} | "
        f"<b>Emissão:</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}",
        body_style
    ))
    elements.append(Spacer(1, 12))

    # Seção 1: Indicadores e IDU
    elements.append(Paragraph("1. Indicadores do Índice de Degradação Urbana (IDU-Pavimento)", h2_style))
    
    table_data = [["Bairro", "L_obs (km)", "L_eleg (km)", "Cobertura", "Danos Conf.", "Densidade (/km)", "IDU Score", "Faixa"]]
    for ind in indicadores:
        table_data.append([
            ind.get("bairro_nome", ""),
            f"{ind.get('L_obs', 0.0):.2f}",
            f"{ind.get('L_eleg', 0.0):.2f}",
            f"{ind.get('cobertura_pct', 0.0):.1f}%",
            str(ind.get("N_confirmadas", 0)),
            f"{ind.get('densidade', 0.0):.1f}",
            f"{ind.get('idu_score', 0.0):.1f}",
            ind.get("faixa", "")
        ])

    table = Table(table_data, colWidths=[100, 55, 55, 60, 60, 75, 60, 65])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    # Seção 2: Conclusões Automatizadas
    elements.append(Paragraph("2. Conclusões Baseadas em Evidências Verificadas", h2_style))
    for c in conclusoes:
        elements.append(Paragraph(f"• {c}", body_style))
        elements.append(Spacer(1, 4))
    elements.append(Spacer(1, 8))

    # Seção 3: Ocorrências Prioritárias Auditáveis
    elements.append(Paragraph("3. Ocorrências Prioritárias e Amostra de Evidências", h2_style))
    occ_sample = ocorrencias[:10]
    occ_data = [["ID Ocorrência", "Classe RDD2022", "Confiança", "Coordenadas (Lat, Lon)", "Status", "Via / Bairro"]]
    for o in occ_sample:
        cls_nome = settings.TAXONOMY.get(o.get("classe", ""), o.get("classe", ""))
        occ_data.append([
            o.get("id", "")[:12],
            cls_nome,
            f"{o.get('confianca', 0.0):.2f}",
            f"{o.get('latitude', 0.0):.5f}, {o.get('longitude', 0.0):.5f}",
            o.get("status", ""),
            f"{o.get('via_nome', '')} ({o.get('bairro_nome', '')})"
        ])

    occ_table = Table(occ_data, colWidths=[70, 120, 50, 110, 65, 115])
    occ_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(occ_table)
    elements.append(Spacer(1, 14))

    # Limitações e Declaração de Conformidade (Princípio da Seção 01 e Seção 11)
    elements.append(Paragraph("4. Limitações Técnicas e Salvaguardas Éticas", h2_style))
    disclaimer = (
        "<b>Aviso de Responsabilidade e Limites do MVP:</b> O UrbanVision Analytics apoia a triagem técnica "
        "e a priorização de vistorias de campo. Não estima profundidade milimétrica de buracos, resistência "
        "estrutural de subleito, causa de falhas nem custos de engenharia apenas por fotografia. A classificação "
        "automática foi gerada por modelo de visão computacional treinado na taxonomia RDD2022. Qualquer ordem "
        "de serviço ou obra de pavimentação requer homologação in loco por engenheiro habilitado."
    )
    elements.append(Paragraph(disclaimer, disclaimer_style))

    doc.build(elements)

    # Gera SHA-256 do PDF gerado para integridade e auditoria (Seção 10)
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    pdf_hash = hasher.hexdigest()

    return file_path, pdf_hash
