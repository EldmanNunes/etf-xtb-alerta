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
REMETENTE = os.getenv("GMAIL_USER", "")
SENHA_APP = os.getenv("GMAIL_PASS", "")
DESTINATARIO = os.getenv("GMAIL_DESTINO", REMETENTE)

# Mapeamento dos ETFs (Nome Amigável: Ticker na Xetra)
ETF_MAP = {
    "PRAB - Amundi 0-1Y": "PRAB.DE",
    "XDEQ - World Quality": "XDEQ.DE",
    "IBCI - Inflation Linked": "IBCI.DE"
}

def enviar_email(assunto: str, corpo: str) -> None:
    """Envia e-mail formatado via SMTP Gmail usando TLS."""
    if not SENHA_APP or not REMETENTE:
        logging.error("Variáveis GMAIL_USER e/ou GMAIL_PASS não configuradas. E-mail não enviado.")
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
            logging.info("E-mail de alerta enviado com sucesso para %s", dest)
    except Exception as e:
        logging.error("Falha ao enviar e-mail via SMTP: %s", str(e))
        raise

def calcular_rsi(serie: pd.Series, window: int = 14) -> pd.Series:
    """Calcula o indicador RSI (Relative Strength Index)."""
    delta = serie.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def buscar_e_analisar_dados() -> tuple:
    """
    Baixa cotações, calcula médias móveis, RSI e Bollinger, 
    classificando a situação em 4 Estados Operacionais.
    """
    tickers = list(ETF_MAP.values())
    logging.info("Buscando histórico para os tickers: %s", tickers)

    df_raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False)

    if 'Close' in df_raw:
        df_close = df_raw['Close']
    else:
        df_close = df_raw

    if isinstance(df_close, pd.Series):
        df_close = df_close.to_frame()

    alertas_detalhados = []
    resumo_tabela = []
    tem_acao_relevante = False

    for nome, ticker in ETF_MAP.items():
        if ticker not in df_close.columns:
            logging.warning("Ticker %s não encontrado nos dados baixados.", ticker)
            continue

        serie = df_close[ticker].dropna()
        if len(serie) < 200:
            logging.warning("Histórico insuficiente para calcular indicadores do ETF %s.", nome)
            continue

        # Cálculo dos Indicadores Técnicos
        ma50_serie = serie.rolling(50).mean()
        ma200_serie = serie.rolling(200).mean()
        rsi_serie = calcular_rsi(serie, 14)

        bb_mid = serie.rolling(20).mean()
        bb_std = serie.rolling(20).std()
        bb_upper_serie = bb_mid + (2 * bb_std)
        bb_lower_serie = bb_mid - (2 * bb_std)

        # Valores mais recentes (fecho de ontem e anteontem)
        preco_atual = float(serie.iloc[-1])
        ma50_ontem = float(ma50_serie.iloc[-1])
        ma50_anteontem = float(ma50_serie.iloc[-2])
        ma200_ontem = float(ma200_serie.iloc[-1])
        ma200_anteontem = float(ma200_serie.iloc[-2])

        rsi_atual = float(rsi_serie.iloc[-1])
        bb_upper = float(bb_upper_serie.iloc[-1])
        bb_lower = float(bb_lower_serie.iloc[-1])

        diff_ma_pct = ((ma50_ontem / ma200_ontem) - 1) * 100 if ma200_ontem > 0 else 0.0

        # Verificação de Cruzamento Técnico
        golden_cross = (ma50_anteontem <= ma200_anteontem) and (ma50_ontem > ma200_ontem)
        death_cross = (ma50_anteontem >= ma200_anteontem) and (ma50_ontem < ma200_ontem)

        # Classificação nos 4 Estados Operacionais
        if ma50_ontem > ma200_ontem:
            if rsi_atual > 70:
                estado = "🟡 [AGUARDAR / NÃO REFORÇAR]"
                diagnostico = f"Tendência primária de alta (MA50 > MA200), mas o preço está sobrecomprado (RSI: {rsi_atual:.1f}). Aguarde recuo tático antes de novos aportes."
            elif rsi_atual < 35 or golden_cross:
                estado = "🟢 [COMPRAR / REFORÇAR]"
                motivo = "Golden Cross recém-confirmado" if golden_cross else f"Recuo pontual em tendência de alta (RSI: {rsi_atual:.1f})"
                diagnostico = f"Excelente oportunidade de aporte! Motivo: {motivo}."
                tem_acao_relevante = True
            else:
                estado = "🔵 [MANTER / NEUTRO]"
                diagnostico = f"Tendência de alta ativa e ritmo equilibrado (RSI: {rsi_atual:.1f}). Posição mantida sem necessidade de intervenção imediata."
        else:
            if rsi_atual < 30:
                estado = "🟡 [AGUARDAR / NÃO REFORÇAR]"
                diagnostico = f"Tendência de baixa (MA50 < MA200), contudo o ativo está fortemente sobrevendido (RSI: {rsi_atual:.1f}). Evite vendas no fundo."
            elif death_cross or rsi_atual >= 30:
                estado = "🔴 [REDUZIR / REBALANCEAR]"
                motivo = "Death Cross recém-confirmado" if death_cross else f"Tendência de baixa confirmada (MA50 < MA200, RSI: {rsi_atual:.1f})"
                diagnostico = f"Atenção necessária: {motivo}. Avalie reequilíbrio caso o ativo esteja sobreponderado."
                if death_cross:
                    tem_acao_relevante = True

        resumo_tabela.append({
            "nome": nome,
            "ticker": ticker,
            "preco": preco_atual,
            "ma50": ma50_ontem,
            "ma200": ma200_ontem,
            "diff_ma": diff_ma_pct,
            "rsi": rsi_atual,
            "bb_lower": bb_lower,
            "bb_upper": bb_upper,
            "estado": estado
        })

        alertas_detalhados.append(
            f"📌 {nome} (`{ticker}`)\n"
            f"• Estado Operacional: {estado}\n"
            f"• Preço Atual: €{preco_atual:.2f} | MA50: €{ma50_ontem:.2f} | MA200: €{ma200_ontem:.2f} (Diff: {diff_ma_pct:+.2f}%)\n"
            f"• RSI (14): {rsi_atual:.1f} | Banda Bollinger Inf/Sup: €{bb_lower:.2f} / €{bb_upper:.2f}\n"
            f"• Diagnóstico: {diagnostico}"
        )

    return alertas_detalhados, resumo_tabela, tem_acao_relevante

