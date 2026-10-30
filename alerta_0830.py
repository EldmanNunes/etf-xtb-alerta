import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pandas as pd
import yfinance as yf

# Configuração de Logging para acompanhamento no GitHub Actions ou terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configurações via Variáveis de Ambiente
REMETENTE = os.getenv("GMAIL_USER", "eldman.nunes@gmail.com")
SENHA_APP = os.getenv("GMAIL_PASS")
DESTINATARIO = os.getenv("GMAIL_DESTINO", REMETENTE)

# Mapeamento dos ETFs (Nome Amigável: Ticker na Xetra)
ETF_MAP = {
    "PRAB - Amundi 0-1Y": "PRAB.DE",
    "XDEQ - World Quality": "XDEQ.DE",
    "IBCI - Inflation Linked": "IBCI.DE"
}

def enviar_email(assunto: str, corpo: str) -> None:
    """Envia e-mail formatado via SMTP Gmail usando TLS."""
    if not SENHA_APP:
        logging.error("Variável de ambiente GMAIL_PASS não configurada. E-mail não enviado.")
        return

    msg = MIMEText(corpo, 'plain', 'utf-8')
    msg['Subject'] = assunto
    msg['From'] = REMETENTE
    msg['To'] = DESTINATARIO

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
            server.starttls()
            server.login(REMETENTE, SENHA_APP)
            server.send_message(msg)
            logging.info("E-mail de alerta enviado com sucesso para %s", DESTINATARIO)
    except Exception as e:
        logging.error("Falha ao enviar e-mail via SMTP: %s", str(e))
        raise

def buscar_e_analisar_dados() -> list:
    """Baixa cotações, calcula médias móveis vetorizadas e identifica sinais."""
    tickers = list(ETF_MAP.values())
    logging.info("Buscando histórico para os tickers: %s", tickers)

    # period="2y" garante dados suficientes para calcular MA200 sem faltas por feriados
    df_raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False)

    # Trata estrutura do DataFrame do yfinance (níveis de coluna)
    if 'Close' in df_raw:
        df_close = df_raw['Close']
    else:
        df_close = df_raw

    # Se apenas um ticker for retornado como Series, converte para DataFrame
    if isinstance(df_close, pd.Series):
        df_close = df_close.to_frame()

    # Cálculo vetorizado das médias móveis de 50 e 200 dias
    df_ma50 = df_close.rolling(window=50).mean()
    df_ma200 = df_close.rolling(window=200).mean()

    alertas = []

    for nome, ticker in ETF_MAP.items():
        if ticker not in df_close.columns:
            logging.warning("Ticker %s não encontrado nos dados baixados.", ticker)
            continue

        # Limpa valores nulos do ticker específico
        serie_preco = df_close[ticker].dropna()
        serie_ma50 = df_ma50[ticker].dropna()
        serie_ma200 = df_ma200[ticker].dropna()

        # Garante que temos pelo menos 200 dias de histórico válido
        if len(serie_preco) < 200 or len(serie_ma50) < 2 or len(serie_ma200) < 2:
            logging.warning("Histórico insuficiente para calcular MA200 do ETF %s.", nome)
            continue

        # Valores de ontem (fechamento oficial) e anteontem para evitar repaint
        preco_ontem = serie_preco.iloc[-1]
        ma50_ontem = serie_ma50.iloc[-1]
        ma50_anteontem = serie_ma50.iloc[-2]
        ma200_ontem = serie_ma200.iloc[-1]
        ma200_anteontem = serie_ma200.iloc[-2]

        # Sinais de Cruzamento
        golden_cross = (ma50_anteontem <= ma200_anteontem) and (ma50_ontem > ma200_ontem)
        death_cross = (ma50_anteontem >= ma200_anteontem) and (ma50_ontem < ma200_ontem)

        if golden_cross:
            sinal = f"🟢 COMPRA (Golden Cross) - {nome}\n   Fecho: €{preco_ontem:.2f} | MA50: €{ma50_ontem:.2f} | MA200: €{ma200_ontem:.2f}"
            alertas.append(sinal)
            logging.info("Sinal de COMPRA gerado para %s", nome)
        elif death_cross:
            sinal = f"🔴 VENDA (Death Cross) - {nome}\n   Fecho: €{preco_ontem:.2f} | MA50: €{ma50_ontem:.2f} | MA200: €{ma200_ontem:.2f}"
            alertas.append(sinal)
            logging.info("Sinal de VENDA gerado para %s", nome)

    return alertas

def main():
    try:
        logging.info("Iniciando execução da análise técnica de ETFs...")
        alertas = buscar_e_analisar_dados()

        if alertas:
            data_str = datetime.now().strftime("%d/%m/%Y")
            corpo = (
                f"Relatório de Sinais XTB - 08:30 Lisboa ({data_str})\n"
                f"Baseado no fecho oficial Xetra do dia anterior.\n\n"
                + "\n\n".join(alertas)
                + "\n\n---"
                + "\nNota: Sinais baseados no cruzamento de Médias Móveis (MA50 e MA200)."
            )
            assunto = f"Alerta XTB 08:30 - {len(alertas)} sinal(is) identificado(s)"
            enviar_email(assunto, corpo)
        else:
            logging.info("Nenhum sinal de compra ou venda gerado hoje. E-mail omitido para evitar spam.")

    except Exception as e:
        logging.error("Erro durante a execução do script: %s", str(e))

if __name__ == "__main__":
    main()
