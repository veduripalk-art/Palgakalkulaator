import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS ---
st.set_page_config(page_title="Vedurijuhi Kalkulaator PRO", layout="wide")

# Sinu uus tabeli ID
SHEET_ID = "1cUzXOh1EB8XH3nzm78C4TRgzDv26twRF_kLVS7pRujU"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Konstandid
KVAL_LISA = {"EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205}
OPILASE_TUNNITASU = 2.83 

if 'minutid' not in st.session_state:
    st.session_state.minutid = {}

# --- 2. ANDMETE LAADIMINE JA PUHASTAMINE ---
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # Puhastame veergude nimed
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Puhastame andmed tühikutest
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.strip()
        
        # Teisendame kuupäevad arvutile arusaadavaks
        df['ALATES_DT'] = pd.to_datetime(df['ALATES'], errors='coerce')
        df['KUNI_DT'] = pd.to_datetime(df['KUNI'], errors='coerce')
        
        return df.dropna(subset=['TUUR'])
    except Exception as e:
        st.error(f"Viga tabeli lugemisel: {e}")
        return None

def get_matching_rows(df, tuur_nimi, valitud_kp):
    # 1. Filtreerime nime järgi
    potentsiaalsed = df[df['TUUR'] == tuur_nimi]
    if potentsiaalsed.empty: return None
    
    # 2. Filtreerime kuupäeva vahemiku järgi (ALATES/KUNI)
    # See tagab, et märtsis võetakse vana graafik ja aprillis uus
    match_periood = potentsiaalsed[
        (potentsiaalsed['ALATES_DT'] <= pd.Timestamp(valitud_kp)) & 
        (potentsiaalsed['KUNI_DT'] >= pd.Timestamp(valitud_kp))
    ]
    
    if match_periood.empty:
        # Kui perioodi ei klapi, proovime leida rida, kus kuupäevad on tühjad (igavene tuur)
        match_periood = potentsiaalsed[potentsiaalsed['ALATES'].isna()]
    
    if match_periood.empty: return None

    # 3. Filtreerime päeva tähise järgi (ER, LP, default jne)
    wd = valitud_kp.weekday() # 0=E, 6=P
    sobivad_tahised = ["DEFAULT"]
    if wd <= 4: sobivad_tahised.append("ER")
    if wd >= 5: sobivad_tahised.append("LP")
    if wd == 4: sobivad_tahised.append("R")
    if wd <= 3: sobivad_tahised.append("E-N")

    # Otsime kõige täpsemat vastet (tähis vs default)
    match_periood['PAEV_UP'] = match_periood['PAEV'].str.upper()
    for tahis in reversed(sobivad_tahised):
        lopp_valik = match_periood[match_periood['PAEV_UP'] == tahis]
        if not lopp_valik.empty:
            return lopp_valik.iloc[0]
            
    return match_periood.iloc[0]

# --- 3. SIDEBAR (SEADED) ---
with st.sidebar:
    st.header("⚙️ Üldseaded")
    baaspalk = st.number_input("Baastasu (€/h)", value=12.42)
    kval = st.selectbox("Kvalifikatsioon", options=list(KVAL_LISA.keys()))
    norm_kuu = st.number_input("Kuu normtunnid", value=168.0)
    
    st.divider()
    valitud_kuu_nimi = st.selectbox("Vali kuu", ["Märts", "Aprill", "Mai", "Juuni"])
    kuu_numbrid = {"Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_numbrid[valitud_kuu_nimi]
    
    st.header("⏳ Lisa minutid")
    paeva_valik = st.number_input("Kuupäev", min_value=1, max_value=31, value=1)
    lisa_min = st.number_input("Minutid (+/-)", value=0, step=5)
    if st.button("Salvesta lisaminutid"):
        st.session_state.minutid[f"{paeva_valik}.{k_num}"] = lisa_min
        st.toast(f"Päevale {paeva_valik} lisatud {lisa_min} min")

# --- 4. PEALINE TÖÖLAUD ---
df = load_data()

if df is not None:
    st.title(f"🚂 {valitud_kuu_nimi} 2026")
    
    # Arvutame kuu päevade arvu
    if k_num == 12: next_m = 1; next_y = 2027
    else: next_m = k_num + 1; next_y = 2026
    paevi_kuus = (datetime(next_y, next_m, 1) - timedelta(days=1)).day
    
    graafik_andmed = []
    nadalapaevad = ["E", "T", "K", "N", "R", "L", "P"]
    
    # Tuuride nimekiri (EMU, DMU, UNI kõik koos)
    koik_tuurid = sorted(df['TUUR'].unique().tolist())
    
    cols = st.columns(7)
    
    for i in range(1, paevi_kuus + 1):
        dt = datetime(2026, k_num, i)
        n_p_nimi = nadalapaevad[dt.weekday()]
        lisa = st.session_state.minutid.get(f"{i}.{k_num}", 0)
        
        with cols[(i-1)%7]:
            st.write(f"**{n_p_nimi} {i:02d}.{k_num:02d}**")
            t_valik = st.selectbox("Vali", ["-", "P", "KO"] + koik_tuurid, key=f"t{i}", label_visibility="collapsed")
            opilane = st.checkbox("Õp", key=f"s{i}")
            
            tunnid, tasu, nv_tunnid, work = 0.0, 0.0, 0.0, False
            viga = ""
            
            if t_valik == "P":
                nv_tunnid = 8.0
            elif t_valik == "KO":
                tunnid = 8.0
                tasu = 8.0 * baaspalk
                work = True
            elif t_valik != "-":
                rida = get_matching_rows(df, t_valik, dt)
                if rida is not None:
                    try:
                        # Kellaaja töötlemine
                        s_str = str(rida['ALGUS']).replace('.', ':').replace(',', ':')
                        e_str = str(rida['LOPP']).replace('.', ':').replace(',', ':')
                        s_dt = datetime.strptime(s_str, "%H:%M")
                        e_dt = datetime.strptime(e_str, "%H:%M")
                        if e_dt <= s_dt: e_dt += timedelta(days=1)
                        
                        tunnid = ((e_dt - s_dt).total_seconds() / 3600) + (lisa / 60)
                        kordaja = 1.2 if str(rida['SPLIT']).upper() == "TRUE" else 1.0
                        
                        tasu = (tunnid * baaspalk * kordaja)
                        if opilane: tasu += (tunnid * OPILASE_TUNNITASU)
                        work = True
                    except:
                        viga = "Kellaaja viga!"
                else:
                    viga = "Periood puudub!"
            
            if viga: st.caption(f":red[{viga}]")
            elif tunnid > 0: st.caption(f"{tunnid:.2f}h | {tasu:.1f}€")
            
            graafik_andmed.append({"t": tunnid, "r": tasu, "nv": nv_tunnid, "work": work})

    # --- KOKKUVÕTE ---
    res = pd.DataFrame(graafik_andmed)
    kokku_t = res["t"].sum()
    tegelik_norm = norm_kuu - res["nv"].sum()
    uletunnid = max(0, kokku_t - tegelik_norm)
    toopaevi = res[res["work"] == True].shape[0]
    
    # Kvalifikatsiooni tasu proportsionaalselt tööpäevadega
    kval_euro = min((toopaevi / 22) * KVAL_LISA[kval], KVAL_LISA[kval])
    
    uletunni_tasu = uletunnid * baaspalk * 0.5
    bruto = res["r"].sum() + kval_euro + uletunni_tasu
    
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Töötunnid kokku", f"{kokku_t:.2f} h")
    c2.metric("Normi täitmine", f"{tegelik_norm:.1f} h")
    c3.metric("Ületunnid", f"{uletunnid:.2f} h")
    c4.metric("Kval. tasu", f"{kval_euro:.2f} €")
    
    st.success(f"## 💰 Prognoositav Bruto: {bruto:.2f} €")
