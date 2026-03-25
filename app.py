import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- KONSTANDID ---
TUNNIHIND = 12.42
OHTULISA_PROTSENT = 0.20
OOLISA_PROTSENT = 0.40
KAHEPOOLNE_LISA_KOKKU = 0.40  # 20% (puhkeaja tasu)
OPILASE_TASU_TUNNIS = 2.58
PAUSI_TASU_PROTSENT = 0.60
ULETUNNI_KOEFITSIENT = 1.5

KVALIFIKATSIOONID = {
    "Puudub": 0,
    "EMU/DMU": 140,
    "EMU+DMU": 165,
    "EMU+DMU+SKODA": 205
}

def arvuta_ajad(algus_dt, lopp_dt):
    """Arvutab vahemikus olevad õhtu- ja öötunnid."""
    if pd.isnull(algus_dt) or pd.isnull(lopp_dt):
        return 0, 0, 0
    
    if lopp_dt < algus_dt:
        lopp_dt += timedelta(days=1)
        
    kokku_min = int((lopp_dt - algus_dt).total_seconds() / 60)
    ohtu_min = 0
    oo_min = 0
    
    praegune = algus_dt
    for _ in range(kokku_min):
        tund = praegune.hour
        if tund >= 22 or tund < 6:
            oo_min += 1
        elif 18 <= tund < 22:
            ohtu_min += 1
        praegune += timedelta(minutes=1)
        
    return kokku_min / 60.0, ohtu_min / 60.0, oo_min / 60.0

def sobib_paevaga(paev_str, weekday_idx):
    if pd.isna(paev_str) or str(paev_str).strip().lower() == 'default':
        return True
    mapping = {0:'E', 1:'T', 2:'K', 3:'N', 4:'R', 5:'L', 6:'P'}
    return mapping[weekday_idx] in str(paev_str).upper()

# --- RAKENDUS ---
st.set_page_config(page_title="Raudtee Palgakalkulaator", layout="wide")
st.title("🚂 Töötasu kalkulaator (Uuendatud puhkeaja tasuga)")

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

# Külgriba seaded
st.sidebar.header("Seaded")
kval = st.sidebar.selectbox("Kvalifikatsioon", options=list(KVALIFIKATSIOONID.keys()))
norm_paevad = st.sidebar.number_input("Kuu norm tööpäevad", value=21)
kvartali_norm = st.sidebar.number_input("Kvartali normtunnid", value=480)

st.sidebar.subheader("Manuaalne korrektsioon")
korr_kp = st.sidebar.date_input("Vali kuupäev")
korr_min = st.sidebar.number_input("Minutid (+/-)", value=0, step=15)

# Graafiku sisestamine
st.subheader("Sisesta oma graafik")
if 'graafik' not in st.session_state:
    st.session_state.graafik = pd.DataFrame({"Kuupäev": [datetime.now().date()], "Tuur": [""], "Õpilane (Õ)": [False]})

editor_df = st.data_editor(st.session_state.graafik, num_rows="dynamic", use_container_width=True)

# ARVUTUS
tulemused = []
kokku_tunnid = 0
normi_vahendus = 0
toopaevad = 0

for _, row in editor_df.iterrows():
    kp = row["Kuupäev"]
    kood = str(row["Tuur"]).strip().upper()
    is_student = row["Õpilane (Õ)"]
    
    if not kood or pd.isna(kp): continue
    
    t, ohtu, oo, paus, split_tasu, opilane_tasu = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    leitud = False
    
    if kood == "P":
        normi_vahendus += 8
        leitud = True
    elif kood in ["TÕ", "KO", "KV"]:
        t = {"TÕ": 2.0, "KO": 8.0, "KV": 4.0}[kood]
        toopaevad += 1
        leitud = True
    else:
        otsing = db[(db['TUUR'].astype(str).str.upper() == kood) & (db['ALATES'] <= kp) & (db['KUNI'] >= kp)]
        rida = next((r for _, r in otsing.iterrows() if sobib_paevaga(r['PAEV'], kp.weekday())), None)
        
        if rida is not None:
            leitud = True
            t_raw, ohtu, oo = arvuta_ajad(datetime.strptime(rida['ALGUS'], "%H:%M"), datetime.strptime(rida['LOPP'], "%H:%M"))
            toopaevad += 1
            
            # Üle 12h loogika
            if t_raw > 12:
                paus = t_raw - 12
                # Proportsionaalne õhtu/öö vähendus, et mitte maksta üle 12h eest lisasid
                suhe = 12 / t_raw
                ohtu *= suhe
                oo *= suhe
                t = 12.0
            else:
                t = t_raw
            
            # Lisade arvutus
            pohitasu_baas = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
            
            if rida['SPLIT'] == True:
                # 20% kahepoolne tuur + 20% puhkeaja tasu = 40% (KAHEPOOLNE_LISA_KOKKU)
                split_tasu = pohitasu_baas * KAHEPOOLNE_LISA_KOKKU
            
            if is_student:
                opilane_tasu = (t + paus) * OPILASE_TASU_TUNNIS

    # Manuaalne lisa
    if kp == korr_kp: t += (korr_min / 60.0)

    if leitud:
        p_tasu = (t * TUNNIHIND) + (paus * TUNNIHIND * PAUSI_TASU_PROTSENT)
        o_tasu = ohtu * TUNNIHIND * OHTULISA_PROTSENT
        oo_tasu = oo * TUNNIHIND * OOLISA_PROTSENT
        
        kokku_tunnid += (t + paus)
        tulemused.append({
            "Kuupäev": kp, "Tuur": kood, "Tunnid": round(t+paus, 2),
            "Põhitasu": round(p_tasu, 2), "Õhtu/Öö": round(o_tasu + oo_tasu, 2),
            "Split+Puhke (+40%)": round(split_tasu, 2), "Õpilane": round(opilane_tasu, 2),
            "Kokku": round(p_tasu + o_tasu + oo_tasu + split_tasu + opilane_tasu, 2)
        })

# Lõpparvutused
kval_summa = min(KVALIFIKATSIOONID[kval], (KVALIFIKATSIOONID[kval] / norm_paevad) * toopaevad) if norm_paevad > 0 else 0
uletunnid = max(0, kokku_tunnid - (kvartali_norm - normi_vahendus))
ut_tasu = uletunnid * TUNNIHIND * ULETUNNI_KOEFITSIENT

st.dataframe(pd.DataFrame(tulemused), use_container_width=True)

# Kokkuvõtte tabel
st.subheader("Tasude koond")
df_summary = pd.DataFrame({
    "Kirjeldus": ["Põhitasu", "Õhtu/Öö lisad", "Split + Puhkeaja tasu", "Õpilase tasu", "Kvalifikatsioon", "Ületunnid"],
    "Summa (€)": [
        sum(x['Põhitasu'] for x in tulemused),
        sum(x['Õhtu/Öö'] for x in tulemused),
        sum(x['Split+Puhke (+40%)'] for x in tulemused),
        sum(x['Õpilane'] for x in tulemused),
        kval_summa,
        ut_tasu
    ]
})
st.table(df_summary)
st.success(f"**Kogu Bruto: {round(df_summary['Summa (€)'].sum(), 2)} €**")
