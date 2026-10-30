import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuração da página
st.set_page_config(page_title="ETF Tracker & Rebalancer XTB", layout="wide", page_icon="📊")

st.title("📊 ETF Tracker & Rebalancer XTB")

# Mapeamento e Alvos Estratégicos
ETF_MAP = {
    "PRAB - Amundi 0-1Y": {"ticker": "PRAB.DE", "target_pct": 0.25, "nome": "Amundi 0-1Y"},
    "XDEQ - World Quality": {"ticker": "XDEQ.DE", "target_pct": 0.30, "nome": "World Quality"},
    "IBCI - Inflation Linked": {"ticker": "IBCI.DE", "target_pct": 0.45, "nome": "Inflation Linked"}
}

TICKER_TO_KEY = {meta["ticker"]: key for key, meta in ETF_MAP.items()}

# Sidebar - Configurações Gerais
st.sidebar.header("⚙️ Configurações")
periodo = st.sidebar.selectbox(
    "Período Histórico (Gráficos):",
    options=["1y", "2y", "5y", "10y", "max"],
    index=2
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Indicadores Técnicos")
mostrar_ma = st.sidebar.checkbox("Médias Móveis (MA50 / MA200)", value=True)
mostrar_bb = st.sidebar.checkbox("Bandas de Bollinger (20, 2)", value=True)
mostrar_rsi = st.sidebar.checkbox("RSI (14)", value=True)
mostrar_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

# Cache de Download de Dados
@st.cache_data(ttl=3600)
def carregar_dados(tickers_list, period):
    df = yf.download(tickers_list, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df = df['Close']
    return df

tickers = [meta["ticker"] for meta in ETF_MAP.values()]
dados = carregar_dados(tickers, periodo)

# Função para cálculo dos indicadores
def calcular_indicadores(serie):
    df = pd.DataFrame({'Preco': serie})
    df['MA50'] = df['Preco'].rolling(50).mean()
    df['MA200'] = df['Preco'].rolling(200).mean()
    
    df['BB_Mid'] = df['Preco'].rolling(20).mean()
    bb_std = df['Preco'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * bb_std)
    df['BB_Lower'] = df['BB_Mid'] - (2 * bb_std)
    
    delta = df['Preco'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    ema12 = df['Preco'].ewm(span=12, adjust=False).mean()
    ema26 = df['Preco'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df

# SEPARADORES PRINCIPAIS
tab1, tab2 = st.tabs(["📈 Análise Técnica & Diagnóstico", "⚖️ Calculadora de Rebalanceamento"])

# =========================================================
# TAB 1: ANÁLISE TÉCNICA E INDICADORES
# =========================================================
with tab1:
    etfs_selecionados = list(ETF_MAP.keys())
    
    # 1. Métricas no topo
    if not dados.empty:
        cols = st.columns(len(etfs_selecionados))
        for idx, nome in enumerate(etfs_selecionados):
            ticker = ETF_MAP[nome]["ticker"]
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

    # 2. Relatório Dinâmico
    st.subheader("📋 Relatório Dinâmico: Decisão Prática do Portfólio")
    with st.expander("🔍 Ver Situação e Ação Prática por ETF", expanded=True):
        for nome in etfs_selecionados:
            ticker = ETF_MAP[nome]["ticker"]
            if ticker in dados.columns:
                serie = dados[ticker].dropna()
                df_ind = calcular_indicadores(serie)
                
                preco = df_ind['Preco'].iloc[-1]
                ma50 = df_ind['MA50'].iloc[-1]
                ma200 = df_ind['MA200'].iloc[-1]
                rsi = df_ind['RSI'].iloc[-1]
                
                if ma50 > ma200:
                    if rsi > 70:
                        status_acao = "🟡 DESFAVORÁVEL À COMPRA (Preço Esticado)"
                        explicacao = f"A tendência geral é positiva, mas o preço subiu muito rápido (RSI: {rsi:.1f}). Aguarde uma pausa antes de novos aportes."
                    elif rsi < 35:
                        status_acao = "🟢 VALORIZADO PARA COMPRA (Preço em Desconto)"
                        explicacao = f"A tendência de longo prazo é de alta e o preço sofreu um recuo pontual (RSI: {rsi:.1f}). Excelente momento para aportar."
                    else:
                        status_acao = "🟢 FAVORÁVEL À COMPRA / MANTER"
                        explicacao = f"Tendência de alta ativa e preço em ritmo equilibrado (RSI: {rsi:.1f}). Favorável para manter ou reforçar."
                else:
                    if rsi < 30:
                        status_acao = "🟡 DESFAVORÁVEL À VENDA (Sobrevendido)"
                        explicacao = f"O ativo está em tendência de baixa, mas o preço já caiu excessivamente (RSI: {rsi:.1f}). Vender agora pode significar sair no fundo."
                    else:
                        status_acao = "🔴 FAVORÁVEL À VENDA / EVITAR"
                        explicacao = f"Tendência primária de baixa confirmada (MA50 < MA200). Evite novas compras até sinal de recuperação."
                
                st.markdown(f"### 📌 {nome} (`{ticker}`)")
                st.write(f"- **Cotação Atual:** €{preco:.2f}")
                st.markdown(f"- **Ação Recomendada:** `{status_acao}`")
                st.write(f"- **Diagnóstico Direto:** {explicacao}")
                st.markdown("---")

    # 3. Gráficos Técnicos
    st.subheader("📈 Gráficos Técnicos Individuais")
    for nome in etfs_selecionados:
        ticker = ETF_MAP[nome]["ticker"]
        if ticker in dados.columns:
            serie = dados[ticker].dropna()
            df_ind = calcular_indicadores(serie)
            
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
                
            total_h = sum(row_heights)
            row_heights = [h/total_h for h in row_heights]
            
            fig = make_subplots(
                rows=num_rows, cols=1, shared_xaxes=True,
                vertical_spacing=0.06, row_heights=row_heights,
                subplot_titles=subplot_titles
            )
            
            fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['Preco'], name="Preço (€)", line=dict(color='#1f77b4', width=1.5)), row=1, col=1)
            
            if mostrar_ma:
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MA50'], name="MA 50", line=dict(color='#ff7f0e', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MA200'], name="MA 200", line=dict(color='#9467bd', width=1.2)), row=1, col=1)
                
            if mostrar_bb:
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['BB_Upper'], name="Bollinger Sup", line=dict(color='rgba(128,128,128,0.5)', dash='dash', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['BB_Lower'], name="Bollinger Inf", line=dict(color='rgba(128,128,128,0.5)', dash='dash', width=1), fill='tonexty', fillcolor='rgba(128,128,128,0.1)'), row=1, col=1)
                
            current_row = 2
            if mostrar_rsi:
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['RSI'], name="RSI (14)", line=dict(color='#2ca02c', width=1.5)), row=current_row, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
                current_row += 1
                
            if mostrar_macd:
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MACD'], name="MACD", line=dict(color='#1f77b4', width=1.2)), row=current_row, col=1)
                fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind['MACD_Signal'], name="Sinal", line=dict(color='#ff7f0e', width=1.2)), row=current_row, col=1)
                colors = ['#2ca02c' if val >= 0 else '#d62728' for val in df_ind['MACD_Hist']]
                fig.add_trace(go.Bar(x=df_ind.index, y=df_ind['MACD_Hist'], name="Histograma", marker_color=colors), row=current_row, col=1)

            fig.update_layout(height=350 + (num_rows * 140), hovermode="x unified", showlegend=True, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # 4. Matriz de Correlação
    st.subheader("📊 Matriz de Correlação dos Retornos Diários")
    if not dados.empty:
        retornos = dados.pct_change().dropna()
        matriz_corr = retornos.corr()
        st.dataframe(matriz_corr.style.background_gradient(cmap="Blues"), use_container_width=True)

# =========================================================
# TAB 2: CALCULADORA DE REBALANCEAMENTO
# =========================================================
with tab2:
    st.subheader("⚖️ Calculadora de Rebalanceamento XTB por Novo Aporte")
    st.caption("Alocação Alvo Estratégica: PRAB (25%) | IBCI (45%) | XDEQ (30%)")
    
    capital = st.number_input("Capital disponível para investir (€)", min_value=0.0, value=4000.0, step=100.0, key="cap_rebalancer")
    
    st.markdown("### 📝 Posição Atual")
    c_cols = st.columns(3)
    
    cotas_input = {}
    precos_input = {}
    
    # Valores Padrão do Seu Portfólio
    padroes = {
        "PRAB": {"cotas": 654, "ticker": "PRAB.DE"},
        "IBCI": {"cotas": 110, "ticker": "IBCI.DE"},
        "XDEQ": {"cotas": 208, "ticker": "XDEQ.DE"}
    }
    
    for idx, (sigla, p_data) in enumerate(padroes.items()):
        ticker = p_data["ticker"]
        preco_live = 20.0
        if not dados.empty and ticker in dados.columns:
            preco_live = float(dados[ticker].dropna().iloc[-1])
            
        with c_cols[idx]:
            st.markdown(f"#### **{sigla}**")
            cotas = st.number_input(f"Cotas Atuais ({sigla})", min_value=0, value=p_data["cotas"], key=f"c_{sigla}")
            preco = st.number_input(f"Preço Unitário (€) ({sigla})", min_value=0.01, value=preco_live, format="%.2f", key=f"p_{sigla}")
            cotas_input[sigla] = cotas
            precos_input[sigla] = preco

    if st.button("🚀 Calcular Ordem de Compra Otimizada", type="primary", use_container_width=True):
        targets = {"PRAB": 0.25, "IBCI": 0.45, "XDEQ": 0.30}
        
        val_atual = {a: cotas_input[a] * precos_input[a] for a in cotas_input}
        patrimonio_atual = sum(val_atual.values())
        patrimonio_futuro = patrimonio_atual + capital
        
        val_alvo = {a: patrimonio_futuro * targets[a] for a in targets}
        
        # Otimização discreta de cotas inteiras
        max_c = {a: int(capital // precos_input[a]) + 1 for a in targets}
        
        melhor_erro = float('inf')
        melhor_compras = {"PRAB": 0, "IBCI": 0, "XDEQ": 0}
        
        for c1 in range(max_c["PRAB"] + 1):
            cost1 = c1 * precos_input["PRAB"]
            if cost1 > capital: continue
            for c2 in range(max_c["IBCI"] + 1):
                cost2 = cost1 + c2 * precos_input["IBCI"]
                if cost2 > capital: continue
                for c3 in range(max_c["XDEQ"] + 1):
                    custo_total = cost2 + c3 * precos_input["XDEQ"]
                    if custo_total > capital: continue
                    
                    v_f1 = val_atual["PRAB"] + c1 * precos_input["PRAB"]
                    v_f2 = val_atual["IBCI"] + c2 * precos_input["IBCI"]
                    v_f3 = val_atual["XDEQ"] + c3 * precos_input["XDEQ"]
                    tot_f = patrimonio_atual + custo_total
                    
                    pct1, pct2, pct3 = v_f1/tot_f, v_f2/tot_f, v_f3/tot_f
                    erro = (pct1-targets["PRAB"])**2 + (pct2-targets["IBCI"])**2 + (pct3-targets["XDEQ"])**2
                    erro += (capital - custo_total) / (capital + 1) * 0.001
                    
                    if erro < melhor_erro:
                        melhor_erro = erro
                        melhor_compras = {"PRAB": c1, "IBCI": c2, "XDEQ": c3}

        st.markdown("---")
        st.subheader("📊 Plano de Compra Sugerido (XTB)")
        
        investir_por_ativo = {a: melhor_compras[a] * precos_input[a] for a in targets}
        saldo_final_est = {a: val_atual[a] + investir_por_ativo[a] for a in targets}
        
        df_res = pd.DataFrame({
            "ETF": list(targets.keys()),
            "Cotas a Comprar": [melhor_compras[a] for a in targets],
            "Investimento (€)": [f"€{investir_por_ativo[a]:,.2f}" for a in targets],
            "Saldo Final Est. (€)": [f"€{saldo_final_est[a]:,.2f}" for a in targets]
        })
        st.dataframe(df_res, use_container_width=True, hide_index=True)
        
        total_investido = sum(investir_por_ativo.values())
        caixa_residual = capital - total_investido
        patrimonio_final = patrimonio_atual + total_investido
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Patrimônio Atual", f"€{patrimonio_atual:,.2f}")
        m2.metric("Total a Investir", f"€{total_investido:,.2f}")
        m3.metric("Caixa Residual (Sobra)", f"€{caixa_residual:,.2f}")
        
        st.markdown("#### **Alocação Final Estimada após Aporte:**")
        desvios = []
        for a in targets:
            pct_f = (saldo_final_est[a] / patrimonio_final) * 100
            desvio = pct_f - (targets[a] * 100)
            st.write(f"• **{a}:** {pct_f:.1f}% *(Alvo: {int(targets[a]*100)}% | Desvio: {desvio:+.1f} pp)*")
            desvios.append(abs(desvio))

# Botão de Download
st.markdown("---")
if not dados.empty:
    csv = dados.to_csv().encode('utf-8')
    st.download_button(
        label="📥 Descarregar Dados Históricos da Carteira (CSV)",
        data=csv,
        file_name="etf_xtb_historico.csv",
        mime="text/csv"
    )