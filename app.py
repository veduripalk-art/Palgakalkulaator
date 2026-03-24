import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# !!! 1g78dHlfNWL8SXc3Ee3C_tpxWvdXNqt2edwzvUuSdW6w !!!
SHEET_ID = "1g78dHlfNWL8SXc3Ee3C_tpxWvdXNqt2edwzvUuSdW6w"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}
OPILASE_TUNNITASU = 2.83  # Fikseeritud lisatasu õpilase eest tunnis

# --- 2. ANDMETE LAADIMINE (VEAPARANDUSEGA) ---
@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # PARANDATUD RIDA: Muudame päised suureks täheks õigesti
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Teisendame kuupäevad
        df['ALATES'] = pd.to_datetime(df['ALATES'].str.strip())
        df['KUNI'] = pd.to_datetime(df['KUNI'].str.strip())
        df['TUUR'] = df['TUUR'].astype(str).str.strip()
        df['PAEV'] = df['PAEV'].astype(str).str.strip().upper()
        return df
    except Exception as e:
        st.error(f"Viga tabeli laadimisel: {e}")
        return None

# --- 3. PÄEVA TÜÜBI TUVASTAMISE LOGIKA ---
def get_matching_rows(df, tuur_nimi, valitud_kuupaev):
    mask = (
        (df['TUUR'] == tuur_nimi) & 
        (df['ALATES'] <= valitud_kuupaev) & 
        (df['KUNI'] >= valitud_kuupaev)
    )
    potentsiaalsed = df[mask]
    if potentsiaalsed.empty: return None

    wd = valitud_kuupaev.weekday() # 0=E, 1=T... 6=P
    kp_str = valitud_kuupaev.strftime("%d.%m")

    sobivad_tahised = ["DEFAULT"]
    if wd <= 4: sobivad_tahised.append("ER")
    if wd >= 5: sobivad_tahised.append("LP")
    if wd == 0: sobivad_tahised.append("E")
    if 1 <= wd <= 4: sobivad_tahised.append("T-R")
    if wd <= 3: sobivad_tahised.append("E-N")
    if wd == 4: sobivad_tahised.append("R")
    
    # 1. Kontrollime täpset kuupäeva (nt 06.04)
    eri_kp = potentsiaalsed[potentsiaalsed['PAEV'].str.contains(kp_str, na=False)]
    if not eri_kp.empty: return eri_kp.iloc[0]

    # 2. Kontrollime nädalapäeva tähist
    for tahis in reversed(sobivad_tahised):
        match = potentsiaalsed[potentsiaalsed['PAEV'] == tahis]
        if not match.empty: return match.iloc[0]
    return None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu_nimi = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu_nimi]

# --- 5. PEALINE TÖÖLAUD ---
df_tuurid = load_data()

if df_tuurid is not None:
    st.title(f"🚂 {valitud_kuu_nimi} 2026")
    
    päevi = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
    graafik_tulemused = []
    
    cols = st.columns(7) # Kalendri vaade
    
    for i in range(1, päevi + 1):
        dt = datetime(2026, k_num, i)
        with cols[(i-1)%7]:
            st.write(f"**{i:02d}.{k_num:02d}**")
            tuuri_nimed = sorted(df_tuurid['TUUR'].unique().tolist())
            t_valik = st.selectbox("Tuur", ["Vaba", "P", "KO"] + tuuri_nimed, key=f"t{i}", label_visibility="collapsed")
            lisa_min = st.number_input("+ min", min_value=0, step=5, key=f"m{i}")
            opilane = st.checkbox("Õps", key=f"s{i}")

            tunnid, tasu, nv_tunnid = 0.0, 0.0, 0.0
            is_work = False

            if t_valik == "P":
                nv_tunnid = 8.0
            elif t_valik == "KO":
                tunnid = 8.0
                tasu = 8.0 * baaspalk
                is_work = True
            elif t_valik != "Vaba":
                leitud_rida = get_matching_rows(df_tuurid, t_valik, dt)
                
                if leitud_rida is not None:
                    try:
                        # Kellaaja arvutus
                        s_str = str(leitud_rida['ALGUS']).strip()
                        e_str = str(leitud_rida['LOPP']).strip()
                        fmt = "%H:%M"
                        s_dt = datetime.strptime(s_str, fmt)
                        e_dt = datetime.strptime(e_str, fmt)
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        
                        # TASU ARVUTUS
                        kordaja = 1.2 if str(leitud_rida['SPLIT']).upper() == "TRUE" else 1.0
                        paeva_pohitasu = tunnid * (baaspalk * kordaja)
                        # Õpilase lisa ainult töötatud aja eest
                        paeva_opilase_lisa = (tunnid * OPILASE_TUNNITASU) if opilane else 0.0
                        
                        tasu = paeva_pohitasu + paeva_opilase_lisa
                        is_work = True
                    except Exception:
                        st.error("Viga kellaajaga")

            graafik_tulemused.append({"t": tunnid, "r": tasu, "nv": nv_tunnid, "work": is_work})

    # --- 6. KOKKUVÕTE ---
    res_df = pd.DataFrame(graafik_tulemused)
    kokku_t = res_df["t"].sum()
    tegelik_norm = norm_kuu - res_df["nv"].sum()
    uletunnid = max(0, kokku_t - tegelik_norm)
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Töötatud tunde", f"{kokku_t:.2f} h")
    c2.metric("Ületunnid", f"{uletunnid:.2f} h")
    c3.metric("Ületunni lisa (0.5x)", f"{uletunnid * baaspalk * 0.5:.2f} €")
    
    toopaevi = res_df[res_df["work"] == True].shape[0]
    arvutatud_kval = min((toopaevi / 22) * KVAL_LISA[kval], KVAL_LISA[kval])
    
    bruto = res_df['r'].sum() + arvutatud_kval + (uletunnid * baaspalk * 0.5)
    st.success(f"### Prognoositav kuu Bruto: {bruto:.2f} €")
    st.info(f"Kvalifikatsioonilisa: {arvutatud_kval:.2f} € | Õpilase lisa on sisse arvutatud.")
else:
    st.warning("Ootan Google Sheetsi andmeid...")
