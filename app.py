import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# Sinu tabeli ID
SHEET_ID = "123_0JLW-SPtFugfMLTCIvTaL80Puexw875lWOmwXvjc"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}
OPILASE_TUNNITASU = 2.83 

# --- 2. ANDMETE LAADIMINE ---
@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # Teeme veerunimed korda
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Puhastame andmed: muudame kõik tekstiks ja eemaldame tühikud enne töötlemist
        for col in ['TUUR', 'PAEV', 'ALGUS', 'LOPP', 'SPLIT']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        # Kuupäevade teisendus (vigade puhul paneb tühja väärtuse)
        df['ALATES'] = pd.to_datetime(df['ALATES'], errors='coerce')
        df['KUNI'] = pd.to_datetime(df['KUNI'], errors='coerce')
        
        # Eemaldame read, kus pole tuuri nime või kuupäeva
        df = df.dropna(subset=['TUUR', 'ALATES', 'KUNI'])
        return df
    except Exception as e:
        st.error(f"Viga tabeli laadimisel: {e}")
        return None

# --- 3. TUURI LEIDMINE ---
def get_matching_rows(df, tuur_nimi, valitud_kuupaev):
    # Filtreerime nime ja kehtivuse järgi
    mask = (
        (df['TUUR'] == tuur_nimi) & 
        (df['ALATES'] <= valitud_kuupaev) & 
        (df['KUNI'] >= valitud_kuupaev)
    )
    potentsiaalsed = df[mask]
    if potentsiaalsed.empty: return None

    wd = valitud_kuupaev.weekday() 
    kp_str = valitud_kuupaev.strftime("%d.%m")
    
    # Määrame tänasele päevale sobivad tähised
    sobivad = ["DEFAULT"]
    if wd <= 4: sobivad.append("ER")
    if wd >= 5: sobivad.append("LP")
    if wd == 0: sobivad.append("E")
    if 1 <= wd <= 4: sobivad.append("T-R")
    if wd <= 3: sobivad.append("E-N")
    if wd == 4: sobivad.append("R")
    
    # 1. Prioriteet: täpne kuupäev
    match = potentsiaalsed[potentsiaalsed['PAEV'].str.contains(kp_str, na=False)]
    if not match.empty: return match.iloc[0]

    # 2. Prioriteet: tähis (ER, LP jne)
    for tahis in reversed(sobivad):
        match = potentsiaalsed[potentsiaalsed['PAEV'].str.upper() == tahis]
        if not match.empty: return match.iloc[0]
    return None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Seaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_map = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_map[valitud_kuu]

# --- 5. PEALINE TÖÖLAUD ---
df_tuurid = load_data()

if df_tuurid is not None:
    st.title(f"🚂 {valitud_kuu} 2026")
    
    paevi_kuus = (pd.Timestamp(2026, k_num, 1) + pd.offsets.MonthEnd(0)).day
    graafik_tulemused = []
    
    cols = st.columns(7) 
    
    for i in range(1, paevi_kuus + 1):
        dt = datetime(2026, k_num, i)
        with cols[(i-1)%7]:
            st.write(f"**{i:02d}.{k_num:02d}**")
            tuuri_nimed = sorted(df_tuurid['TUUR'].unique().tolist())
            t_valik = st.selectbox("T", ["Vaba", "P", "KO"] + tuuri_nimed, key=f"t{i}", label_visibility="collapsed")
            lisa_min = st.number_input("+min", min_value=0, step=5, key=f"m{i}")
            opilane = st.checkbox("Õ", key=f"s{i}")

            tunnid, tasu, nv_tunnid = 0.0, 0.0, 0.0
            is_work = False

            if t_valik == "P":
                nv_tunnid = 8.0
            elif t_valik == "KO":
                tunnid = 8.0
                tasu = 8.0 * baaspalk
                is_work = True
            elif t_valik != "Vaba":
                rida = get_matching_rows(df_tuurid, t_valik, dt)
                if rida is not None:
                    try:
                        # Puhastame kellaaja tekstist igaks juhuks
                        s_str = str(rida['ALGUS']).replace('.', ':')
                        e_str = str(rida['LOPP']).replace('.', ':')
                        
                        s_dt = datetime.strptime(s_str, "%H:%M")
                        e_dt = datetime.strptime(e_str, "%H:%M")
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa_min / 60)
                        
                        # Split tasu (1.2x)
                        kordaja = 1.2 if str(rida['SPLIT']).upper() == "TRUE" else 1.0
                        tasu = (tunnid * baaspalk * kordaja) + (tunnid * OPILASE_TUNNITASU if opilane else 0)
                        is_work = True
                    except:
                        pass # Kui kellaaeg on vigane, jätame vahele

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
else:
    st.warning("Ootan andmeid... Veendu, et Google Sheet on jagatud 'Anyone with the link'!")
