import pandas as pd
from datetime import datetime, timedelta

def normalize_day(day_str, target_day_name):
    """
    Kontrollib, kas otsitav nädalapäev kuulub tabelis märgitud tähise alla.
    """
    day_str = str(day_str).upper().replace(" ", "")
    target_map = {
        'Monday': ['E', 'ER', 'E-R', 'EP', 'E-P', 'ESMASPÄEV', 'DEFAULT'],
        'Tuesday': ['T', 'ER', 'E-R', 'EP', 'E-P', 'TR', 'T-R', 'TEISIPÄEV', 'DEFAULT'],
        'Wednesday': ['K', 'ER', 'E-R', 'EP', 'E-P', 'TR', 'T-R', 'KOLMAPÄEV', 'DEFAULT'],
        'Thursday': ['N', 'ER', 'E-R', 'EP', 'E-P', 'TR', 'T-R', 'EN', 'E-N', 'NELJAPÄEV', 'DEFAULT'],
        'Friday': ['R', 'ER', 'E-R', 'EP', 'E-P', 'TR', 'T-R', 'REEDE', 'DEFAULT'],
        'Saturday': ['L', 'LP', 'L-P', 'EP', 'E-P', 'LAUPÄEV', 'DEFAULT'],
        'Sunday': ['P', 'LP', 'L-P', 'EP', 'E-P', 'PÜHAPÄEV', 'DEFAULT']
    }
    
    # Kui tabelis on kuupäev (nt 06.04), kontrollime seda eraldi
    if "." in day_str and len(day_str) <= 5:
        return False # Seda käitleme filtreerimisel eraldi
        
    allowed_codes = target_map.get(target_day_name, [])
    return day_str in allowed_codes

def arvuta_tuuri_andmed(sisestatud_kuupäev, tuuri_number, tabeli_fail):
    df = pd.read_csv(tabeli_fail)
    
    kuupaev_obj = datetime.strptime(sisestatud_kuupäev, '%Y-%m-%d')
    inglise_paev = kuupaev_obj.strftime('%A') # Nt 'Monday'
    luhike_kp = kuupaev_obj.strftime('%d.%m') # Nt '06.04'

    # 1. Filtreerime kuupäeva vahemiku järgi
    df['ALATES'] = pd.to_datetime(df['ALATES'])
    df['KUNI'] = pd.to_datetime(df['KUNI'])
    df = df[(df['ALATES'] <= kuupaev_obj) & (df['KUNI'] >= kuupaev_obj)].copy()

    # 2. Otsime õiget rida (prioriteet: täpne kuupäev -> nädalapäev)
    match = df[(df['TUUR'] == str(tuuri_number)) & (df['PAEV'] == luhike_kp)]
    
    if match.empty:
        # Kui täpset kuupäeva pole, otsime nädalapäeva tähise järgi
        df['is_match'] = df['PAEV'].apply(lambda x: normalize_day(x, inglise_paev))
        match = df[(df['TUUR'] == str(tuuri_number)) & (df['is_match'] == True)]

    if match.empty:
        return "Viga: Tuuri või päeva ei leitud!"

    rida = match.iloc[0]
    
    # 3. Kellaaja arvutus
    fmt = '%H:%M'
    # Puhastame kellaaja stringid tühikutest
    algus_s = str(rida['ALGUS']).strip()
    lopp_s = str(rida['LOPP']).strip()
    
    t1 = datetime.strptime(algus_s, fmt)
    t2 = datetime.strptime(lopp_s, fmt)

    if t2 <= t1:
        t2 += timedelta(days=1)

    tunnid = (t2 - t1).total_seconds() / 3600
    
    # 4. PIIRANG: Maksimaalselt 12 tundi
    if tunnid > 12.0:
        tunnid = 12.0

    return {
        "tuur": tuuri_number,
        "paev": inglise_paev,
        "algus": algus_s,
        "lopp": lopp_s,
        "tunnid": tunnid
    }

# Testimine:
# print(arvuta_tuuri_andmed('2026-04-06', '13/1', 'tabel.csv'))