def main():
    try:
        logging.info("Iniciando monitorização diária de ETFs XTB (v3.0 - 4 Estados Operacionais)...")
        alertas, tabela, tem_acao = buscar_e_analisar_dados()

        if alertas:
            data_str = datetime.now().strftime("%d/%m/%Y")
            
            # Formatação do corpo do e-mail com Tabela Numérica e Diagnóstico
            corpo_tabela = "📊 QUADRO DE INDICADORES TÉCNICOS:\n"
            for item in tabela:
                corpo_tabela += (
                    f"- {item['nome']} ({item['ticker']}): Fecho €{item['preco']:.2f} | "
                    f"MA50 €{item['ma50']:.2f} | MA200 €{item['ma200']:.2f} ({item['diff_ma']:+.2f}%) | "
                    f"RSI {item['rsi']:.1f} | Estado: {item['estado']}\n"
                )

            corpo = (
                f"📋 RELATÓRIO DIÁRIO DE ANÁLISE DE ETFS XTB (v3.0)\n"
                f"Data da Análise: {data_str} (Fecho Oficial Bolsa Xetra)\n\n"
                f"{corpo_tabela}\n"
                f"--------------------------------------------------\n"
                f"🔍 DIAGNÓSTICO E ORIENTAÇÃO OPERACIONAL:\n\n"
                + "\n\n".join(alertas)
                + "\n\n--------------------------------------------------\n"
                f"Metadados: Fonte yfinance (Xetra EUR) | Versão do Algoritmo: v3.0\n"
                f"Legenda de Estados:\n"
                f"🟢 [COMPRAR / REFORÇAR] | 🔵 [MANTER / NEUTRO] | 🟡 [AGUARDAR / NÃO REFORÇAR] | 🔴 [REDUZIR / REBALANCEAR]"
            )

            if tem_acao:
                assunto = f"🟢 Alerta ETFs XTB ({data_str}): Oportunidade ou Sinal de Aporte Detectado"
                enviar_email(assunto, corpo)
                logging.info("E-mail de alerta enviado (sinal relevante detectado).")
            else:
                logging.info("Nenhum sinal crítico (COMPRAR/REDUZIR) ativado hoje. Estado atual mantido. E-mail omitido para evitar spam.")

    except Exception as e:
        logging.error("Erro durante a execução do script de alerta de ETFs: %s", str(e))

if __name__ == "__main__":
    main()
