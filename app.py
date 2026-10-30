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
# RELATÓRIO DINÂMICO LINGUAGEM CLARA E AÇÕES PRÁTICAS
# =========================================================
st.markdown("---")
st.subheader("📋 Relatório de Decisão Prática do Portfólio")

with st.expander("🔍 Ver Situação e Ação Prática por ETF", expanded=True):
    for nome in etfs_selecionados:
        ticker = ETF_MAP[nome]
        if ticker in dados.columns:
            serie = dados[ticker].dropna()
            df_ind = calcular_indicadores(serie)
            
            preco = df_ind['Preco'].iloc[-1]
            ma50 = df_ind['MA50'].iloc[-1]
            ma200 = df_ind['MA200'].iloc[-1]
            rsi = df_ind['RSI'].iloc[-1]
            
            # Matriz de Decisão com Linguagem Clara
            if ma50 > ma200:
                if rsi > 70:
                    status_acao = "🟡 DESFAVORÁVEL À COMPRA (Preço Esticado)"
                    explicacao = f"A tendência geral é positiva, mas o preço subiu muito rápido (RSI: {rsi:.1f}). Aguarde uma pequena pausa antes de fazer novos aportes."
                elif rsi < 35:
                    status_acao = "🟢 VALORIZADO PARA COMPRA (Preço em Desconto)"
                    explicacao = f"A tendência de longo prazo é de alta e o preço sofreu um recuo pontual (RSI: {rsi:.1f}). Excelente momento técnico para aportar."
                else:
                    status_acao = "🟢 FAVORÁVEL À COMPRA / MANTER"
                    explicacao = f"Tendência de alta ativa e preço em ritmo equilibrado (RSI: {rsi:.1f}). Favorável para manter ou reforçar a posição."
            else:
                if rsi < 30:
                    status_acao = "🟡 DESFAVORÁVEL À VENDA (Sobrevendido)"
                    explicacao = f"O ativo está em tendência de baixa, mas o preço já caiu excessivamente (RSI: {rsi:.1f}). Vender agora pode significar sair no fundo."
                else:
                    status_acao = "🔴 FAVORÁVEL À VENDA / EVITAR"
                    explicacao = f"Tendência primária de baixa confirmada (MA50 abaixo da MA200). Evite novas compras até surgir um sinal claro de recuperação."
            
            # Exibição no Streamlit
            st.markdown(f"### 📌 {nome} (`{ticker}`)")
            st.write(f"- **Cotação Atual:** €{preco:.2f}")
            st.markdown(f"- **Ação Recomendada:** `{status_acao}`")
            st.write(f"- **Diagnóstico Direto:** {explicacao}")
            st.markdown("---")