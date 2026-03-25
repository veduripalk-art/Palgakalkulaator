import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import calendar

# --- KONSTANDID ---
TUNNIHIND = 12.42
OHTULISA_PROTSENT = 0.20
OOLISA_PROTSENT = 0.40
KAHEPOOLNE_LISA = 0.20        # PARANDATUD: Ainult 20% kogu tuuri ulatuses
OPILASE_TASU_TUNNIS = 2.58
PAUSI_TASU_PROTSENT = 0.60
ULETUNNI_KOEFITSIENT = 1.5

KVALIFIKATSIOONID = {
    "Puudub": 0, "EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205
}

# --- ABIFUNKTSIOONID ---
def arvuta_ajad(algus_str, lopp_str):
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
            if tund >= 22 or tund < 6: oo_min += 1
            elif 18 <= tund < 22: ohtu_min += 1
            praegune += timedelta(minutes=1)
        return kokku_min / 60.0, ohtu_min / 60.0, oo_min / 60.0
    except:
        return 0.0, 0.0, 0.0

def sobib_paevaga(paev_str, weekday_idx):
    if pd.isna(paev_str) or str(paev_str).strip().lower() == 'default': return True
    mapping = {0:'E', 1:'T', 2:'K', 3:'N', 4:'R', 5:'L', 6:'P'}
    return mapping[weekday_idx] in str(paev_str).upper()

# --- RAKENDUS ---
st.set_page_config(page_title="Raudtee Kalkulaator", layout="wide")
st.title("🚂 Töötasu kalkulaator")

@st.cache_data
def lae_db():
    try:
        # Loeme Sinu andmebaasi
        df_db = pd.read_csv("parandatud tabel.csv", sep="\t")
        df_db['ALATES'] = pd.to_datetime(df_db['ALATES']).dt.date
        df_db['KUNI'] = pd.to_datetime(df_db['KUNI']).dt.date
        return df_db
    except Exception as e:
        st.error(f"Andmebaasi faili ei leitud või viga: {e}")
        return pd.DataFrame()

db = lae_db()

# 1. KALENDRI SEADED
st.sidebar.header("Kalender")
tana = datetime.now()
valitud_aasta = st.sidebar.selectbox("Aasta", [2025, 2026], index=1)
valitud_kuu = st.sidebar.selectbox("Kuu", list(range(1, 13)), index=tana.month-1)

_, viimane_paev = calendar.monthrange(valitud_aasta, valitud_kuu)
kuupaevad = [date(valitud_aasta, valitud_kuu, d) for d in range(1, viimane_paev + 1)]

# Tuuride valikunimekiri
if not db.empty:
    tuuride_valik = [""] + sorted(db['TUUR'].unique().astype(str).tolist()) + ["P", "TÕ", "KO", "KV"]
else:
    tuuride_valik = ["", "P", "TÕ", "KO", "KV"]

# 2. ÜLDISED LISAD
st.sidebar.markdown("---")
kval = st.sidebar.selectbox("Kvalifikatsioon", options=list(KVALIFIKATSIOONID.keys()))
norm_paevad = st.sidebar.number_input("Kuu norm tööpäevad", value=21)
kvartali_norm = st.sidebar.number_input("Kvartali normtunnid", value=480)

# 3. GRAAFIKU TABEL
st.subheader(f"📅 {valitud_kuu}.{valitud_aasta} Töögraafik")

if 'df_input' not in st.session_state or st.sidebar.button("Uuenda kalendri kuud"):
    st.session_state.df_input = pd.DataFrame({
        "Kuupäev": kuupaevad,
        "Tuuri Valik": [""] * len(kuupaevad),
        "Õpilane (Õ)": [False] * len(kuupaevad)
    })

muudetud_df = st.data_editor(
    st.session_state.df_input,
    column_config={
        "Kuupäev": st.column_config.DateColumn(disabled=True, format="DD.MM (dddd)"),
        "Tuuri Valik": st.column_config.SelectboxColumn("Vali Tuur", options=tuuride_valik, width="medium"),
        "Õpilane (Õ)": st.column_config.CheckboxColumn(width="small")
    },
    hide_index=True,
    use_container_width=True,
    key="editor"
)

