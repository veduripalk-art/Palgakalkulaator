import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import calendar

# --- KONSTANDID ---
TUNNIHIND = 12.42
OHTULISA_PROTSENT = 0.20
OOLISA_PROTSENT = 0.40
KAHEPOOLNE_LISA_PROTSENT = 0.20 # Tuuri lisa
PUHKE_LISA_PROTSENT = 0.20      # Puhkeaja tasu lisa
OPILASE_TASU_TUNNIS = 2.58
PAUSI_TASU_PROTSENT = 0.60
ULETUNNI_KOEFITSIENT = 1.5

KVALIFIKATSIOONID = {
    "Puudub": 0, "EMU/DMU": 140, "EMU+DMU": 165, "EMU+DMU+SKODA": 205
}

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

st.set_page_config(page_title="Raudtee Kalkulaator", layout="wide")
st.title("🚂 Töötasu kalkulaator")

@st.cache_data
def lae_db():
    try:
        df_db = pd.read_csv("parandatud tabel.csv", sep="\t")
        df_db['ALATES'] = pd.to_datetime(df_db['ALATES']).dt.date
        df_db['KUNI'] = pd.to_datetime(df_db['KUNI']).dt.date
        return df_db
    except:
        return pd.DataFrame()

db = lae_db()

# --- SEADED ---
st.sidebar.header("Seaded")
valitud_aasta = st.sidebar.selectbox("Aasta", [2025, 2026], index=1)
valitud_kuu = st.sidebar.selectbox("Kuu", list(range(1, 13)), index=datetime.now().month-1)
kval = st.sidebar.selectbox("Kvalifikatsioon", options=list(KVALIFIKATSIOONID.keys()))
norm_paevad = st.sidebar.number_input("Kuu norm tööpäevad", value=21)
kvartali_norm = st.sidebar.number_input("Kvartali normtunnid", value=480)

_, viimane_paev = calendar.monthrange(valitud_aasta, valitud_kuu)
kuupaevad = [date(valitud_aasta, valitud_kuu, d) for d in range(1, viimane_paev + 1)]
tuuride_valik = [""] + sorted(db['TUUR'].unique().astype(str).tolist()) + ["P", "TÕ", "KO", "KV"]

if 'df_input' not in st.session_state or st.sidebar.button("Uuenda kalender"):
    st.session_state.df_input = pd.DataFrame({
        "Kuupäev": kuupaevad, "Tuur": [""] * len(kuupaevad),
        "Lisa min": [0] * len(kuupaevad), "Õpilane (Õ)": [False] * len(kuupaevad)
    })

muudetud_df = st.data_editor(st.session_state.df_input, column_config={
    "Kuupäev": st.column_config.DateColumn(disabled=True, format="DD.MM (dddd)"),
    "Tuur": st.column_config.SelectboxColumn("Tuur", options=tuuride_valik),
    "Lisa min": st.column_config.NumberColumn("Lisa min", step=1)
}, hide_index=True, use_container_width=True)

# --- ARVUTUS ---
tulemused = []
kokku_tunnid, normi_vahendus, toopaevad_count = 0.0, 0, 0

for _, row in muudetud_df.iterrows():
    kp, kood, lisa_min, is_student = row["Kuupäev"], str(row["Tuur"]), row["Lisa min"], row["Õpilane (Õ)"]
    if not kood or kood == "": continue
    
    t, ohtu, oo, paus, split_lisa, puhke_lisa, opilane_tasu = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    leitud = False
    
    if kood == "P": normi_vahendus += 8; leitud = True
    elif kood in ["TÕ", "KO", "KV"]:
        t = {"TÕ": 2.0, "KO": 8.0, "KV": 4.0}[kood]; toopaevad_count += 1; leitud = True
    else:
        otsing = db[(db['TUUR'].astype(str) == kood) & (db['ALATES'] <= kp) & (db['KUNI'] >= kp)]
        rida = next((r for _, r in otsing.iterrows() if sobib_paevaga(r['PAEV'], kp.weekday())), None)
        if rida is not None:
            leitud = True; toopaevad_count += 1
            t_raw, o_h, oo_h = arvuta_ajad(rida['ALGUS'], rida['LOPP'])
            if t_raw > 12:
                paus = t_raw - 12; suhe = 12 / t_raw
                ohtu, oo, t = o_h * suhe, oo_h * suhe, 12.0
            else:
                ohtu, oo, t = o_h, oo_h, t_raw
            
            # KONTROLL: Ainult SPLIT tuuridele kehtivad lisad
            if str(rida['SPLIT']).upper() == 'TRUE':
                pohitasu_baas = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
                split_lisa = pohitasu_baas * KAHEPOOLNE_LISA_PROTSENT
                puhke_lisa = (t + paus) * TUNNIHIND * PUHKE_LISA_PROTSENT # Algusest lõpuni 20%
            
            if is_student: opilane_tasu = (t + paus) * OPILASE_TASU_TUNNIS

    t += (lisa_min / 60.0)
    if leitud:
        p_tasu = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
        oo_ohtu = (ohtu * TUNNIHIND * OHTULISA_PROTSENT) + (oo * TUNNIHIND * OOLISA_PROTSENT)
        kokku_tunnid += (t + paus)
        tulemused.append({
            "KP": kp.strftime("%d.%m"), "Tuur": kood, "Tunnid": round(t+paus, 2),
            "Põhitasu": p_tasu, "Õhtu/Öö": oo_ohtu, "Split": split_lisa, 
            "Puhke": puhke_lisa, "Õpilane": opilane_tasu
        })

# --- KOKKUVÕTE ---
st.markdown("---")
if tulemused:
    res_df = pd.DataFrame(tulemused)
    c1, c2 = st.columns([2, 1])
    with c1: st.dataframe(res_df, hide_index=True, use_container_width=True)
    with c2:
        kval_tasu = min(KVALIFIKATSIOONID[kval], (KVALIFIKATSIOONID[kval]/norm_paevad)*toopaevad_count) if norm_paevad > 0 else 0
        ut = max(0, kokku_tunnid - (kvartali_norm - normi_vahendus))
        
        df_summ = pd.DataFrame({
            "Liik": ["Põhitasu", "Õhtu/Öö", "Split-tuur", "Puhkeaja tasu", "Õpilane", "Kvalifikatsioon", "Ületunnid"],
            "Summa (€)": [
                res_df["Põhitasu"].sum(), res_df["Õhtu/Öö"].sum(), res_df["Split"].sum(),
                res_df["Puhke"].sum(), res_df["Õpilane"].sum(), kval_tasu, ut * TUNNIHIND * 1.5
            ]
        })
        st.table(df_summ.assign(Summa=df_summ["Summa (€)"].round(2))[["Liik", "Summa"]])
        st.success(f"**KOGUSUMMA: {round(df_summ['Summa (€)'].sum(), 2)} €**")
