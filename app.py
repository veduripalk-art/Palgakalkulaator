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

@st.cache_data(ttl=600)
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
st.sidebar.header("✏️ Manuaalne minutite muudatus")
korr_kp = st.sidebar.date_input("Vali kuupäev, kuhu minuteid lisada/eemaldada")
korr_min = st.sidebar.number_input("Minutid (+/-)", value=0, step=1)

# 2. GRAAFIKU TABELI GENEREERIMINE
_, viimane_paev = calendar.monthrange(valitud_aasta, valitud_kuu)
kuupaevad = [date(valitud_aasta, valitud_kuu, d) for d in range(1, viimane_paev + 1)]

if not db.empty and 'TUUR' in db.columns:
    tuuride_valik = [""] + sorted(db['TUUR'].dropna().astype(str).unique().tolist()) + ["P", "TÕ", "KO", "KV"]
else:
    tuuride_valik = ["", "P", "TÕ", "KO", "KV"]

st.subheader(f"Töögraafik: {valitud_kuu}.{valitud_aasta}")

if 'df_input' not in st.session_state or st.button("Uuenda kalendrit uue kuu jaoks"):
    st.session_state.df_input = pd.DataFrame({
        "Kuupäev": kuupaevad,
        "Tuur": [""] * len(kuupaevad),
        "Õpilane (Õ)": [False] * len(kuupaevad),
        "Riigipüha": [False] * len(kuupaevad) # Uus veerg pühade jaoks
    })