# 4. ARVUTUSTE LOOGIKA
tulemused = []
kokku_tunnid, normi_vahendus, toopaevad_count = 0.0, 0, 0

for _, row in muudetud_df.iterrows():
    kp = row["Kuupäev"]
    kood = str(row["Tuuri Valik"])
    is_student = row["Õpilane (Õ)"]
    
    if not kood or kood == "": continue
    
    t, ohtu, oo, paus, split_tasu, opilane_tasu = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    leitud = False
    
    # Erikoodid
    if kood == "P":
        normi_vahendus += 8
        leitud = True
    elif kood in ["TÕ", "KO", "KV"]:
        t = {"TÕ": 2.0, "KO": 8.0, "KV": 4.0}[kood]
        toopaevad_count += 1
        leitud = True
    else:
        # Otsing andmebaasist
        otsing = db[(db['TUUR'].astype(str) == kood) & (db['ALATES'] <= kp) & (db['KUNI'] >= kp)]
        rida = next((r for _, r in otsing.iterrows() if sobib_paevaga(r['PAEV'], kp.weekday())), None)
        
        if rida is not None:
            leitud = True
            toopaevad_count += 1
            t_raw, o_h, oo_h = arvuta_ajad(rida['ALGUS'], rida['LOPP'])
            
            # 12h piirangu loogika
            if t_raw > 12:
                paus = t_raw - 12
                suhe = 12 / t_raw
                ohtu, oo, t = o_h * suhe, oo_h * suhe, 12.0
            else:
                ohtu, oo, t = o_h, oo_h, t_raw
            
            # Tasude arvutus
            pohitasu_baas = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
            
            # KONTROLL: Kas on kahepoolne tuur?
            if str(rida['SPLIT']).upper() == 'TRUE':
                split_tasu = pohitasu_baas * KAHEPOOLNE_LISA
            
            if is_student:
                opilane_tasu = (t + paus) * OPILASE_TASU_TUNNIS

    if leitud:
        p_tasu_rida = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
        o_tasu_rida = (ohtu * TUNNIHIND * OHTULISA_PROTSENT) + (oo * TUNNIHIND * OOLISA_PROTSENT)
        kokku_tunnid += (t + paus)
        
        tulemused.append({
            "Kuupäev": kp.strftime("%d.%m"),
            "Tuur": kood,
            "Tunnid": round(t+paus, 2),
            "Põhitasu": round(p_tasu_rida, 2),
            "Õhtu/Öö": round(o_tasu_rida, 2),
            "Split (20%)": round(split_tasu, 2),
            "Õpilane": round(opilane_tasu, 2),
            "Kokku": round(p_tasu_rida + o_tasu_rida + split_tasu + opilane_tasu, 2)
        })

# KOONDARVUTUSED
kval_summa = min(KVALIFIKATSIOONID[kval], (KVALIFIKATSIOONID[kval] / norm_paevad) * toopaevad_count) if norm_paevad > 0 else 0
uletunnid = max(0, kokku_tunnid - (kvartali_norm - normi_vahendus))
ut_tasu = uletunnid * TUNNIHIND * ULETUNNI_KOEFITSIENT

# 5. KUVAMINE
st.markdown("---")
if tulemused:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.dataframe(pd.DataFrame(tulemused), hide_index=True, use_container_width=True)
    with c2:
        df_summ = pd.DataFrame({
            "Kirjeldus": ["Põhitasu", "Õhtu/Öö lisad", "Kahepoolne tuur", "Õpilase tasu", "Kvalifikatsioon", "Ületunnid"],
            "Summa (€)": [
                sum(x['Põhitasu'] for x in tulemused),
                sum(x['Õhtu/Öö'] for x in tulemused),
                sum(x['Split (20%)'] for x in tulemused),
                sum(x['Õpilane'] for x in tulemused),
                kval_summa, ut_tasu
            ]
        })
        st.table(df_summ)
        st.success(f"**KOGUSUMMA: {round(df_summ['Summa (€)'].sum(), 2)} €**")
else:
    st.info("Tabel on tühi. Vali rippmenüüst tuurid.")
