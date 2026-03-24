import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SEADISTUS JA KONFIGURATSIOON ---
st.set_page_config(page_title="Vedurijuhi Portaal", layout="wide")

# Google Sheets CSV eksportimise link (Asenda see oma uue meili tabeli lingiga!)
# Tabel peab olema "Anyone with the link can view"
SHEET_URL = "https://docs.google.com/spreadsheets/d/SINU_TABELI_ID/export?format=csv"

KVALIFIKATSIOONID = {
    "EMU/DMU (140€)": 140,
    "EMU+DMU (165€)": 165,
    "EMU+DMU+SKODA (205€)": 205
}

ERISYNDMUSED = {
    "KO (Kontor)": 8.0,
    "Tehniline õppus": 2.0,
    "Liikluskorralduse infotund": 4.0
}

# --- 2. ABIFUNKTSIOONID ---

def get_day_type(date):
    d = date.weekday()
    if d == 0: return "E"
    if 1 <= d <= 3: return "T-N"
    if d == 4: return "R"
    return "LP"

def get_quarter(month):
    if month in [1, 2, 3]: return "Q1 (Jaan-Märts)"
    if month in [4, 5, 6]: return "Q2 (Apr-Juuni)"
    if month in [7, 8, 9]: return "Q3 (Juuli-Sept)"
    return "Q4 (Okt-Dets)"

def calculate_hours_and_pay(start_str, end_str, base, is_split, has_student, extra_min):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(start_str.strip(), fmt)
        e = datetime.strptime(end_str.strip(), fmt)
        if e <= s: e += timedelta(days=1)
        
        tunnid = ((e - s).total_seconds() / 3600) + (extra_min / 60)
        
        tunnitasu = base
        if is_split: tunnitasu += (base * 0.20)
        if has_student: tunnitasu += (base * 0.20)
            
        return tunnid, tunnid * tunnitasu
    except:
        return 0, 0

# --- 3. ANDMETE LAADIMINE ---

# Märtsikuu tuurid (ajutine lokaalne andmebaas kuni Sheets on valmis)
# Formaat: "Tuur": {"Paevatüüp": (Algus, Lopp, Split)}
MARTS_TUURID = {
    "11/1": {"default": ("11:20", "20:50", True)},
    "15/2": {"E": ("05:15", "10:25", False), "T-R": ("05:50", "09:35", False)},
    "61/1": {"ER": ("05:40", "19:00", True), "LP": ("08:10", "19:00", True)},
    # Siia lisanduvad ülejäänud märtsi tuurid...
}

# --- 4. KASUTAJALIIDES (SIDEBAR) ---

with st.sidebar:
    st.header("⚙️ Seaded")
    baas_palk = st.number_input("Baastasu (€/h)", value=12.42)
    valitud_kval = st.selectbox("Kvalifikatsioonipakett", options=list(KVALIFIKATSIOONID.keys()))
    norm_kuu = st.number_input("Kuu normtunnid (100%)", value=168.0)
    
    st.divider()
    valitud_kuu = st.selectbox("Vali kuu täitmiseks", ["Jaanuar", "Veebruar", "Märts", "Aprill", "Mai", "Juuni"])
    kuu_indeksid = {"Jaanuar": 1, "Veebruar": 2, "Märts": 3, "Aprill": 4, "Mai": 5, "Juuni": 6}
    k_num = kuu_indeksid[valitud_kuu]
    st.info(f"Kvartal: {get_quarter(k_num)}")

# --- 5. TÖÖGRAAFIKU TÄITMINE ---

st.title(f"🚂 Vedurijuhi Töölaud: {valitud_kuu}")

# Määrame päevade arvu
if k_num in [4, 6, 9, 11]: päevi = 30
elif k_num == 2: päevi = 28
else: päevi = 31

graafik_tabel = []
cols = st.columns(7)

for i in range(1, päevi + 1):
    curr_date = datetime(2026, k_num, i)
    dtype = get_day_type(curr_date)
    
    with cols[(i-1) % 7]:
        st.write(f"**{i:02d}.{k_num:02d} ({dtype})**")
        
        # Tuuri valik (Lisatud P - Puhkus)
        t_valik = st.selectbox("Tuur", ["Vaba", "P (Puhkus)", "KO", "Õppus"] + sorted(list(MARTS_TUURID.keys())), key=f"t_{i}")
        
        # Lisaaeg ja õpilane
        lisa_min = st.number_input("+ min", min_value=0, step=5, key=f"m_{i}")
        on_opilane = st.checkbox("Õp", key=f"s_{i}")

        p_tunnid, p_tasu, is_work, normi_vahendus = 0, 0, False, 0

        if t_valik == "P (Puhkus)":
            normi_vahendus = 8.0 # Vähendab kuu normi
        elif t_valik in ERISYNDMUSED:
            p_tunnid = ERISYNDMUSED[t_valik]
            p_tasu = p_tunnid * baas_palk
            is_work = True
        elif t_valik in MARTS_TUURID:
            is_work = True
            db = MARTS_TUURID[t_valik]
            # Valime loogika (lihtsustatud siin, laiendatav Sheetsiga)
            if dtype in db: logic = db[dtype]
            elif "ER" in db and dtype != "LP": logic = db["ER"]
            else: logic = db.get("default", ("00:00", "00:00", False))
            
            p_tunnid, p_tasu = calculate_hours_and_pay(logic[0], logic[1], baas_palk, logic[2], on_opilane, lisa_min)

        graafik_tabel.append({
            "Päev": i, 
            "Tunnid": p_tunnid, 
            "Tasu": p_tasu, 
            "Töö": is_work, 
            "Normivähendus": normi_vahendus
        })

# --- 6. ARVUTUSED JA STATISTIKA ---

df = pd.DataFrame(graafik_tabel)

kokku_tunnid = df["Tunnid"].sum()
kokku_tasu = df["Tasu"].sum()
kokku_normi_vahendus = df["Normivähendus"].sum()
toopaevi = df[df["Töö"] == True].shape[0]

# Kvalifikatsioonitasu (piiranguga)
max_kval = KVALIFIKATSIOONID[valitud_kval]
arvutatud_kval = min((toopaevi / 22) * max_kval, max_kval) # 22 on keskmine tööpäevade arv

# Ületundide loogika
tegelik_norm = norm_kuu - kokku_normi_vahendus
uletunnid = max(0, kokku_tunnid - tegelik_norm)
uletundide_lisatasu = uletunnid * (baas_palk * 0.5) # See on see "0.5 osa", mis teeb kokku 1.5x

st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Tehtud töötunnid", f"{kokku_tunnid:.2f} h")
col2.metric("Tegelik norm", f"{tegelik_norm:.1f} h", delta=f"-{kokku_normi_vahendus}h (P)")
col3.metric("Ületunnid", f"{uletunnid:.2f} h")
col4.metric("Kvalifikatsioon", f"{arvutatud_kval:.2f} €")

st.subheader(f"💰 Prognoositav väljamakse: {(kokku_tasu + arvutatud_kval):.2f} €")

# Kvartali info
with st.expander("📊 Kvartali ületundide arvestus (info)"):
    st.write(f"Käesolev kvartal: **{get_quarter(k_num)}**")
    st.write(f"Selle kuu ületundide lisatasu (1.5x): **{uletundide_lisatasu:.2f} €**")
    st.caption("Märkus: Ületundide lisatasu makstakse välja kvartali viimasel kuul.")

st.dataframe(df[df["Tunnid"] > 0][["Päev", "Tunnid", "Tasu"]], use_container_width=True)
