import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pandas as pd
import yfinance as yf

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configurações via Variáveis de Ambiente
REMETENTE = os.getenv("GMAIL_USER", "eldman.nunes@gmail.com")
SENHA_APP = os.getenv("GMAIL_PASS")
DESTINATARIO = os.getenv("GMAIL_DESTINO", REMETENTE)

# Mapeamento dos ETFs (Nome Amigável: Ticker na Xetra)
ETF_MAP = {
    "XDEQ - World Quality": "XDEQ.DE",
    "PRAB - Amundi 0-1Y": "PRAB.DE",
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

def calcular_rsi(serie_preco: pd.Series, periodo: int = 14) -> pd.Series:
    """Calcula o RSI (Relative Strength Index) de 14 períodos."""
    delta = serie_preco.diff()
    gain = delta.where(delta > 0, 0).rolling(periodo).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(periodo).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def buscar_e_analisar_dados() -> list:
    """Baixa cotações, calcula MA50, MA200 e RSI14 e gera blocos de texto formatados para o e-mail."""
    tickers = list(ETF_MAP.values())
    logging.info("Buscando histórico para os tickers: %s", tickers)

    df_raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False)

    if 'Close' in df_raw:
        df_close = df_raw['Close']
    else:
        df_close = df_raw

    if isinstance(df_close, pd.Series):
        df_close = df_close.to_frame()

    df_ma50 = df_close.rolling(window=50).mean()
    df_ma200 = df_close.rolling(window=200).mean()

    alertas = []

    for nome, ticker in ETF_MAP.items():
        if ticker not in df_close.columns:
            logging.warning("Ticker %s não encontrado nos dados baixados.", ticker)
            continue

        serie_preco = df_close[ticker].dropna()
        serie_ma50 = df_ma50[ticker].dropna()
        serie_ma200 = df_ma200[ticker].dropna()
        serie_rsi = calcular_rsi(serie_preco)

        if len(serie_preco) < 200:
            logging.warning("Histórico insuficiente para %s.", nome)
            continue

        preco_ontem = serie_preco.iloc[-1]
        ma50_ontem = serie_ma50.iloc[-1]
        ma50_anteontem = serie_ma50.iloc[-2]
        ma200_ontem = serie_ma200.iloc[-1]
        ma200_anteontem = serie_ma200.iloc[-2]
        rsi_ontem = serie_rsi.iloc[-1]

        # Verifica cruzamentos de médias
        golden_cross = (ma50_anteontem <= ma200_anteontem) and (ma50_ontem > ma200_ontem)
        death_cross = (ma50_anteontem >= ma200_anteontem) and (ma50_ontem < ma200_ontem)

        if golden_cross or death_cross:
            # Classificação amigável do RSI
            if rsi_ontem > 70:
                rsi_label = f"{rsi_ontem:.1f} (Sobrecomprado)"
            elif rsi_ontem < 30:
                rsi_label = f"{rsi_ontem:.1f} (Preço com Desconto / Sobrevendido)"
            else:
                rsi_label = f"{rsi_ontem:.1f} (Zona Neutra / Preço Saudável)"

            # Definição da Ação e Motivo
            if golden_cross:
                if rsi_ontem > 70:
                    acao = "🟡 DESFAVORÁVEL À COMPRA (Preço Esticado)"
                    motivo = f"Ocorreu cruzamento de alta (Golden Cross), mas o preço subiu muito rápido (RSI {rsi_ontem:.1f}). Aguarde uma pausa antes de novos aportes."
                else:
                    acao = "🟢 FAVORÁVEL À COMPRA"
                    motivo = f"Novo cruzamento de alta (Golden Cross) confirmado com RSI saudável ({rsi_ontem:.1f}). Bom momento técnico para compra."
            else: # death_cross
                if rsi_ontem < 30:
                    acao = "🟡 DESFAVORÁVEL À VENDA (Sobrevendido)"
                    motivo = f"Ocorreu cruzamento de baixa (Death Cross), porém o ativo já caiu excessivamente (RSI {rsi_ontem:.1f}). Vender agora pode significar sair no fundo."
                else:
                    acao = "🔴 FAVORÁVEL À VENDA"
                    motivo = f"Cruzamento de baixa (Death Cross) confirmado. Evite novas compras e considere rebalancear a posição."

            bloco = (
                f"📌 {nome} (`{ticker}`)\n"
                f"• Cotação de Fecho: €{preco_ontem:.2f}\n"
                f"• Ação Recomendada: {acao}\n"
                f"• Velocímetro (RSI 14): {rsi_label}\n"
                f"• Motivo: {motivo}"
            )
            alertas.append(bloco)
            logging.info("Sinal gerado para %s: %s", nome, acao)

    return alertas

def main():
    try:
        logging.info("Iniciando execução do script de alertas...")
        alertas = buscar_e_analisar_dados()

        if alertas:
            data_str = datetime.now().strftime("%d/%m/%Y")
            corpo = (
                f"🗓️ 08:30 Lisboa | {data_str}\n"
                f"📈 Preços do fecho de ontem na Bolsa Xetra\n\n"
                f"----------------------------------------\n\n"
                + "\n\n----------------------------------------\n\n".join(alertas)
                + "\n\n----------------------------------------\n"
                + "💡 Acesse o seu painel de gráficos e análises completo em: https://etf-xtb-alerta.streamlit.app"
            )
            assunto = f"Alerta XTB 08:30 - {len(alertas)} Sinal(is) Detetado(s)"
            enviar_email(assunto, corpo)
        else:
            logging.info("Nenhum sinal de compra ou venda gerado hoje. E-mail omitido para evitar spam.")

    except Exception as e:
        logging.error("Erro durante a execução do script: %s", str(e))

if __name__ == "__main__":
    main()