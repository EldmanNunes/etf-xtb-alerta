'\n=============================================================================\n📊 ETF Tracker, Rebalancer & Análise Cambial XTB — Versão v4.10 (app-v41.py)\n=============================================================================\nData de Atualização: 15/11/2026\nDescrição: Aplicação completa de gestão patrimonial, rebalanceamento tático, \n           gestão de saques defensivos e apuração fiscal para investidores UCITS.\n\nMódulos da Aplicação (Fluxo Reordenado de Trabalho):\n  1. 📈 Análise Técnica & Relatório (ETFs)\n  2. 📊 Rendimentos & Performance de Aportes\n  3. 💱 Análise Cambial, VET & Projeções\n  4. ⚖ Calculadora de Rebalanceamento por Novo Aporte\n  5. 💸 Gestão Anual de Saque & Reequilíbrio UCITS\n  6. 🏛️ Relatório Fiscal & Apuração IRS (Portugal) / IRPF (Brasil)\n\nAPIs e Fontes de Dados:\n  • Yahoo Finance (yfinance): Cotações históricas e ao vivo dos ETFs.\n  • Eurostat API: Taxa oficial de inflação HICP da Zona Euro.\n  • Frankfurter API (BCE): Taxas de câmbio históricas e spot oficiais do BCE.\n=============================================================================\n'
import os
import io
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fpdf import FPDF
from statsmodels.tsa.arima.model import ARIMA
from sklearn.linear_model import LinearRegression
st.set_page_config(page_title='ETF Tracker, Rebalancer & Análise Cambial XTB', layout='wide', page_icon='📊 ')
st.title('📊 ETF Tracker, Rebalancer & Análise Cambial XTB')
ETF_MAP = {'IBCI - Inflation Linked': {'ticker': 'IBCI.DE', 'target_pct': 0.45, 'nome': 'Inflation Linked', 'isin': 'IE00B0M62X26', 'ter': '0.09% p.a.', 'classe': 'Renda Fixa Soberana Inflação (Zona Euro)', 'indice': 'Bloomberg Euro Government Inflation-Linked Bond Index', 'politica': 'Acumulação'}, 'XDEQ - World Quality': {'ticker': 'XDEQ.DE', 'target_pct': 0.3, 'nome': 'World Quality', 'isin': 'IE00BL25JP72', 'ter': '0.25% p.a.', 'classe': 'Ações Globais (Factor Quality Equity)', 'indice': 'MSCI World Quality Index', 'politica': 'Acumulação'}, 'PRAB - Amundi 0-1Y': {'ticker': 'PRAB.DE', 'target_pct': 0.25, 'nome': 'Amundi 0-1Y', 'isin': 'LU2233156582', 'ter': '0.09% p.a.', 'classe': 'Renda Fixa Soberana Curto Prazo (Cash Equivalent)', 'indice': 'Solactive 0-1 Year Euro Government Bond Index', 'politica': 'Acumulação'}}
padroes_pos_global = {'IBCI': {'cotas': 0, 'p_compra': 230.19, 'p_venda': 230.1, 'ticker': 'IBCI.DE', 'alvo': 0.45, 'teto': 0.5, 'nome_full': 'IBCI - Inflation Linked'}, 'XDEQ': {'cotas': 0, 'p_compra': 81.82, 'p_venda': 81.75, 'ticker': 'XDEQ.DE', 'alvo': 0.3, 'teto': 0.35, 'nome_full': 'XDEQ - World Quality'}, 'PRAB': {'cotas': 0, 'p_compra': 21.84, 'p_venda': 21.82, 'ticker': 'PRAB.DE', 'alvo': 0.25, 'teto': 0.3, 'nome_full': 'PRAB - Amundi 0-1Y'}}
tickers_etf = [meta['ticker'] for meta in ETF_MAP.values()]

# =========================================================
# FUNÇÕES DE SUPORTE E UTILITÁRIOS DA APLICAÇÃO
# =========================================================

def update_carteira_state(sigla, field, widget_key):
    val = st.session_state[widget_key]
    if field == 'cotas':
        st.session_state['carteira_etfs'][sigla][field] = int(round(val)) if val is not None else 0
    else:
        st.session_state['carteira_etfs'][sigla][field] = float(val) if val is not None else 0.0
    sincronizar_chaves_carteira()

def sincronizar_carteira_com_historico():
    """Sincroniza o número total de cotas em st.session_state['carteira_etfs']
    a partir da soma dos lotes registados em st.session_state['historico_compras']."""
    if 'historico_compras' in st.session_state and isinstance(st.session_state['historico_compras'], pd.DataFrame):
        df_h = st.session_state['historico_compras']
        totais = {}
        if not df_h.empty and 'Sigla' in df_h.columns and ('Volume (Cotas)' in df_h.columns):
            vols = pd.to_numeric(df_h['Volume (Cotas)'], errors='coerce').fillna(0)
            df_temp = df_h.copy()
            df_temp['Vol_Num'] = vols
            totais = df_temp.groupby('Sigla')['Vol_Num'].sum().to_dict()
        if 'carteira_etfs' in st.session_state:
            for sigla in ['IBCI', 'XDEQ', 'PRAB']:
                cotas_totais = int(round(float(totais.get(sigla, 0))))
                if sigla in st.session_state['carteira_etfs']:
                    st.session_state['carteira_etfs'][sigla]['cotas'] = cotas_totais
    sincronizar_chaves_carteira()

def sincronizar_chaves_carteira():
    for sigla in ['IBCI', 'XDEQ', 'PRAB']:
        c_val = int(round(st.session_state['carteira_etfs'][sigla]['cotas'])) if st.session_state['carteira_etfs'][sigla]['cotas'] is not None else 0
        pc_val = float(st.session_state['carteira_etfs'][sigla]['p_compra']) if st.session_state['carteira_etfs'][sigla]['p_compra'] is not None else 0.0
        pv_val = float(st.session_state['carteira_etfs'][sigla]['p_venda']) if st.session_state['carteira_etfs'][sigla]['p_venda'] is not None else 0.0
        st.session_state['carteira_etfs'][sigla]['cotas'] = c_val
        st.session_state['carteira_etfs'][sigla]['p_compra'] = pc_val
        st.session_state['carteira_etfs'][sigla]['p_venda'] = pv_val
        keys_to_set = {f'c_t1_{sigla}': c_val, f'p_compra_t1_{sigla}': pc_val, f'p_venda_t1_{sigla}': pv_val, f'c_t2_{sigla}': c_val, f'p_compra_t2_{sigla}': pc_val, f'c_t3_{sigla}': c_val, f'p_venda_t3_{sigla}': pv_val}
        for k, v in keys_to_set.items():
            try:
                st.session_state[k] = v
            except Exception:
                pass

def aplicar_perfil_tatico(rec_i, rec_x, rec_p):
    """Callback para aplicar perfis táticos na carteira e sincronizar os widgets da barra lateral."""
    rec_i = float(rec_i)
    rec_x = float(rec_x)
    rec_p = float(rec_p)
    if 'carteira_etfs' in st.session_state:
        st.session_state['carteira_etfs']['IBCI']['alvo'] = rec_i / 100.0
        st.session_state['carteira_etfs']['IBCI']['teto'] = (rec_i + 5.0) / 100.0
        st.session_state['carteira_etfs']['XDEQ']['alvo'] = rec_x / 100.0
        st.session_state['carteira_etfs']['XDEQ']['teto'] = (rec_x + 5.0) / 100.0
        st.session_state['carteira_etfs']['PRAB']['alvo'] = rec_p / 100.0
        st.session_state['carteira_etfs']['PRAB']['teto'] = (rec_p + 5.0) / 100.0
    st.session_state['in_taa_ibci'] = rec_i
    st.session_state['in_taa_xdeq'] = rec_x
    st.session_state['in_taa_prab'] = rec_p
    sincronizar_chaves_carteira()