muudetud_df = st.data_editor(
    st.session_state.df_input,
    column_config={
        "Kuupäev": st.column_config.DateColumn(disabled=True, format="DD.MM.YYYY"),
        "Tuur": st.column_config.SelectboxColumn("Vali Tuur", options=tuuride_valik, width="medium"),
        "Õpilane (Õ)": st.column_config.CheckboxColumn("Õpilane"),
        "Riigipüha": st.column_config.CheckboxColumn("Riigipüha (2x baas)")
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
    is_holiday = row["Riigipüha"]
    
    if not kood or kood == "": 
        continue
    
    t_span, ohtu_h, oo_h, t_work, paus_h = 0.0, 0.0, 0.0, 0.0, 0.0
    p_tasu_rida, o_tasu_rida, split_tasu, opilane_tasu = 0.0, 0.0, 0.0, 0.0
    leitud = False
    on_kahepoolne = "/" in kood  
    
    # Erikoodid
    if kood == "P":
        normist_maha += 8
        leitud = True
    elif kood in ["TÕ", "KO", "KV"]:
        t_work = {"TÕ": 2.0, "KO": 8.0, "KV": 4.0}[kood]
        toopaevad_count += 1
        leitud = True
        if kp == korr_kp: t_work += (korr_min / 60.0)
        aktiivne_too = t_work
        baas_kordaja = 2.0 if is_holiday else 1.0
        p_tasu_rida = aktiivne_too * TUNNIHIND * baas_kordaja
        
    else:
        # Otsime tuuri DB-st
        if not db.empty:
            otsing = db[db['TUUR'].astype(str).str.upper() == kood]
            if not otsing.empty:
                rida = otsing.iloc[0]
                leitud = True
                toopaevad_count += 1
                
                # t_span on KOGU aeg algusest lõpuni (sh paus kahe osa vahel)
                t_span, ohtu_h, oo_h = arvuta_ajad(rida['ALGUS'], rida['LOPP'])
                
               # KRIITILINE: Reaalsed töötunnid (vaja õpilase ja põhitasu jaoks)
                if 'TÖÖTUNNID' in db.columns and pd.notna(rida['TÖÖTUNNID']) and str(rida['TÖÖTUNNID']).strip() != "":
                    try:
                        # Puhastame teksti: asendame komad punktidega ja eemaldame tühikud
                        puhas_vaartus = str(rida['TÖÖTUNNID']).strip().replace(',', '.')
                        t_work = float(puhas_vaartus)
                    except ValueError:
                        # Kui lahtris on mingi tekst, mida ei saa numbriks teha, kasutame kogu aega
                        t_work = t_span
                else:
                    t_work = t_span

                # Manuaalne korrektsioon töötundidele
                if kp == korr_kp:
                    t_work += (korr_min / 60.0)
                
                # 12h piirangu loogika (Rakendub AINULT töötundidele)
                aktiivne_too = min(t_work, 12.0)
                paus_h = max(0.0, t_work - 12.0)
                
                # Riigipüha loogika (Kordaja 2.0 ainult 12.42 baasile)
                baas_kordaja = 2.0 if is_holiday else 1.0
                
                # PÕHITASU + >12h PAUSITASU
                p_tasu_rida = (aktiivne_too * TUNNIHIND * baas_kordaja) + (paus_h * TUNNIHIND * PAUSI_TASU_PROTSENT)
                
                # LISAD (Arvutatakse alati tavalise TUNNIHIND (12.42) baasil)
                o_tasu_rida = (ohtu_h * TUNNIHIND * OHTULISA_PROTSENT) + (oo_h * TUNNIHIND * OOLISA_PROTSENT)
                
                # KAHEPOOLNE LISATASU (20% kehtib kogu SPAN'ile alates 1. osa algusest kuni 2. osa lõpuni)
                if on_kahepoolne:
                    split_tasu = t_span * TUNNIHIND * KAHEPOOLNE_LISA
                
                # ÕPILASE TASU (Rakendub ainult reaalsetele TÖÖTUNDIDELE, mitte vahepausile)
                if is_student:
                    opilane_tasu = t_work * OPILASE_TASU_TUNNIS

    if leitud:
        kokku_tunnid += t_work
        tulemused.append({
            "Kuupäev": kp.strftime("%d.%m"),
            "Tuur": kood,
            "Tunde": round(t_work, 2),
            "Põhitasu+Paus": round(p_tasu_rida, 2),
            "Õhtu/Öö": round(o_tasu_rida, 2),
            "Split (20%)": round(split_tasu, 2),
            "Õpilane": round(opilane_tasu, 2),
            "Päev Kokku": round(p_tasu_rida + o_tasu_rida + split_tasu + opilane_tasu, 2)
        })

# 4. KOKKUVÕTE
st.markdown("---")
st.subheader("📊 Arvutuskäik ja tulemused")

if tulemused:
    res_df = pd.DataFrame(tulemused)
    st.dataframe(res_df, hide_index=True, use_container_width=True)
    
    # Kvalifikatsioonitasu arvutus (arvestab haiguspäevadega automaatselt läbi töötatud päevade)
    baas_kval = KVALIFIKATSIOONID[kval]
    kval_summa = min(baas_kval, (baas_kval / norm_paevad) * toopaevad_count) if norm_paevad > 0 else 0

    st.subheader("💰 Koondkokkuvõte")
    st.info(f"**Töötunnid kokku:** {round(kokku_tunnid, 2)} h")
    
    df_summ = pd.DataFrame({
        "Tasuliik": [
            "1. Põhitasu (sh >12h pausid ja pühad)", 
            "2. Õhtu- ja öölisad", 
            "3. Kahepoolne tuur (Split 20%)", 
            "4. Õpilase juhendamine", 
            "5. Kvalifikatsioonitasu"
        ],
        "Summa (€)": [
            res_df['Põhitasu+Paus'].sum(),
            res_df['Õhtu/Öö'].sum(),
            res_df['Split (20%)'].sum(),
            res_df['Õpilane'].sum(),
            kval_summa
        ]
    })
    
    df_summ['Summa (€)'] = df_summ['Summa (€)'].round(2)
    st.table(df_summ)
    
    kogusumma = round(df_summ['Summa (€)'].sum(), 2)
    st.success(f"**HINNANGULINE KOGUSUMMA (BRUTO): {kogusumma} €**")
    
else:
    st.info("Palun täida töögraafik (vali tuurid), et näha tulemusi.")
