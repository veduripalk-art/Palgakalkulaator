import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import calendar

# --- KONSTANDID ---
TUNNIHIND = 12.42
OHTULISA_PROTSENT = 0.20
OOLISA_PROTSENT = 0.40
KAHEPOOLNE_LISA = 0.20
OPILASE_TASU_TUNNIS = 2.58
PAUSI_TASU_PROTSENT = 0.60

KVALIFIKATSIOONID = {
    "Puudub": 0, 
    "EMU/DMU": 140, 
    "EMU+DMU": 165, 
    "EMU+DMU+SKODA": 205
}

SHEET_ID = "1cUzXOh1EB8XH3nzm78C4TRgzDv26twRF_kLVS7pRujU"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- ABIFUNKTSIOONID ---
def arvuta_ajad(algus_str, lopp_str):
    """Arvutab töötunnid minuti kaupa ja eraldab õhtu- ning öötunnid."""
    try:
        algus_dt = datetime.strptime(str(algus_str).strip(), "%H:%M")
        lopp_dt = datetime.strptime(str(lopp_str).strip(), "%H:%M")
        if lopp_dt <= algus_dt:
            lopp_dt += timedelta(days=1)
        
        kokku_min = int((lopp_dt - algus_dt).total_seconds() / 60)
        ohtu_min, oo_min = 0, 0
        praegune = algus_dt
        
        for _ in range(kokku_min):
            tund = praegune.hour
            if tund >= 22 or tund < 6: 
                oo_min += 1
            elif 18 <= tund < 22: 
                ohtu_min += 1
            praegune += timedelta(minutes=1)
            
        return kokku_min / 60.0, ohtu_min / 60.0, oo_min / 60.0
    except:
        return 0.0, 0.0, 0.0

@st.cache_data(ttl=600) # Uuendab andmeid iga 10 minuti tagant
def lae_andmebaas():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"Viga Google Sheetsi lugemisel. Kas tabel on avalik (Anyone with link)? Viga: {e}")
        return pd.DataFrame()

# --- RAKENDUS ---
st.set_page_config(page_title="Raudtee Kalkulaator", layout="wide")
st.title("🚂 Töötasu Kalkulaator")

db = lae_andmebaas()

# 1. KÜLGRIBA: SEADED JA MANUAALNE KORREKTSIOON
st.sidebar.header("🗓️ Perioodi Seaded")
valitud_aasta = st.sidebar.selectbox("Aasta", [2025, 2026], index=1)
valitud_kuu = st.sidebar.selectbox("Kuu", list(range(1, 13)), index=datetime.now().month-1)

st.sidebar.markdown("---")
st.sidebar.header("💶 Üldised seaded")
kval = st.sidebar.selectbox("Kvalifikatsioon", options=list(KVALIFIKATSIOONID.keys()))
norm_paevad = st.sidebar.number_input("Kuu norm tööpäevad", value=21, min_value=1)

