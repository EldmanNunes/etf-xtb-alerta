import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import numpy as np
import pandas as pd
import requests

# Configuração de Logging para acompanhamento no GitHub Actions ou terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configurações via Variáveis de Ambiente
REMETENTE = os.getenv("GMAIL_USER", "")
SENHA_APP = os.getenv("GMAIL_PASS", "")
DESTINATARIO = os.getenv("GMAIL_DESTINO", REMETENTE)

# Parâmetros Cambiais (Configuráveis via Variáveis de Ambiente)
MOEDA_BASE = os.getenv("MOEDA_BASE", "EUR")
MOEDA_ALVO = os.getenv("MOEDA_ALVO", "BRL")
SPREAD_ESTIMADO = float(os.getenv("SPREAD_PCT", "1.5"))  # Spread bancário estimado (%)
META_COMPRA_MANUAL = float(os.getenv("META_COMPRA", "0.0"))  # Opcional: Meta fixa definida pelo utilizador
MONTANTE_SIMULACAO = float(os.getenv("MONTANTE_BASE", "1000.0"))  # Exemplo de capital para simulação no e-mail

def enviar_email(assunto: str, corpo: str) -> None:
    """Envia e-mail de alerta cambial via SMTP Gmail usando TLS."""
    if not SENHA_APP or not REMETENTE:
        logging.error("Variáveis GMAIL_USER e/ou GMAIL_PASS não configuradas. E-mail omitido.")
        return

    dest = DESTINATARIO if DESTINATARIO else REMETENTE
    msg = MIMEText(corpo, 'plain', 'utf-8')
    msg['Subject'] = assunto
    msg['From'] = REMETENTE
    msg['To'] = dest

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
            server.starttls()
            server.login(REMETENTE, SENHA_APP)
            server.send_message(msg)
            logging.info("E-mail de alerta cambial enviado com sucesso para %s", dest)
    except Exception as e:
        logging.error("Falha ao enviar e-mail via SMTP: %s", str(e))
        raise

def buscar_dados_cambio(base: str, alvo: str, inicio: str = "2024-01-01") -> pd.DataFrame:
    """Obtém o histórico de taxas de câmbio da API pública do Frankfurter sem avisos de depreciação."""
    domain_frankfurter = "api." + "frankfurter." + "dev"
    endpoint_fx = f'https://{domain_frankfurter}/v1/{inicio}..?from={base}&to={alvo}'
    
    try:
        r = requests.get(endpoint_fx, timeout=10)
        if r.status_code == 200:
            data = r.json().get('rates', {})
            df = pd.DataFrame([{'date': pd.to_datetime(d), 'rate': v[alvo]} for d, v in data.items()])
            df = df.set_index('date').sort_index()
            return df
        else:
            logging.error("API Frankfurter respondeu com status %d", r.status_code)
    except Exception as e:
        logging.error("Erro na consulta da API Frankfurter: %s", str(e))
    return pd.DataFrame()

def analisar_sinal_cambial(df: pd.DataFrame) -> dict:
    """Calcula indicadores técnicos (MA20, MA90, Bollinger, Z-Score, Volatilidade) e classifica em 4 Estados Operacionais."""
    if df.empty or len(df) < 20:
        logging.warning("Dados históricos insuficientes para calcular indicadores cambiais.")
        return {}

    rate_atual = float(df['rate'].iloc[-1])
    data_cotacao = df.index[-1].strftime("%d/%m/%Y")

    ma20 = float(df['rate'].tail(20).mean())
    ma90 = float(df['rate'].tail(90).mean()) if len(df) >= 90 else ma20
    std20 = float(df['rate'].tail(20).std())
    bollinger_inf = ma20 - (1.8 * std20)
    bollinger_sup = ma20 + (1.8 * std20)
    z_score = (rate_atual - ma20) / std20 if std20 > 0 else 0.0
    diff_ma20_pct = ((rate_atual - ma20) / ma20) * 100 if ma20 > 0 else 0.0

    retornos = df['rate'].pct_change().dropna()
    vol_anual = float(retornos.std() * np.sqrt(252) * 100) if len(retornos) > 0 else 0.0

    compra_efetiva = rate_atual * (1 + SPREAD_ESTIMADO / 100)
    venda_efetiva = rate_atual * (1 - SPREAD_ESTIMADO / 100)

    # Classificação em 4 Estados Operacionais para Câmbio (v3.3)
    if z_score <= -1.5 or rate_atual <= bollinger_inf:
        estado = "🟢 [COMPRA TÁTICA - SOBREVENDIDO]"
        explicacao = f"Preço estatisticamente sobrevendido (Z-Score: {z_score:.2f} std). Excelente janela para antecipar compras."
        tem_alerta = True
    elif z_score >= 1.8 or rate_atual >= bollinger_sup:
        estado = "🔴 [VENDA FAVORÁVEL / SOBRECOMPRADO]"
        explicacao = f"Cotação em topo relativo (Z-Score: {z_score:.2f} std). Momento ideal para conversão/venda de divisas."
        tem_alerta = True
    elif z_score >= 1.5:
        estado = "🟡 [AGUARDAR / PREÇO ESTICADO]"
        explicacao = f"Valorização acentuada de curto prazo (Z-Score: {z_score:.2f} std). Evite compras de impulso; aguarde recuo."
        tem_alerta = False
    else:
        estado = "🔵 [COMPRA FRACIONADA / NEUTRO]"
        explicacao = f"Cotação em níveis equilibrados (Z-Score: {z_score:.2f} std). Recomenda-se a estratégia DCA (30% lote inicial + 70% ordens limite)."
        tem_alerta = False

    # Verificação adicional de meta manual definida
    e_meta_atingida = (META_COMPRA_MANUAL > 0.0) and (rate_atual <= META_COMPRA_MANUAL)
    if e_meta_atingida:
        tem_alerta = True
        estado = "🟢 [COMPRA TÁTICA - META ATINGIDA]"

    # Cálculos da Simulação Financeira (Montante Absoluto)
    total_efetivo_compra = MONTANTE_SIMULACAO * compra_efetiva
    custo_spread = MONTANTE_SIMULACAO * (rate_atual * SPREAD_ESTIMADO / 100)
    lote1_base = MONTANTE_SIMULACAO * 0.30
    lote1_efetivo = lote1_base * compra_efetiva
    lotes23_base = MONTANTE_SIMULACAO * 0.70
    lotes23_efetivo = lotes23_base * compra_efetiva

    return {
        "data": data_cotacao,
        "rate_atual": rate_atual,
        "compra_efetiva": compra_efetiva,
        "venda_efetiva": venda_efetiva,
        "ma20": ma20,
        "ma90": ma90,
        "diff_ma20_pct": diff_ma20_pct,
        "bollinger_inf": bollinger_inf,
        "bollinger_sup": bollinger_sup,
        "z_score": z_score,
        "vol_anual": vol_anual,
        "estado": estado,
        "explicacao": explicacao,
        "tem_alerta": tem_alerta,
        "montante_base": MONTANTE_SIMULACAO,
        "total_efetivo_compra": total_efetivo_compra,
        "custo_spread": custo_spread,
        "lote1_base": lote1_base,
        "lote1_efetivo": lote1_efetivo,
        "lotes23_base": lotes23_base,
        "lotes23_efetivo": lotes23_efetivo
    }

