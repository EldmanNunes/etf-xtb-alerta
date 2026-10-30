import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pandas as pd
import requests

# Configuração de Logging
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
    """Obtém o histórico de taxas de câmbio da API pública do Frankfurter."""
    domain_frankfurter = "api." + "frankfurter." + "dev"
    endpoint_fx = f'https://{domain_frankfurter}/v1/{inicio}..?from={base}&to={alvo}'
    
    try:
        r = requests.get(endpoint_fx, timeout=10)
        if r.status_code == 200:
            data = r.json().get('rates', {})
            df = pd.DataFrame([{'date': pd.to_datetime(d), 'rate': v[alvo]} for d, v in data.items()])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            return df
        else:
            logging.error("API Frankfurter respondeu com status %d", r.status_code)
    except Exception as e:
        logging.error("Erro na consulta da API Frankfurter: %s", str(e))
    return pd.DataFrame()

def analisar_sinal_cambial(df: pd.DataFrame) -> dict:
    """Calcula indicadores técnicos (MA20, Bollinger, Z-Score) e identifica oportunidades de compra."""
    if df.empty or len(df) < 20:
        logging.warning("Dados históricos insuficientes para calcular indicadores cambiais.")
        return {}

    rate_atual = float(df['rate'].iloc[-1])
    data_cotacao = df.index[-1].strftime("%d/%m/%Y")

    ma20 = float(df['rate'].tail(20).mean())
    std20 = float(df['rate'].tail(20).std())
    bollinger_inf = ma20 - (1.8 * std20)
    bollinger_sup = ma20 + (1.8 * std20)
    z_score = (rate_atual - ma20) / std20 if std20 > 0 else 0.0

    compra_efetiva = rate_atual * (1 + SPREAD_ESTIMADO / 100)

    # Condições de Alerta para COMPRA FAVORÁVEL:
    # 1. Z-Score <= -1.5 (Preço sobrevendido em relação à média de 20 dias)
    # 2. Cotação abaixo ou na Banda Inferior de Bollinger
    # 3. Cotação igual ou inferior à meta manual definida (se configurada)
    e_sobrevendido = z_score <= -1.5
    e_bollinger_baixa = rate_atual <= bollinger_inf
    e_meta_atingida = (META_COMPRA_MANUAL > 0.0) and (rate_atual <= META_COMPRA_MANUAL)

    tem_alerta = e_sobrevendido or e_bollinger_baixa or e_meta_atingida

    return {
        "data": data_cotacao,
        "rate_atual": rate_atual,
        "compra_efetiva": compra_efetiva,
        "ma20": ma20,
        "bollinger_inf": bollinger_inf,
        "bollinger_sup": bollinger_sup,
        "z_score": z_score,
        "tem_alerta": tem_alerta,
        "motivo": (
            "Meta manual de compra atingida" if e_meta_atingida else
            "Preço abaixo da Banda Inferior de Bollinger" if e_bollinger_baixa else
            "Z-Score fortemente sobrevendido" if e_sobrevendido else "Neutro"
        )
    }

def main():
    try:
        logging.info("Iniciando monitorização de alerta cambial (%s/%s)...", MOEDA_BASE, MOEDA_ALVO)
        df_cambio = buscar_dados_cambio(MOEDA_BASE, MOEDA_ALVO)
        info = analisar_sinal_cambial(df_cambio)

        if info and info.get("tem_alerta"):
            corpo = (
                f"💱 ALERTA DE OPORTUNIDADE CAMBIAL - {MOEDA_BASE}/{MOEDA_ALVO}\n"
                f"Data da Cotação: {info['data']}\n\n"
                f"📌 Diagnóstico: OPORTUNIDADE FAVORÁVEL DE COMPRA\n"
                f"• Motivo do Sinal: {info['motivo']}\n\n"
                f"📊 Cotações Atualizadas:\n"
                f"• Cotação Spot ({MOEDA_BASE}/{MOEDA_ALVO}): {MOEDA_ALVO} {info['rate_atual']:.4f}\n"
                f"• Estimativa de Compra com Spread (+{SPREAD_ESTIMADO}%): {MOEDA_ALVO} {info['compra_efetiva']:.4f}\n"
                f"• Z-Score Técnico: {info['z_score']:.2f} desvios padrão\n"
                f"• Banda Inferior de Bollinger (20d): {MOEDA_ALVO} {info['bollinger_inf']:.4f}\n"
                f"• Média Móvel (20d): {MOEDA_ALVO} {info['ma20']:.4f}\n\n"
                f"💡 Recomendação Tática (DCA):\n"
                f"• Lote 1 (30% do orçamento): Executar compra inicial de proteção à cotação atual.\n"
                f"• Lotes 2 e 3 (70% restante): Programar ordens limite em patamares inferiores.\n\n"
                f"---\n"
                f"Alerta automático gerado pelo script alerta_cambial_0830.py"
            )
            assunto = f"🟢 Alerta Cambial: Oportunidade de Compra {MOEDA_BASE}/{MOEDA_ALVO} ({info['rate_atual']:.4f})"
            enviar_email(assunto, corpo)
        else:
            logging.info("Mercado cambial neutro (%s/%s). Nenhum alerta de compra gerado hoje.", MOEDA_BASE, MOEDA_ALVO)

    except Exception as e:
        logging.error("Erro durante a execução do script de alerta cambial: %s", str(e))

if __name__ == "__main__":
    main()