st.sidebar.markdown("---")
st.sidebar.header("⏱️ Kvartali Ületunnid")
st.sidebar.info("Q1: Jaan-Märts | Q2: Apr-Juuni jne.")
kvartali_norm = st.sidebar.number_input("Kvartali normtunnid kokku", value=480, step=8)
eelmiste_kuude_tunnid = st.sidebar.number_input("Samas kvartalis JUBa tehtud tunnid", value=0.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("✏️ Manuaalne minutite muudatus")
korr_kp = st.sidebar.date_input("Vali kuupäev, kuhu minuteid lisada/eemaldada")
korr_min = st.sidebar.number_input("Minutid (+/-)", value=0, step=1)

# 2. GRAAFIKU TABELI GENEREERIMINE
_, viimane_paev = calendar.monthrange(valitud_aasta, valitud_kuu)
kuupaevad = [date(valitud_aasta, valitud_kuu, d) for d in range(1, viimane_paev + 1)]

# Tuuride valik (Otsib DB-st kõik unikaalsed tuurid, lisab erikoodid)
if not db.empty and 'TUUR' in db.columns:
    tuuride_valik = [""] + sorted(db['TUUR'].dropna().astype(str).unique().tolist()) + ["P", "TÕ", "KO", "KV"]
else:
    tuuride_valik = ["", "P", "TÕ", "KO", "KV"]

st.subheader(f"Töögraafik: {valitud_kuu}.{valitud_aasta}")

if 'df_input' not in st.session_state or st.button("Uuenda kalendrit uue kuu jaoks"):
    st.session_state.df_input = pd.DataFrame({
        "Kuupäev": kuupaevad,
        "Tuur": [""] * len(kuupaevad),
        "Õpilane (Õ)": [False] * len(kuupaevad)
    })

muudetud_df = st.data_editor(
    st.session_state.df_input,
    column_config={
        "Kuupäev": st.column_config.DateColumn(disabled=True, format="DD.MM.YYYY"),
        "Tuur": st.column_config.SelectboxColumn("Vali Tuur", options=tuuride_valik, width="medium"),
        "Õpilane (Õ)": st.column_config.CheckboxColumn("Õpilane")
    },
    hide_index=True,
    use_container_width=True
)

# 3. ARVUTUSTE LOOGIKA
tulemused = []
kokku_tunnid = 0.0
normist_maha = 0
toopaevad_count = 0

for _, row in muudetud_df.iterrows():
    kp = row["Kuupäev"]
    kood = str(row["Tuur"]).strip().upper()
    is_student = row["Õpilane (Õ)"]
    
    if not kood or kood == "": 
        continue
    
    t, ohtu, oo, paus, split_tasu, opilane_tasu = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    leitud = False
    on_kahepoolne = "/" in kood  # Loogika: kahepoolne on see, millel on "/1" või "/2"
    
    # Erikoodid
    if kood == "P":
        normist_maha += 8
        leitud = True
    elif kood in ["TÕ", "KO", "KV"]:
        t = {"TÕ": 2.0, "KO": 8.0, "KV": 4.0}[kood]
        toopaevad_count += 1
        leitud = True
    else:
        # Otsime tuuri DB-st (eeldab veergusid TUUR, ALGUS, LOPP)
        if not db.empty:
            otsing = db[db['TUUR'].astype(str).str.upper() == kood]
            if not otsing.empty:
                rida = otsing.iloc[0]
                leitud = True
                toopaevad_count += 1
                t_raw, o_h, oo_h = arvuta_ajad(rida['ALGUS'], rida['LOPP'])
                
                # 12h piirangu loogika (tasustatud paus 60%)
                if t_raw > 12:
                    paus = t_raw - 12
                    suhe = 12 / t_raw
                    ohtu, oo, t = o_h * suhe, oo_h * suhe, 12.0
                else:
                    ohtu, oo, t = o_h, oo_h, t_raw
                
                # Rahalised väärtused põhitasu osas
                pohitasu_baas = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
                
                # Kahepoolse tuuri lisa (20%) - ainult kui koodis on "/"
                if on_kahepoolne:
                    split_tasu = pohitasu_baas * KAHEPOOLNE_LISA
                
                # Õpilase tasu tervele tuurile
                if is_student:
                    opilane_tasu = (t + paus) * OPILASE_TASU_TUNNIS

    # Manuaalne minutite lisamine vastavale kuupäevale
    if kp == korr_kp and leitud:
        t += (korr_min / 60.0)

    # Kui rida on kehtiv, salvestame tulemuse
    if leitud:
        p_tasu_rida = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
        o_tasu_rida = (ohtu * TUNNIHIND * OHTULISA_PROTSENT) + (oo * TUNNIHIND * OOLISA_PROTSENT)
        kokku_tunnid += (t + paus)
        
        tulemused.append({
            "Kuupäev": kp.strftime("%d.%m"),
            "Tuur": kood,
            "Tunde": round(t + paus, 2),
            "Põhitasu+Paus": round(p_tasu_rida, 2),
            "Õhtu/Öö": round(o_tasu_rida, 2),
            "Split (20%)": round(split_tasu, 2),
            "Õpilane": round(opilane_tasu, 2),
            "Päev Kokku": round(p_tasu_rida + o_tasu_rida + split_tasu + opilane_tasu, 2)
        })

# 4. KOKKUVÕTE JA ÜLETUNNID
st.markdown("---")
st.subheader("📊 Arvutuskäik ja tulemused")

if tulemused:
    res_df = pd.DataFrame(tulemused)
    st.dataframe(res_df, hide_index=True, use_container_width=True)
    
    # Kvalifikatsioonitasu arvutus
    baas_kval = KVALIFIKATSIOONID[kval]
    kval_summa = min(baas_kval, (baas_kval / norm_paevad) * toopaevad_count) if norm_paevad > 0 else 0
    
    # Kvartali ületundide arvutus
    kvartali_tegelik_norm = kvartali_norm - normist_maha
    kvartali_kokku_tehtud = kokku_tunnid + eelmiste_kuude_tunnid
    uletunnid_h = max(0, kvartali_kokku_tehtud - kvartali_tegelik_norm)
    uletundide_tasu = uletunnid_h * TUNNIHIND * 1.5

    # Koondtabeli kuvamine
    st.subheader("💰 Koondkokkuvõte")
    df_summ = pd.DataFrame({
        "Tasuliik": [
            "1. Põhitasu (sh >12h pausid)", 
            "2. Õhtu- ja öölisad", 
            "3. Kahepoolne tuur (Split 20%)", 
            "4. Õpilase juhendamine", 
            "5. Kvalifikatsioonitasu", 
            f"6. Kvartali ületunnid ({round(uletunnid_h, 2)} h)"
        ],
        "Summa (€)": [
            res_df['Põhitasu+Paus'].sum(),
            res_df['Õhtu/Öö'].sum(),
            res_df['Split (20%)'].sum(),
            res_df['Õpilane'].sum(),
            kval_summa,
            uletundide_tasu
        ]
    })
    
    df_summ['Summa (€)'] = df_summ['Summa (€)'].round(2)
    st.table(df_summ)
    
    kogusumma = round(df_summ['Summa (€)'].sum(), 2)
    st.success(f"**HINNANGULINE KOGUSUMMA (BRUTO): {kogusumma} €**")
    
else:
    st.info("Palun täida töögraafik (vali tuurid), et näha tulemusi.")