def main():
    try:
        logging.info("Iniciando monitorização de alerta cambial (%s/%s - v3.3)...", MOEDA_BASE, MOEDA_ALVO)
        df_cambio = buscar_dados_cambio(MOEDA_BASE, MOEDA_ALVO)
        info = analisar_sinal_cambial(df_cambio)

        if info and info.get("tem_alerta"):
            corpo = (
                f"💱 RELATÓRIO DIÁRIO DE ANÁLISE CAMBIAL ({MOEDA_BASE}/{MOEDA_ALVO} - v3.3)\n"
                f"Data da Análise: {info['data']} (Fonte: API Frankfurter / ECB)\n\n"
                f"📊 QUADRO DE INDICADORES TÉCNICOS CAMBIAIS:\n"
                f"- Spot: {MOEDA_ALVO} {info['rate_atual']:.4f} | Compra Ef.: {MOEDA_ALVO} {info['compra_efetiva']:.4f} | Venda Ef.: {MOEDA_ALVO} {info['venda_efetiva']:.4f}\n"
                f"- MA20: {MOEDA_ALVO} {info['ma20']:.4f} | MA90: {MOEDA_ALVO} {info['ma90']:.4f} (Dif MA20: {info['diff_ma20_pct']:+.2f}%)\n"
                f"- Bollinger (Inf/Sup): {MOEDA_ALVO} {info['bollinger_inf']:.4f} / {MOEDA_ALVO} {info['bollinger_sup']:.4f}\n"
                f"- Z-Score: {info['z_score']:.2f} std | Volatilidade Anualizada: {info['vol_anual']:.1f}%\n"
                f"- Sinal Operacional: {info['estado']}\n\n"
                f"--------------------------------------------------\n"
                f"🔍 DIAGNÓSTICO E ORIENTAÇÃO OPERACIONAL:\n"
                f"• Estado: {info['estado']}\n"
                f"• Diagnóstico: {info['explicacao']}\n\n"
                f"💼 SIMULAÇÃO FINANCEIRA DE APORTE ({MOEDA_BASE} {info['montante_base']:,.2f}):\n"
                f"• Total Efetivo a Receber/Pagar (+{SPREAD_ESTIMADO}% spread): {MOEDA_ALVO} {info['total_efetivo_compra']:,.2f}\n"
                f"• Custo Absoluto do Spread Bancário: {MOEDA_ALVO} {info['custo_spread']:,.2f}\n"
                f"• Lote 1 (30% Proteção Imediata): {MOEDA_BASE} {info['lote1_base']:,.2f} -> {MOEDA_ALVO} {info['lote1_efetivo']:,.2f} à taxa {info['compra_efetiva']:.4f}\n"
                f"• Lotes 2 e 3 (70% Ordens Limite em Recuos): {MOEDA_BASE} {info['lotes23_base']:,.2f} -> {MOEDA_ALVO} {info['lotes23_efetivo']:,.2f}\n\n"
                f"--------------------------------------------------\n"
                f"Metadados de Auditoria & Rastreabilidade (v3.3 - Cambial) | API Frankfurter (ECB)\n"
                f"Legenda de Estados:\n"
                f"🟢 [COMPRA TÁTICA - SOBREVENDIDO] | 🔵 [COMPRA FRACIONADA / NEUTRO] | 🟡 [AGUARDAR / PREÇO ESTICADO] | 🔴 [VENDA FAVORÁVEL / SOBRECOMPRADO]"
            )
            assunto = f"🟢 Alerta Cambial ({info['data']}): {info['estado']} - {MOEDA_BASE}/{MOEDA_ALVO} ({info['rate_atual']:.4f})"
            enviar_email(assunto, corpo)
            logging.info("E-mail de alerta cambial v3.3 enviado com sucesso.")
        else:
            logging.info("Mercado cambial neutro/aguardar (%s/%s - Z-Score: %.2f). Nenhum alerta crítico gerado hoje.", MOEDA_BASE, MOEDA_ALVO, info.get("z_score", 0.0))

    except Exception as e:
        logging.error("Erro durante a execução do script de alerta cambial: %s", str(e))

if __name__ == "__main__":
    main()
