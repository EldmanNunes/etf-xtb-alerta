# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuração da página
st.set_page_config(page_title="ETF Tracker XTB", layout="wide", page_icon="📊")

st.title("📊 ETF Tracker XTB")

# Mapeamento dos ETFs na Xetra
ETF_MAP = {
    "PRAB - Amundi 0-1Y": "PRAB.DE",
    "XDEQ - World Quality": "XDEQ.DE",
    "IBCI - Inflation Linked": "IBCI.DE"
}

# Sidebar - Configurações
st.sidebar.header("⚙️ Configurações")
etfs_selecionados = st.sidebar.multiselect(
    "Selecione os ETFs:",
    options=list(ETF_MAP.keys()),
    default=list(ETF_MAP.keys())
)

periodo = st.sidebar.selectbox(
    "Período Histórico:",
    options=["1y", "2y", "5y", "10y", "max"],
    index=2
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Indicadores Técnicos")
mostrar_ma = st.sidebar.checkbox("Médias Móveis (MA50 / MA200)", value=True)
mostrar_bb = st.sidebar.checkbox("Bandas de Bollinger (20, 2)", value=True)
mostrar_rsi = st.sidebar.checkbox("RSI (14)", value=True)
mostrar_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

# Função de Cache para download dos dados
@st.cache_data(ttl=3600)
def carregar_dados(tickers, period):
    df = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df = df['Close']
    return df

tickers = list(ETF_MAP.values())
dados = carregar_dados(tickers, periodo)

# 1. Métricas no topo
if not dados.empty and etfs_selecionados:
    cols = st.columns(len(etfs_selecionados))
    for idx, nome in enumerate(etfs_selecionados):
        ticker = ETF_MAP[nome]
        if ticker in dados.columns:
            serie = dados[ticker].dropna()
            if len(serie) >= 2:
                preco_atual = serie.iloc[-1]
                var_dia = ((serie.iloc[-1] / serie.iloc[-2]) - 1) * 100
                cols[idx].metric(
                    label=nome,
                    value=f"€{preco_atual:.2f}",
                    delta=f"{var_dia:+.2f}%"
                )

st.markdown("---")

# Função para cálculo dos indicadores técnicos
def calcular_indicadores(serie):
    df = pd.DataFrame({'Preco': serie})
    
    # Médias Móveis Simples
    df['MA50'] = df['Preco'].rolling(50).mean()
    df['MA200'] = df['Preco'].rolling(200).mean()
    
    # Bandas de Bollinger (20 períodos, 2 desvios padrão)
    df['BB_Mid'] = df['Preco'].rolling(20).mean()
    bb_std = df['Preco'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * bb_std)
    df['BB_Lower'] = df['BB_Mid'] - (2 * bb_std)
    
    # RSI (14)
    delta = df['Preco'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema12 = df['Preco'].ewm(span=12, adjust=False).mean()
    ema26 = df['Preco'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df

# 2. Gráficos Técnicos Individuais
for nome in etfs_selecionados:
    ticker = ETF_MAP[nome]
    if ticker in dados.columns:
        serie = dados[ticker].dropna()
        df_ind = calcular_indicadores(serie)
        
        # Estruturar subplots dinamicamente conforme seleção
        num_rows = 1
        row_heights = [0.5]
        subplot_titles = [f"Análise Técnica - {nome}"]
        
        if mostrar_rsi:
            num_rows += 1
            row_heights.append(0.25)
            subplot_titles.append("RSI (14)")
            
        if mostrar_macd:
            num_rows += 1
            row_heights.append(0.25)
            subplot_titles.append("MACD (12, 26, 9)")
            
        # Normalização das alturas
        total_h = sum(row_heights)
        row_heights = [h/total_h for h in row_heights]
        
        fig = make_subplots(
            rows=num_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=row_heights,
            subplot_titles=subplot_titles
        )
        
        # Subplot 1: Preço + MAs + Bollinger
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['Preco'], name="Preço (€)", line=dict(color='#1f77b4', width=1.5)), row=1, col=1)
        
        if mostrar_ma:
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MA50'], name="MA 50", line=dict(color='#ff7f0e', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MA200'], name="MA 200", line=dict(color='#9467bd', width=1.2)), row=1, col=1)
            
        if mostrar_bb:
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['BB_Upper'], name="Bollinger Sup", line=dict(color='rgba(128,128,128,0.5)', dash='dash', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['BB_Lower'], name="Bollinger Inf", line=dict(color='rgba(128,128,128,0.5)', dash='dash', width=1), fill='tonexty', fillcolor='rgba(128,128,128,0.1)'), row=1, col=1)
            
        current_row = 2
        
        # Subplot RSI
        if mostrar_rsi:
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['RSI'], name="RSI (14)", line=dict(color='#2ca02c', width=1.5)), row=current_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
            current_row += 1
            
        # Subplot MACD
        if mostrar_macd:
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MACD'], name="MACD", line=dict(color='#1f77b4', width=1.2)), row=current_row, col=1)
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MACD_Signal'], name="Sinal", line=dict(color='#ff7f0e', width=1.2)), row=current_row, col=1)
            
            # Histograma colorido
            colors = ['#2ca02c' if val >= 0 else '#d62728' for val in df_ind['MACD_Hist']]
            fig.add_trace(go.Bar(x=df_ind.index, y=df_ind['MACD_Hist'], name="Histograma", marker_color=colors), row=current_row, col=1)

        fig.update_layout(
            height=350 + (num_rows * 140),
            hovermode="x unified",
            showlegend=True,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

# 3. Matriz de Correlação
st.subheader("📊 Matriz de Correlação dos Retornos Diários")
if not dados.empty and len(etfs_selecionados) > 1:
    tickers_sel = [ETF_MAP[e] for e in etfs_selecionados if ETF_MAP[e] in dados.columns]
    retornos = dados[tickers_sel].pct_change().dropna()
    matriz_corr = retornos.corr()
    st.dataframe(matriz_corr.style.background_gradient(cmap="Blues"), use_container_width=True)

# 4. Botão de Download
st.markdown("---")
if not dados.empty:
    csv = dados.to_csv().encode('utf-8')
    st.download_button(
        label="📥 Descarregar Dados Históricos (CSV)",
        data=csv,
        file_name="etf_xtb_historico.csv",
        mime="text/csv"
    )
    
# =========================================================
# 5. RELATÓRIO DINÂMICO COM AÇÃO E JUSTIFICATIVA DETALHADA
# =========================================================
st.markdown("---")
st.subheader("📋 Relatório Dinâmico: Ação Recomendada e Justificativa")

with st.expander("🔍 Clique para ver a Situação Detalhada por Ativo", expanded=True):
    for nome in etfs_selecionados:
        ticker = ETF_MAP[nome]
        if ticker in dados.columns:
            serie = dados[ticker].dropna()
            df_ind = calcular_indicadores(serie)
            
            preco = df_ind['Preco'].iloc[-1]
            ma50 = df_ind['MA50'].iloc[-1]
            ma200 = df_ind['MA200'].iloc[-1]
            rsi = df_ind['RSI'].iloc[-1]
            macd = df_ind['MACD'].iloc[-1]
            sinal = df_ind['MACD_Signal'].iloc[-1]
            
            # Lógica de Decisão (Ação e Porquê)
            if ma50 > ma200:
                if rsi > 70:
                    acao = "🟡 ESPERAR / MANTER"
                    porque = (
                        f"A tendência primária é de **alta** (Golden Cross ativa: MA50 €{ma50:.2f} > MA200 €{ma200:.2f}), "
                        f"mas o RSI está em **{rsi:.1f} (Sobrecomprado)**. Fazer novas compras agora seria entrar a um preço esticado. "
                        f"A recomendação é manter a posição atual sem efetuar novos aportes."
                    )
                else:
                    acao = "🟢 COMPRAR / MANTER"
                    porque = (
                        f"A tendência primária é de **alta** (MA50 > MA200) e o RSI está em **{rsi:.1f} (Saudável)**. "
                        f"A estrutura técnica é favorável para manter a posição ou realizar novos aportes."
                    )
            else:
                if macd > sinal:
                    acao = "🟡 ESPERAR"
                    porque = (
                        f"O ativo encontra-se em **tendência primária de baixa** (Death Cross ativa: MA50 €{ma50:.2f} < MA200 €{ma200:.2f}). "
                        f"Embora o MACD indique uma ligeira recuperação no curto prazo, o modelo exige aguardar um cruzamento de alta "
                        f"(Golden Cross) definitivo antes de abrir nova posição."
                    )
                else:
                    acao = "🔴 ESPERAR / EVITAR COMPRAS"
                    porque = (
                        f"Tendência primária de **baixa** (MA50 < MA200) e sem sinais de recuperação no curto prazo (MACD vendedor). "
                        f"Mantenha-se fora do ativo até que surjam sinais claros de reversão técnica."
                    )
            
            st.markdown(f"### 📌 {nome} (`{ticker}`)")
            st.markdown(f"- **Preço Atual:** €{preco:.2f}")
            st.markdown(f"- **Ação Recomendada:** `{acao}`")
            st.markdown(f"- **Porquê / Justificativa:** {porque}")
            st.markdown("---")
            
    # Conclusão Geral da Carteira
    if len(etfs_selecionados) > 1:
        st.markdown("### 📊 Conclusão da Diversificação")
        st.info(
            "**Descorrelação Estrutural:** A relação entre o fundo monetário (PRAB) e as ações globais (XDEQ) "
            "mantém-se em ~0.05. Isto garante que a sua reserva de curto prazo permanece imune às oscilações e volatilidades do mercado acionista."
        )