@st.cache_data(ttl=3600)
def carregar_dados_etfs(tickers_list, period):
    df = yf.download(tickers_list, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df = df['Close']
    return df

def obter_rentabilidade_global_historico():
    """Calcula o resumo consolidado de custos, valor de mercado e P&L líquido
    a partir de st.session_state['historico_compras']."""
    custo_total = 0.0
    valor_mercado_total = 0.0
    if 'historico_compras' in st.session_state and isinstance(st.session_state['historico_compras'], pd.DataFrame):
        df_h = st.session_state['historico_compras']
        if not df_h.empty and 'Sigla' in df_h.columns:
            for _, r in df_h.iterrows():
                sigla = str(r.get('Sigla', '')).strip().upper()
                vol = pd.to_numeric(r.get('Volume (Cotas)', 0), errors='coerce')
                vol_num = float(vol) if pd.notnull(vol) else 0.0
                p_abert = pd.to_numeric(r.get('Preço Abertura (€)', 0), errors='coerce')
                p_abert_num = float(p_abert) if pd.notnull(p_abert) else 0.0
                comiss = pd.to_numeric(r.get('Comissão (€)', 0), errors='coerce')
                comiss_num = float(comiss) if pd.notnull(comiss) else 0.0
                p_mkt = 0.0
                if 'carteira_etfs' in st.session_state and sigla in st.session_state['carteira_etfs']:
                    p_mkt = float(st.session_state['carteira_etfs'][sigla].get('p_venda', p_abert_num))
                else:
                    p_mkt = p_abert_num
                custo_lote = vol_num * p_abert_num + comiss_num
                val_mkt_lote = vol_num * p_mkt
                custo_total += custo_lote
                valor_mercado_total += val_mkt_lote
    lucro_neto = valor_mercado_total - custo_total
    retorno_pct = lucro_neto / custo_total * 100.0 if custo_total > 0 else 0.0
    return {'custo_total': custo_total, 'valor_mercado_total': valor_mercado_total, 'lucro_neto': lucro_neto, 'retorno_pct': retorno_pct}

def sanitizar_df_historico(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=['ID Posição', 'Data Compra', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Abertura (€)', 'Comissão (€)'])
    df_out = df.copy()
    cols_req = ['ID Posição', 'Data Compra', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Abertura (€)', 'Comissão (€)']
    for col in cols_req:
        if col not in df_out.columns:
            df_out[col] = '' if col in ['ID Posição', 'Data Compra', 'ETF', 'Sigla'] else 0
    df_out = df_out[cols_req]

    def _fix_id(val):
        if pd.isna(val) or val == '':
            return ''
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()
    df_out['ID Posição'] = df_out['ID Posição'].apply(_fix_id)

    def _fix_date(val):
        if pd.isna(val) or val == '':
            return ''
        if isinstance(val, (pd.Timestamp, datetime, date)):
            return val.strftime('%d/%m/%Y')
        s = str(val).strip()
        try:
            dt = pd.to_datetime(s, dayfirst=True)
            return dt.strftime('%d/%m/%Y')
        except Exception:
            return s
    df_out['Data Compra'] = df_out['Data Compra'].apply(_fix_date)
    sigla_map_to_full = {'IBCI': 'IBCI - Inflation Linked', 'XDEQ': 'XDEQ - World Quality', 'PRAB': 'PRAB - Amundi 0-1Y'}
    full_to_sigla = {v: k for k, v in sigla_map_to_full.items()}

    def _fix_sigla(row):
        sigla_val = str(row['Sigla']).strip().upper() if pd.notnull(row['Sigla']) else ''
        etf_val = str(row['ETF']).strip() if pd.notnull(row['ETF']) else ''
        if sigla_val in sigla_map_to_full:
            actual_sigla = sigla_val
        elif etf_val in full_to_sigla:
            actual_sigla = full_to_sigla[etf_val]
        else:
            actual_sigla = 'IBCI'
        actual_etf = sigla_map_to_full[actual_sigla]
        return pd.Series([actual_etf, actual_sigla])
    df_out[['ETF', 'Sigla']] = df_out.apply(_fix_sigla, axis=1)
    df_out['Volume (Cotas)'] = pd.to_numeric(df_out['Volume (Cotas)'], errors='coerce').fillna(1)
    df_out['Volume (Cotas)'] = df_out['Volume (Cotas)'].apply(lambda x: max(1, int(round(float(x)))))
    df_out['Preço Abertura (€)'] = pd.to_numeric(df_out['Preço Abertura (€)'], errors='coerce').fillna(0.01)
    df_out['Preço Abertura (€)'] = df_out['Preço Abertura (€)'].apply(lambda x: max(0.01, float(x)))
    df_out['Comissão (€)'] = pd.to_numeric(df_out['Comissão (€)'], errors='coerce').fillna(0.0)
    df_out['Comissão (€)'] = df_out['Comissão (€)'].apply(lambda x: max(0.0, float(x)))
    return df_out

def obter_df_lotes_demo():
    return pd.DataFrame([{'ID Posição': '2280842619', 'Data Compra': '09/01/2026', 'ETF': 'IBCI - Inflation Linked', 'Sigla': 'IBCI', 'Volume (Cotas)': 2, 'Preço Abertura (€)': 231.3, 'Comissão (€)': 0.0}, {'ID Posição': '1002849120', 'Data Compra': '15/12/2025', 'ETF': 'IBCI - Inflation Linked', 'Sigla': 'IBCI', 'Volume (Cotas)': 108, 'Preço Abertura (€)': 230.17, 'Comissão (€)': 0.0}, {'ID Posição': '1002849121', 'Data Compra': '10/01/2026', 'ETF': 'XDEQ - World Quality', 'Sigla': 'XDEQ', 'Volume (Cotas)': 208, 'Preço Abertura (€)': 81.82, 'Comissão (€)': 0.0}, {'ID Posição': '1002849122', 'Data Compra': '05/01/2026', 'ETF': 'PRAB - Amundi 0-1Y', 'Sigla': 'PRAB', 'Volume (Cotas)': 654, 'Preço Abertura (€)': 21.84, 'Comissão (€)': 0.0}])

def gerar_modelo_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_lotes_demo = pd.DataFrame([{'ID Posição': '2280842619', 'Data Compra': '09/01/2026', 'ETF': 'IBCI - Inflation Linked', 'Sigla': 'IBCI', 'Volume (Cotas)': 2, 'Preço Abertura (€)': 231.3, 'Comissão (€)': 0.0}, {'ID Posição': '1002849120', 'Data Compra': '15/12/2025', 'ETF': 'IBCI - Inflation Linked', 'Sigla': 'IBCI', 'Volume (Cotas)': 108, 'Preço Abertura (€)': 230.17, 'Comissão (€)': 0.0}, {'ID Posição': '1002849121', 'Data Compra': '10/01/2026', 'ETF': 'XDEQ - World Quality', 'Sigla': 'XDEQ', 'Volume (Cotas)': 208, 'Preço Abertura (€)': 81.82, 'Comissão (€)': 0.0}, {'ID Posição': '1002849122', 'Data Compra': '05/01/2026', 'ETF': 'PRAB - Amundi 0-1Y', 'Sigla': 'PRAB', 'Volume (Cotas)': 654, 'Preço Abertura (€)': 21.84, 'Comissão (€)': 0.0}])
        df_lotes_demo.to_excel(writer, sheet_name='Historico_Lotes', index=False)
        df_carteira_demo = pd.DataFrame([{'Sigla': 'IBCI', 'Volume (Cotas)': 110, 'Preço Compra (€)': 230.19, 'Preço Venda (€)': 230.1}, {'Sigla': 'XDEQ', 'Volume (Cotas)': 208, 'Preço Compra (€)': 81.82, 'Preço Venda (€)': 81.75}, {'Sigla': 'PRAB', 'Volume (Cotas)': 654, 'Preço Compra (€)': 21.84, 'Preço Venda (€)': 21.82}])
        df_carteira_demo.to_excel(writer, sheet_name='Carteira_Geral', index=False)
    return output.getvalue()

def exportar_carteira_excel_full(df_lotes, carteira_dict, df_vendas=None):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if df_lotes is not None and (not df_lotes.empty):
            df_lotes.to_excel(writer, sheet_name='Historico_Lotes', index=False)
        else:
            pd.DataFrame(columns=['ID Posição', 'Data Compra', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Abertura (€)', 'Comissão (€)']).to_excel(writer, sheet_name='Historico_Lotes', index=False)
        if df_vendas is not None and (not df_vendas.empty):
            df_vendas.to_excel(writer, sheet_name='Historico_Vendas', index=False)
        else:
            pd.DataFrame(columns=['ID Posição', 'Data Compra', 'Data Venda', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Compra (€)', 'Preço Venda (€)', 'Comissão (€)']).to_excel(writer, sheet_name='Historico_Vendas', index=False)
        rows_c = []
        if carteira_dict:
            for sigla, d in carteira_dict.items():
                rows_c.append({'Sigla': sigla, 'Volume (Cotas)': d.get('cotas', 0), 'Preço Compra (€)': d.get('p_compra', 0.0), 'Preço Venda (€)': d.get('p_venda', 0.0)})
        pd.DataFrame(rows_c).to_excel(writer, sheet_name='Carteira_Geral', index=False)
    return output.getvalue()

def processar_importacao_excel(file_bytes):
    try:
        xls = pd.ExcelFile(file_bytes)
        if 'Historico_Lotes' in xls.sheet_names:
            df_lotes = pd.read_excel(xls, sheet_name='Historico_Lotes')
            st.session_state['historico_compras'] = sanitizar_df_historico(df_lotes)
            if 'editor_lotes_compras' in st.session_state:
                del st.session_state['editor_lotes_compras']
        if 'Historico_Vendas' in xls.sheet_names:
            df_vendas = pd.read_excel(xls, sheet_name='Historico_Vendas')
            st.session_state['historico_vendas'] = sanitizar_df_vendas(df_vendas)
            if 'editor_lotes_vendas' in st.session_state:
                del st.session_state['editor_lotes_vendas']
        if 'Carteira_Geral' in xls.sheet_names:
            df_cart = pd.read_excel(xls, sheet_name='Carteira_Geral')
            for _, r in df_cart.iterrows():
                sigla = str(r.get('Sigla', '')).strip().upper()
                if 'carteira_etfs' in st.session_state and sigla in st.session_state['carteira_etfs']:
                    vol = r.get('Volume (Cotas)', r.get('Cotas', st.session_state['carteira_etfs'][sigla]['cotas']))
                    pc = r.get('Preço Compra (€)', r.get('Preço Compra', st.session_state['carteira_etfs'][sigla]['p_compra']))
                    pv = r.get('Preço Venda (€)', r.get('Preço Venda', st.session_state['carteira_etfs'][sigla]['p_venda']))
                    st.session_state['carteira_etfs'][sigla]['cotas'] = int(round(float(vol))) if pd.notnull(vol) else 0
                    st.session_state['carteira_etfs'][sigla]['p_compra'] = float(pc) if pd.notnull(pc) else 0.0
                    st.session_state['carteira_etfs'][sigla]['p_venda'] = float(pv) if pd.notnull(pv) else 0.0
        if 'Historico_Lotes' in xls.sheet_names:
            sincronizar_carteira_com_historico()
        else:
            sincronizar_chaves_carteira()
        return (True, 'Planilha Excel importada com sucesso! Todas as abas foram sincronizadas com os novos dados.')
    except Exception as e:
        return (False, f'Erro ao importar planilha: {str(e)}')

def limpar_dados_sessao():
    st.session_state['historico_compras'] = pd.DataFrame(columns=['ID Posição', 'Data Compra', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Abertura (€)', 'Comissão (€)'])
    st.session_state['historico_vendas'] = pd.DataFrame(columns=['ID Posição', 'Data Compra', 'Data Venda', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Compra (€)', 'Preço Venda (€)', 'Comissão (€)'])
    if 'editor_lotes_compras' in st.session_state:
        del st.session_state['editor_lotes_compras']
    if 'editor_lotes_vendas' in st.session_state:
        del st.session_state['editor_lotes_vendas']
    for sigla in ['IBCI', 'XDEQ', 'PRAB']:
        if 'carteira_etfs' in st.session_state and sigla in st.session_state['carteira_etfs']:
            st.session_state['carteira_etfs'][sigla]['cotas'] = 0
            p_live = 0.0
            if 'dados' in globals() and isinstance(dados, pd.DataFrame) and (not dados.empty):
                tk = padroes_pos_global.get(sigla, {}).get('ticker')
                if tk and tk in dados.columns:
                    s_t = dados[tk].dropna()
                    if not s_t.empty:
                        p_live = round(float(s_t.iloc[-1]), 2)
            if p_live == 0.0:
                p_live = float(padroes_pos_global.get(sigla, {}).get('p_compra', 0.0))
            st.session_state['carteira_etfs'][sigla]['p_compra'] = p_live
            st.session_state['carteira_etfs'][sigla]['p_venda'] = p_live
    for sigla in ['IBCI', 'XDEQ', 'PRAB']:
        for prefix in ['c_t1_', 'p_compra_t1_', 'p_venda_t1_', 'c_t2_', 'p_compra_t2_', 'c_t3_', 'p_venda_t3_']:
            key_w = f'{prefix}{sigla}'
            if key_w in st.session_state:
                del st.session_state[key_w]
    sincronizar_chaves_carteira()

@st.cache_data(ttl=86400)
def obter_hicp_oficial_eurostat():
    try:
        domain_eurostat = 'ec.' + 'europa.' + 'eu'
        endpoint_hicp = f'https://{domain_eurostat}/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr?geo=EA&coicop=CP00&lastTimePeriod=1'
        response = requests.get(endpoint_hicp, timeout=5)
        if response.status_code == 200:
            dados_hicp = response.json()
            valores = list(dados_hicp.get('value', {}).values())
            if valores:
                return round(float(valores[-1]), 1)
    except Exception:
        pass
    return 2.2

def calcular_indicadores_etf(serie):
    df = pd.DataFrame({'Preco': serie})
    df['MA50'] = df['Preco'].rolling(50).mean()
    df['MA200'] = df['Preco'].rolling(200).mean()
    df['BB_Mid'] = df['Preco'].rolling(20).mean()
    bb_std = df['Preco'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Mid'] - 2 * bb_std
    delta = df['Preco'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - 100 / (1 + rs)
    ema12 = df['Preco'].ewm(span=12, adjust=False).mean()
    ema26 = df['Preco'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    return df

def fmt_br(val, decimals=2, signed=False, prefix='', suffix=''):
    if val is None or pd.isna(val):
        return ''
    try:
        val = float(val)
        fmt_str = f'{val:+,.{decimals}f}' if signed else f'{val:,.{decimals}f}'
        res = fmt_str.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f'{prefix}{res}{suffix}'
    except Exception:
        return str(val)

def sanitizar_pdf(texto: str) -> str:
    replacements = {'•': '-', '€': 'EUR', '🟢 ': '[COMPRAR]', '🔵 ': '[MANTER]', '🟡 ': '[AGUARDAR]', '🔴 ': '[REDUZIR]', '📌 ': '-', '⚠ ': '[Aviso]', '📊 ': '', '📋 ': '', '🔍 ': '', '📈 ': '', '⚖ ': '', '💡 ': '', '🚀 ': '', '💸 ': '', '💱 ': '', 'ℹ ': '[Info]'}
    for orig, repl in replacements.items():
        texto = texto.replace(orig, repl)
    return texto.encode('latin-1', 'replace').decode('latin-1')

def enviar_email_relatorio(destinatario, assunto, corpo_texto):
    if not GMAIL_PASS or not GMAIL_USER:
        return (False, 'Senha de aplicativo ou usuário do Gmail (GMAIL_USER / GMAIL_PASS) não configurados nos Secrets do Streamlit.')
    if not destinatario or '@' not in destinatario:
        return (False, 'Por favor, introduza um e-mail de destino válido.')
    try:
        msg = MIMEText(corpo_texto, 'plain', 'utf-8')
        msg['Subject'] = assunto
        msg['From'] = GMAIL_USER
        msg['To'] = destinatario
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=20) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)
        return (True, 'E-mail enviado com sucesso!')
    except Exception as e:
        return (False, f'Falha ao enviar e-mail: {str(e)}')

def gerar_pdf_relatorio(itens_diagnostico, df_resumo_num, matriz_corr, data_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(pdf.epw, 9, sanitizar_pdf('ETF Tracker XTB - Relatório Interpretativo & Técnico (v3.2)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(pdf.epw, 5, sanitizar_pdf(f'Data de Emissao: {data_str} | Bolsa: Xetra (EUR) | Fonte: yfinance (Fecho Oficial)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('1. Tabela Resumo dos Indicadores Técnicos'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    if df_resumo_num is not None and (not df_resumo_num.empty):
        headers = ['Ativo', 'Preço', 'MA50', 'MA200', 'Dif MA', 'RSI', 'Atual', 'Alvo', 'Decisão']
        table_rows = [headers]
        for _, r in df_resumo_num.iterrows():
            preco_val = f'EUR {fmt_br(r['Preço (€)'], 2)}' if 'Preço (€)' in r and pd.notnull(r['Preço (€)']) else str(r.get('Preço', ''))
            ma50_val = f'EUR {fmt_br(r['MA50 (€)'], 2)}' if 'MA50 (€)' in r and pd.notnull(r['MA50 (€)']) else str(r.get('MA50', ''))
            ma200_val = f'EUR {fmt_br(r['MA200 (€)'], 2)}' if 'MA200 (€)' in r and pd.notnull(r['MA200 (€)']) else str(r.get('MA200', ''))
            dif_ma_val = str(r.get('Dif MA (%)', r.get('Dif MA', 'N/A')))
            rsi_val = fmt_br(r['RSI (14)'], 1) if 'RSI (14)' in r and pd.notnull(r['RSI (14)']) else str(r.get('RSI', ''))
            aloc_atual_val = str(r.get('Aloc. Atual', 'N/A'))
            aloc_alvo_val = str(r.get('Aloc. Alvo', 'N/A'))
            decisao_val = str(r.get('Decisão Integrada', r.get('Sinal Recomendado', r.get('Sinal Técnico', ''))))
            table_rows.append([str(r.get('Ativo', '')), preco_val, ma50_val, ma200_val, dif_ma_val, rsi_val, aloc_atual_val, aloc_alvo_val, decisao_val])
        with pdf.table() as table:
            for row in table_rows:
                row_cells = table.row()
                for datum in row:
                    row_cells.cell(sanitizar_pdf(datum))
        pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('2. Diagnóstico de Decisão e Ação Prática por Ativo'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    for item in itens_diagnostico:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- {item['nome']} ({item['ticker']})'), new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(pdf.epw, 4, sanitizar_pdf(f' Preço de Fecho: EUR {fmt_br(item['preco'], 2)} | MA50: EUR {fmt_br(item['ma50'], 2)} | MA200: EUR {fmt_br(item['ma200'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 4, sanitizar_pdf(f' Sinal Recomendado: {item['acao']} (RSI 14: {fmt_br(item['rsi'], 1)})'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 4, sanitizar_pdf(f' Diagnóstico: {item['explicacao']}'), new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
    if matriz_corr is not None and (not matriz_corr.empty):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(pdf.epw, 7, sanitizar_pdf('3. Matriz de Correlação dos Retornos Diários'), new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        corr_headers = ['ETF'] + list(matriz_corr.columns)
        table_data = [corr_headers]
        for idx_c, row_c in matriz_corr.iterrows():
            r_list = [str(idx_c)]
            for val in row_c:
                r_list.append(f'{val:.2f}')
            table_data.append(r_list)
        with pdf.table() as table:
            for row in table_data:
                row_cells = table.row()
                for datum in row:
                    row_cells.cell(sanitizar_pdf(datum))
    return bytes(pdf.output())

def gerar_pdf_rebalanceamento(patrimonio_atual, capital, total_investido, caixa_residual, df_res_records, alocacoes_str, data_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(pdf.epw, 10, sanitizar_pdf('XTB Portfolio Rebalancer - Plano de Aporte (v3.4)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(pdf.epw, 6, sanitizar_pdf(f'Data de emissao: {data_str} | Corretora XTB (Cotas Inteiras) | Trava de Risco (+5.0 pp)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('1. Resumo do Capital e Patrimonio'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Patrimonio Atual: EUR {fmt_br(patrimonio_atual, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Capital Disponivel para Aporte: EUR {fmt_br(capital, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Total Efetivamente Investido: EUR {fmt_br(total_investido, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Caixa Residual (Excedente nao alocado): EUR {fmt_br(caixa_residual, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('2. Ordens de Compra Sugeridas'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for rec in df_res_records:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- {rec['ETF']}: Comprar {rec['Cotas a Comprar']} cotas -> Investimento: {rec['Investimento (€)']} | Saldo Final Est.: {rec['Saldo Final Est. (€)']} '), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('3. Alocacao Final Estimada vs Alvo Estrategico'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for aloc in alocacoes_str:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- {aloc}'), new_x='LMARGIN', new_y='NEXT')
    if caixa_residual > 50.0:
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(pdf.epw, 8, sanitizar_pdf('4. Orientacao de Fracionamento Temporal (Tranchas) & Trava de Risco'), new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Excedente Retido em Liquidez: EUR {fmt_br(caixa_residual, 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf('- Motivo: Trava de Risco por Banda de Tolerancia (+5.0 pp sobre o alvo) e/ou selecao tatica de ativos elegiveis.'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf('- Recomendacao: Manter o excedente em caixa / PRAB (0-1Y) e alocar em 2 a 3 tranchas temporais (30 a 90 dias).'), new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())

def gerar_pdf_performance(df_lotes_records, resumo_etfs_records, custo_total, val_mercado_total, pnl_eur, pnl_pct, fonte_preco_str, data_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(pdf.epw, 9, sanitizar_pdf('ETF Tracker XTB - Relatório de Performance & Aportes (v3.8)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(pdf.epw, 5, sanitizar_pdf(f'Data de Emissão: {data_str} | Fonte de Preço: {fonte_preco_str} | Bolsa: Xetra (EUR)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('1. Resumo Consolidado da Carteira'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Capital Total Investido: EUR {fmt_br(custo_total, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Valor Atual da Carteira: EUR {fmt_br(val_mercado_total, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Lucro / Prejuízo Neto Total: EUR {fmt_br(pnl_eur, 2, signed=True)} ({fmt_br(pnl_pct, 2, signed=True, suffix='%')})'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('2. Resumo Consolidado por Ativo ETF (Preço Médio & Alocação)'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    if resumo_etfs_records:
        headers = ['Ativo', 'Vol Total', 'P. Médio', 'P. Atual', 'Custo Tot.', 'Val. Mercado', 'P&L', 'Retorno', 'Aloc. Real', 'Aloc. Alvo', 'Desvio']
        table_rows = [headers]
        for r in resumo_etfs_records:
            table_rows.append([str(r.get('Ativo', '')), str(r.get('Volume Total', '')), str(r.get('Preço Médio (€)', '')), str(r.get('Preço Atual (€)', '')), str(r.get('Custo Total (€)', '')), str(r.get('Valor Mercado (€)', '')), str(r.get('P&L (€)', '')), str(r.get('Retorno (%)', '')), str(r.get('Alocação Real (%)', '')), str(r.get('Alocação Alvo (%)', '')), str(r.get('Desvio (pp)', ''))])
        with pdf.table() as table:
            for row in table_rows:
                row_cells = table.row()
                for datum in row:
                    row_cells.cell(sanitizar_pdf(datum))
        pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('3. Histórico Detalhado de Lotes de Compra Registados'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    if df_lotes_records:
        lote_headers = ['Data', 'Ativo', 'Cotas', 'P. Abertura', 'P. Mercado', 'Custo Tot.', 'Val. Atual', 'P&L Neto', 'Retorno']
        lote_rows = [lote_headers]
        for r in df_lotes_records:
            p_ab = f'EUR {fmt_br(r['Preço Abertura (€)'], 2)}' if isinstance(r.get('Preço Abertura (€)'), (int, float)) else str(r.get('Preço Abertura (€)', ''))
            p_mkt = f'EUR {fmt_br(r['Preço Mercado (€)'], 2)}' if isinstance(r.get('Preço Mercado (€)'), (int, float)) else str(r.get('Preço Mercado (€)', ''))
            c_tot = f'EUR {fmt_br(r['Custo Total Abertura (€)'], 2)}' if isinstance(r.get('Custo Total Abertura (€)'), (int, float)) else str(r.get('Custo Total Abertura (€)', ''))
            v_mkt = f'EUR {fmt_br(r['Valor Mercado Atual (€)'], 2)}' if isinstance(r.get('Valor Mercado Atual (€)'), (int, float)) else str(r.get('Valor Mercado Atual (€)', ''))
            pnl_val = f'EUR {fmt_br(r['Lucro Neto (€)'], 2, signed=True)}' if isinstance(r.get('Lucro Neto (€)'), (int, float)) else str(r.get('Lucro Neto (€)', ''))
            ret_val = fmt_br(r['Retorno (%)'], 2, signed=True, suffix='%') if isinstance(r.get('Retorno (%)'), (int, float)) else str(r.get('Retorno (%)', ''))
            lote_rows.append([str(r.get('Data Compra', '')), str(r.get('Sigla', '')), str(r.get('Volume (Cotas)', '')), p_ab, p_mkt, c_tot, v_mkt, pnl_val, ret_val])
        with pdf.table() as table:
            for row in lote_rows:
                row_cells = table.row()
                for datum in row:
                    row_cells.cell(sanitizar_pdf(datum))
    return bytes(pdf.output())

def gerar_pdf_saque(patrimonio_inicial, hicp, saque_teorico, saque_efetivo, ativo_venda, cotas_vendidas, tabela_records, data_str, justificativa_saque=None, protecao_info=None, fichas_ordens_xtb=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(pdf.epw, 10, sanitizar_pdf('Carteira Ideal UCITS - Gestão Anual de Saque & Reequilíbrio (v3.5)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(pdf.epw, 6, sanitizar_pdf(f'Data da Operacao: {data_str} | Proteção de Fundo & Reequilíbrio Tático'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('1. Parâmetros e Saque Recomendado'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Patrimonio Inicial: EUR {fmt_br(patrimonio_inicial, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Inflacao HICP: {fmt_br(hicp, 1, suffix='%')}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Saque Teorico Calculado (3.5% + HICP): EUR {fmt_br(saque_teorico, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Valor Efetivamente Sacado: EUR {fmt_br(saque_efetivo, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Ordem de Venda: {ativo_venda} ({cotas_vendidas} cotas)'), new_x='LMARGIN', new_y='NEXT')
    if justificativa_saque:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Justificativa Tática: {justificativa_saque}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('2. Estado da Carteira Apos Venda'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for rec in tabela_records:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- {rec['Ativo']}: Saldo EUR {rec['Saldo (€)']} | Actual: {rec['% Atual']} | Meta: {rec['% Meta']} | Desvio: {rec['Desvio']}'), new_x='LMARGIN', new_y='NEXT')
    if protecao_info:
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(pdf.epw, 8, sanitizar_pdf('3. Trava de Proteção de Fundo & Preservação Patrimonial'), new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- {protecao_info}'), new_x='LMARGIN', new_y='NEXT')
    if fichas_ordens_xtb:
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(pdf.epw, 8, sanitizar_pdf('4. Guia de Execução de Liquidação por ID na XTB'), new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        for item in fichas_ordens_xtb:
            pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- ID #{item.get('ID Posição XTB', '')} | {item.get('ETF', '')}: {item.get('Ação na XTB', '')} | Preço Compra: {item.get('Preço Compra (€)', '')} | P&L: {item.get('P&L Est. (€)', '')}'), new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())

@st.cache_data(ttl=86400)
def obter_taxa_cambio_historica(data_str, base='EUR', alvo='BRL'):
    """Obtém a taxa de câmbio histórica oficial do BCE (Frankfurter API) para uma data específica (DD/MM/YYYY ou YYYY-MM-DD)."""
    try:
        if '/' in str(data_str):
            dt_obj = datetime.strptime(str(data_str).strip(), '%d/%m/%Y')
        else:
            dt_obj = pd.to_datetime(data_str)
        dt_fmt = dt_obj.strftime('%Y-%m-%d')
        domain_frankfurter = 'api.' + 'frankfurter.' + 'dev'
        endpoint = f'https://{domain_frankfurter}/v1/{dt_fmt}?from={base}&to={alvo}'
        r = requests.get(endpoint, timeout=5)
        if r.status_code == 200:
            val = r.json().get('rates', {}).get(alvo)
            if val is not None:
                return float(val)
    except Exception:
        pass
    try:
        df_c = obter_dados_cambio(base=base, alvo=alvo, inicio='2020-01-01')
        if not df_c.empty:
            idx_dt = pd.to_datetime(dt_obj)
            if idx_dt in df_c.index:
                return float(df_c.loc[idx_dt, 'rate'])
            idx_nearest = df_c.index.get_indexer([idx_dt], method='nearest')[0]
            return float(df_c.iloc[idx_nearest]['rate'])
    except Exception:
        pass
    return 6.12

def sanitizar_df_vendas(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=['ID Posição', 'Data Compra', 'Data Venda', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Compra (€)', 'Preço Venda (€)', 'Comissão (€)'])
    df_out = df.copy()
    cols_req = ['ID Posição', 'Data Compra', 'Data Venda', 'ETF', 'Sigla', 'Volume (Cotas)', 'Preço Compra (€)', 'Preço Venda (€)', 'Comissão (€)']
    for col in cols_req:
        if col not in df_out.columns:
            df_out[col] = '' if col in ['ID Posição', 'Data Compra', 'Data Venda', 'ETF', 'Sigla'] else 0
    df_out = df_out[cols_req]

    def _fix_id(val):
        if pd.isna(val) or val == '':
            return ''
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()
    df_out['ID Posição'] = df_out['ID Posição'].apply(_fix_id)

    def _fix_date(val):
        if pd.isna(val) or val == '':
            return datetime.now().strftime('%d/%m/%Y')
        if isinstance(val, (pd.Timestamp, datetime, date)):
            return val.strftime('%d/%m/%Y')
        s = str(val).strip()
        try:
            dt = pd.to_datetime(s, dayfirst=True)
            return dt.strftime('%d/%m/%Y')
        except Exception:
            return s
    df_out['Data Compra'] = df_out['Data Compra'].apply(_fix_date)
    df_out['Data Venda'] = df_out['Data Venda'].apply(_fix_date)
    sigla_map_to_full = {'IBCI': 'IBCI - Inflation Linked', 'XDEQ': 'XDEQ - World Quality', 'PRAB': 'PRAB - Amundi 0-1Y'}
    full_to_sigla = {v: k for k, v in sigla_map_to_full.items()}

    def _fix_sigla(row):
        sigla_val = str(row['Sigla']).strip().upper() if pd.notnull(row['Sigla']) else ''
        etf_val = str(row['ETF']).strip() if pd.notnull(row['ETF']) else ''
        if sigla_val in sigla_map_to_full:
            actual_sigla = sigla_val
        elif etf_val in full_to_sigla:
            actual_sigla = full_to_sigla[etf_val]
        else:
            actual_sigla = 'IBCI'
        actual_etf = sigla_map_to_full[actual_sigla]
        return pd.Series([actual_etf, actual_sigla])
    df_out[['ETF', 'Sigla']] = df_out.apply(_fix_sigla, axis=1)
    df_out['Volume (Cotas)'] = pd.to_numeric(df_out['Volume (Cotas)'], errors='coerce').fillna(1).apply(lambda x: max(1, int(round(float(x)))))
    df_out['Preço Compra (€)'] = pd.to_numeric(df_out['Preço Compra (€)'], errors='coerce').fillna(0.01).apply(lambda x: max(0.01, float(x)))
    df_out['Preço Venda (€)'] = pd.to_numeric(df_out['Preço Venda (€)'], errors='coerce').fillna(0.01).apply(lambda x: max(0.01, float(x)))
    df_out['Comissão (€)'] = pd.to_numeric(df_out['Comissão (€)'], errors='coerce').fillna(0.0).apply(lambda x: max(0.0, float(x)))
    return df_out

def obter_df_vendas_demo():
    return pd.DataFrame([{'ID Posição': '1002849120', 'Data Compra': '15/01/2025', 'Data Venda': '14/11/2026', 'ETF': 'IBCI - Inflation Linked', 'Sigla': 'IBCI', 'Volume (Cotas)': 5, 'Preço Compra (€)': 225.5, 'Preço Venda (€)': 230.1, 'Comissão (€)': 0.0}, {'ID Posição': '2280842619', 'Data Compra': '10/02/2025', 'Data Venda': '14/11/2026', 'ETF': 'XDEQ - World Quality', 'Sigla': 'XDEQ', 'Volume (Cotas)': 10, 'Preço Compra (€)': 75.2, 'Preço Venda (€)': 81.75, 'Comissão (€)': 0.0}])

def gerar_pdf_fiscal(patrimonio_vendas_eur, total_lucro_eur, patrimonio_vendas_brl, total_lucro_brl, tabela_irs_records, tabela_irpf_records, data_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(pdf.epw, 10, sanitizar_pdf('Carteira Ideal UCITS - Relatório Fiscal & Apuração IRS / IRPF (v3.8)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(pdf.epw, 6, sanitizar_pdf(f'Data da Emissão: {data_str} | Suporte Fiscal Portugal (IRS Anexo G) & Brasil (IRPF GCAP)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('1. Resumo Geral de Apuração de Mais-Valias'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Total de Alienações (€): EUR {fmt_br(patrimonio_vendas_eur, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Mais-Valia Líquida Acumulada (€ - IRS Portugal): EUR {fmt_br(total_lucro_eur, 2, signed=True)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Total de Alienações em Reais (BRL): R$ {fmt_br(patrimonio_vendas_brl, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Ganho de Capital Acumulado (BRL - IRPF Brasil): R$ {fmt_br(total_lucro_brl, 2, signed=True)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('2. Portugal - Declaração de IRS (Anexo G / Categoria G)'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    for r in tabela_irs_records:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Pos #{r.get('ID Posição', '')} | {r.get('Ativo', '')} | Acq: {r.get('Data Aquisição', '')} ({r.get('Custo (€)', '')}) | Alien: {r.get('Data Alienação', '')} ({r.get('Venda (€)', '')}) | Result: {r.get('Mais-Valia (€)', '')}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(pdf.epw, 8, sanitizar_pdf('3. Brasil - Declaração de IRPF (Ganho de Capital no Exterior - GCAP)'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    for r in tabela_irpf_records:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Pos #{r.get('ID Posição', '')} | {r.get('Ativo', '')} | Compra: {r.get('Data Compra', '')} (Tx: {r.get('Câmbio Compra', '')} -> {r.get('Custo BRL', '')}) | Venda: {r.get('Data Venda', '')} (Tx: {r.get('Câmbio Venda', '')} -> {r.get('Venda BRL', '')}) | Result: {r.get('Ganho BRL', '')}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.multi_cell(pdf.epw, 4, sanitizar_pdf('Nota: Este documento possui caráter exclusivamente informativo de suporte à elaboração das declarações fiscais (Finanças Portugal & Receita Federal do Brasil). As taxas de câmbio são baseadas no fecho diário oficial do Banco Central Europeu (BCE).'), new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())

@st.cache_data(ttl=14400)
def obter_dados_cambio(base='EUR', alvo='BRL', inicio='2024-01-01'):
    domain_frankfurter = 'api.' + 'frankfurter.' + 'dev'
    endpoint_fx = f'https://{domain_frankfurter}/v1/{inicio}..?from={base}&to={alvo}'
    try:
        r = requests.get(endpoint_fx, timeout=10)
        if r.status_code == 200:
            data = r.json().get('rates', {})
            df = pd.DataFrame([{'date': pd.to_datetime(d), 'rate': v[alvo]} for d, v in data.items()])
            df = df.set_index('date').sort_index()
            return df
    except Exception:
        pass
    datas = pd.date_range(start=inicio, end=pd.Timestamp.today(), freq='B')
    np.random.seed(42)
    ret = np.random.normal(0.0001, 0.006, len(datas))
    precos = 5.9563 * np.exp(np.cumsum(ret) - np.cumsum(ret)[-1])
    df = pd.DataFrame({'rate': precos}, index=datas)
    return df

def calcular_indicadores_cambio(df):
    df = df.copy()
    df['MA20'] = df['rate'].rolling(20).mean()
    df['MA90'] = df['rate'].rolling(90).mean()
    df['Std20'] = df['rate'].rolling(20).std()
    df['Bollinger_Upper'] = df['MA20'] + 2 * df['Std20']
    df['Bollinger_Lower'] = df['MA20'] - 2 * df['Std20']
    df['Z_Score'] = (df['rate'] - df['MA20']) / df['Std20']
    df['Sinal'] = 0
    df.loc[df['Z_Score'] <= -1.8, 'Sinal'] = 1
    df.loc[df['Z_Score'] >= 1.8, 'Sinal'] = -1
    return df

def arima_projecao_cambio(df, dias=30):
    s = df['rate'].dropna()
    try:
        model = ARIMA(s.values, order=(1, 1, 1))
        res = model.fit().get_forecast(steps=dias)
        f_mean = res.predicted_mean
        f_ci = res.conf_int(alpha=0.05)
        ci_lower = f_ci[:, 0]
        ci_upper = f_ci[:, 1]
    except Exception:
        f_mean = np.full(dias, s.iloc[-1])
        ci_lower = f_mean * 0.97
        ci_upper = f_mean * 1.03
    X = np.arange(len(s)).reshape(-1, 1)
    reg = LinearRegression().fit(X, s.values)
    y_tend = reg.predict(np.arange(len(s), len(s) + dias).reshape(-1, 1))
    idx = pd.date_range(start=s.index[-1] + pd.Timedelta(days=1), periods=dias, freq='B')
    return pd.DataFrame({'ARIMA': f_mean, 'Lower_CI': ci_lower, 'Upper_CI': ci_upper, 'Trend': y_tend}, index=idx)

def monte_carlo_cambio(s0, dias=30, n_sim=10000, m_compra=5.95, m_venda=6.2, ret=None):
    mu = ret.mean() if ret is not None else 0.00015
    sig = ret.std() if ret is not None else 0.0065
    np.random.seed(42)
    choques = np.random.normal(0, 1, (dias, n_sim))
    fatores = np.exp(mu - 0.5 * sig ** 2 + sig * choques)
    precos = np.zeros((dias + 1, n_sim))
    precos[0] = s0
    for t in range(1, dias + 1):
        precos[t] = precos[t - 1] * fatores[t - 1]
    finais = precos[-1]
    max_caminhos = np.max(precos, axis=0)
    min_caminhos = np.min(precos, axis=0)
    prob_v = np.mean(max_caminhos >= m_venda) * 100
    prob_c = np.mean(min_caminhos <= m_compra) * 100
    probabilidades = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99]
    tabela_prob = []
    for p in probabilidades:
        alvo_compra = np.percentile(min_caminhos, p)
        alvo_venda = np.percentile(max_caminhos, 100 - p)
        tabela_prob.append({'Probabilidade': fmt_br(p, 0, suffix='%'), 'Alvo Compra (Mínima <= X)': fmt_br(alvo_compra, 4), 'Alvo Venda (Máxima >= Y)': fmt_br(alvo_venda, 4)})
    return {'prob_venda': prob_v, 'prob_compra': prob_c, 'tabela_prob': pd.DataFrame(tabela_prob)}

def gerar_pdf_cambio(base_m, alvo_m, s0, s_compra, s_venda, z_score, diag, m_compra, m_venda, prob_c, prob_v, arima_30d, df_tb_records, df_resumo_num_cambio, data_str, sim_dados=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(pdf.epw, 9, sanitizar_pdf(f'Relatório de Análise Cambial {base_m}/{alvo_m} (v3.6 - VET & IOF)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(pdf.epw, 5, sanitizar_pdf(f'Data de Emissao: {data_str} | API: Frankfurter (ECB) | Monte Carlo, ARIMA & VET (Wise/XTB)'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('1. Tabela Resumo dos Indicadores Cambiais'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    if df_resumo_num_cambio is not None and (not df_resumo_num_cambio.empty):
        headers = ['Par', 'Spot', 'Compra Ef.', 'Venda Ef.', 'MA20', 'MA90', 'Dif MA20', 'BB Inf', 'BB Sup', 'Z-Score', 'Vol. Anual', 'Sinal']
        table_rows = [headers]
        for _, r in df_resumo_num_cambio.iterrows():
            table_rows.append([str(r.get('Par', f'{base_m}/{alvo_m}')), str(r.get('Spot', fmt_br(s0, 4))), str(r.get('Compra Ef.', fmt_br(s_compra, 4))), str(r.get('Venda Ef.', fmt_br(s_venda, 4))), str(r.get('MA20', '')), str(r.get('MA90', '')), str(r.get('Dif MA20 (%)', '')), str(r.get('BB Inf', '')), str(r.get('BB Sup', '')), str(r.get('Z-Score', fmt_br(z_score, 2))), str(r.get('Vol. Anual', '')), str(r.get('Sinal Operacional', diag))])
        with pdf.table() as table:
            for row in table_rows:
                row_cells = table.row()
                for datum in row:
                    row_cells.cell(sanitizar_pdf(datum))
        pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('2. Diagnóstico Operacional & Estrutura de Cotações'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Cotação Spot (Mid-Market): {alvo_m} {fmt_br(s0, 4)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Estimativa de Compra Efetiva (+Spread): {alvo_m} {fmt_br(s_compra, 4)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Estimativa de Venda Efetiva (-Spread): {alvo_m} {fmt_br(s_venda, 4)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Z-Score Atual: {fmt_br(z_score, 2)} desvios padrão -> Diagnóstico: {diag}'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('3. Projeção ARIMA & Metas Monte Carlo'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Projeção ARIMA (30 dias úteis): {alvo_m} {fmt_br(arima_30d, 2)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Meta de Compra: {alvo_m} {fmt_br(m_compra, 2)} (Probabilidade de atingimento: {fmt_br(prob_c, 1, suffix='%')})'), new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Meta de Venda: {alvo_m} {fmt_br(m_venda, 2)} (Probabilidade de atingimento: {fmt_br(prob_v, 1, suffix='%')})'), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(pdf.epw, 7, sanitizar_pdf('4. Matriz de Probabilidade de Alcance (10.000 Trajetórias)'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for rec in df_tb_records:
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Probabilidade {rec['Probabilidade']}: Compra <= {alvo_m} {rec['Alvo Compra (Mínima <= X)']} | Venda >= {alvo_m} {rec['Alvo Venda (Máxima >= Y)']} '), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    if sim_dados:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(pdf.epw, 7, sanitizar_pdf('5. Simulação Financeira, VET & Lotes DCA (Valores Absolutos)'), new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Capital a Converter: {base_m} {fmt_br(sim_dados['montante_base'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Cotação Comercial Bruta (Spot): {alvo_m} {fmt_br(s0, 4)} | Bruto: {alvo_m} {fmt_br(sim_dados['valor_bruto_alvo'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Tarifa da Plataforma / Spread ({fmt_br(sim_dados.get('spread_pct', 0.64), 2, suffix='%')}): {alvo_m} {fmt_br(sim_dados['custo_plataforma_alvo'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Imposto IOF ({fmt_br(sim_dados['iof_pct'], 2, suffix='%')}): {alvo_m} {fmt_br(sim_dados['custo_iof_alvo'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Total Pago Efetivo com Tarifas & Impostos: {alvo_m} {fmt_br(sim_dados['valor_efetivo_compra_alvo'], 2)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Valor Efetivo Total (VET): 1 {base_m} = {alvo_m} {fmt_br(sim_dados['vet_taxa'], 4)}'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Lote 1 (30% Proteção Imediata): {base_m} {fmt_br(sim_dados['lote1_base'], 2)} -> {alvo_m} {fmt_br(sim_dados['lote1_efetivo_alvo'], 2)} (Taxa VET {fmt_br(sim_dados['vet_taxa'], 4)})'), new_x='LMARGIN', new_y='NEXT')
        pdf.multi_cell(pdf.epw, 5, sanitizar_pdf(f'- Lotes 2 e 3 (70% Ordens Limite em Recuos): {base_m} {fmt_br(sim_dados['lotes23_base'], 2)} -> {alvo_m} {fmt_br(sim_dados['lotes23_efetivo_alvo'], 2)}'), new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())

# =========================================================
# FLUXO DE EXECUÇÃO PRINCIPAL DA APLICAÇÃO
# =========================================================

st.sidebar.header('⚙ Configurações Gerais')
periodo = st.sidebar.selectbox('Período Histórico (Gráficos ETFs):', options=['1y', '2y', '5y', '10y', 'max'], index=2)
dados = carregar_dados_etfs(tickers_etf, periodo)

if 'carteira_etfs' not in st.session_state:
    st.session_state['carteira_etfs'] = padroes_pos_global.copy()
    for sigla, info in st.session_state['carteira_etfs'].items():
        tk = info["ticker"]
        if not dados.empty and tk in dados.columns:
            s_t = dados[tk].dropna()
            if not s_t.empty:
                p_live = float(s_t.iloc[-1])
                info["p_compra"] = round(p_live, 2)
                info["p_venda"] = round(p_live, 2)
    sincronizar_chaves_carteira()

st.sidebar.markdown('---')
st.sidebar.subheader('📈 Indicadores Técnicos (ETFs)')
mostrar_ma = st.sidebar.checkbox('Médias Móveis (MA50 / MA200)', value=True)
mostrar_bb = st.sidebar.checkbox('Bandas de Bollinger (20, 2)', value=True)
mostrar_rsi = st.sidebar.checkbox('RSI (14)', value=True)
mostrar_macd = st.sidebar.checkbox('MACD (12, 26, 9)', value=True)
st.sidebar.markdown('---')
st.sidebar.subheader('🎯 Alocação Tática Dinâmica & Metas (TAA)')
st.sidebar.caption('Defina percentuais flexíveis ou escolha um perfil tático pré-definido.')
m_ibci_curr = float(st.session_state.get('carteira_etfs', {}).get('IBCI', {}).get('alvo', 0.45) * 100)
m_xdeq_curr = float(st.session_state.get('carteira_etfs', {}).get('XDEQ', {}).get('alvo', 0.3) * 100)
m_prab_curr = float(st.session_state.get('carteira_etfs', {}).get('PRAB', {}).get('alvo', 0.25) * 100)
col_taa1, col_taa2, col_taa3 = st.sidebar.columns(3)
with col_taa1:
    in_m_ibci = st.number_input('IBCI (%)', min_value=0.0, max_value=100.0, value=m_ibci_curr, step=1.0, key='in_taa_ibci')
with col_taa2:
    in_m_xdeq = st.number_input('XDEQ (%)', min_value=0.0, max_value=100.0, value=m_xdeq_curr, step=1.0, key='in_taa_xdeq')
with col_taa3:
    in_m_prab = st.number_input('PRAB (%)', min_value=0.0, max_value=100.0, value=m_prab_curr, step=1.0, key='in_taa_prab')
soma_m = in_m_ibci + in_m_xdeq + in_m_prab
if abs(soma_m - 100.0) < 0.01:
    st.sidebar.success('🟢 Soma das Metas: 100%')
    if 'carteira_etfs' in st.session_state:
        st.session_state['carteira_etfs']['IBCI']['alvo'] = in_m_ibci / 100.0
        st.session_state['carteira_etfs']['IBCI']['teto'] = (in_m_ibci + 5.0) / 100.0
        st.session_state['carteira_etfs']['XDEQ']['alvo'] = in_m_xdeq / 100.0
        st.session_state['carteira_etfs']['XDEQ']['teto'] = (in_m_xdeq + 5.0) / 100.0
        st.session_state['carteira_etfs']['PRAB']['alvo'] = in_m_prab / 100.0
        st.session_state['carteira_etfs']['PRAB']['teto'] = (in_m_prab + 5.0) / 100.0
else:
    st.sidebar.warning(f'⚠️ Total das metas: {soma_m:.1f}% (deve ser 100%)')
st.sidebar.markdown('**⚡ Perfis Táticos Pré-Definidos:**')
col_p1, col_p2, col_p3 = st.sidebar.columns(3)
col_p1.button('🛡️ Defensivo', help='50% IBCI / 25% XDEQ / 25% PRAB', use_container_width=True, key='btn_prof_def', on_click=aplicar_perfil_tatico, args=(50.0, 25.0, 25.0))
col_p2.button('⚖️ Equilibrado', help='45% IBCI / 30% XDEQ / 25% PRAB', use_container_width=True, key='btn_prof_eq', on_click=aplicar_perfil_tatico, args=(45.0, 30.0, 25.0))
col_p3.button('🚀 Expansão', help='35% IBCI / 40% XDEQ / 25% PRAB', use_container_width=True, key='btn_prof_exp', on_click=aplicar_perfil_tatico, args=(35.0, 40.0, 25.0))
try:
    hicp_v = float(obter_hicp_oficial_eurostat())
except Exception:
    hicp_v = 2.1
m50_x, m200_x, rsi_x = (0.0, 0.0, 50.0)
if 'dados' in globals() and isinstance(dados, pd.DataFrame) and (not dados.empty):
    if 'XDEQ.DE' in dados.columns:
        s_x = dados['XDEQ.DE'].dropna()
        if len(s_x) >= 50:
            m50_x = float(s_x.tail(50).mean())
            m200_x = float(s_x.tail(200).mean()) if len(s_x) >= 200 else m50_x
            d_x = s_x.diff()
            g_x = float(d_x.where(d_x > 0, 0).tail(14).mean())
            l_x = float((-d_x.where(d_x < 0, 0)).tail(14).mean())
            rsi_x = 100 - 100 / (1 + g_x / l_x) if l_x > 0 else 50.0
if hicp_v > 3.5 or (m50_x < m200_x and m50_x > 0):
    rec_prof_name = 'Defensivo'
    rec_i, rec_x, rec_p = (50.0, 25.0, 25.0)
    rec_icon = '🛡️'
    rec_motivo = f'Inflação HICP elevada ({fmt_br(hicp_v, 1, suffix='%')}) ou XDEQ em tendência de baixa.'
elif hicp_v < 3.0 and m50_x > m200_x and (rsi_x > 50):
    rec_prof_name = 'Expansão'
    rec_i, rec_x, rec_p = (35.0, 40.0, 25.0)
    rec_icon = '🚀'
    rec_motivo = f'Inflação HICP controlada ({fmt_br(hicp_v, 1, suffix='%')}) e XDEQ em alta técnica.'
else:
    rec_prof_name = 'Equilibrado'
    rec_i, rec_x, rec_p = (45.0, 30.0, 25.0)
    rec_icon = '⚖️'
    rec_motivo = f'Cenário macroeconómico e técnico equilibrado (HICP: {fmt_br(hicp_v, 1, suffix='%')}).'
st.sidebar.markdown('---')
st.sidebar.markdown('**💡 Diagnóstico Inteligente (Smart TAA):**')
st.sidebar.info(f'**Sugestão Tática:** {rec_icon} **{rec_prof_name}** ({int(rec_i)}% IBCI / {int(rec_x)}% XDEQ / {int(rec_p)}% PRAB)\n\n*Motivo:* {rec_motivo}')
st.sidebar.button(f'⚡ Aplicar Sugestão ({rec_prof_name})', use_container_width=True, key='btn_apply_smart_taa', on_click=aplicar_perfil_tatico, args=(rec_i, rec_x, rec_p))
