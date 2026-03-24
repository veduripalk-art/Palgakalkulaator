import pandas as pd
from datetime import datetime, timedelta

def arvuta_tuuri_andmed(sisestatud_kuupäev, tuuri_number, tabeli_fail):
    # 1. Laeme tabeli
    df = pd.read_csv(tabeli_fail)
    
    # 2. Teisendame kuupäevad ja leiame nädalapäeva
    kuupaev_obj = datetime.strptime(sisestatud_kuupäev, '%Y-%m-%d')
    nadalapaev = kuupaev_obj.strftime('%A') # Tagastab nt 'Monday'
    
    # Eesti keelsed vasted, kui tabelis on eestikeelsed päevad
    paevade_kaart = {
        'Monday': 'Esmaspäev',
        'Tuesday': 'Teisipäev',
        'Wednesday': 'Kolmapäev',
        'Thursday': 'Neljapäev',
        'Friday': 'Reede',
        'Saturday': 'Laupäev',
        'Sunday': 'Pühapäev'
    }
    ee_paev = paevade_kaart[nadalapaev]

    # 3. Filtreerime õige rea (Tuur + Päev + Kehtivusvahemik)
    df['ALATES'] = pd.to_datetime(df['ALATES'])
    df['KUNI'] = pd.to_datetime(df['KUNI'])
    
    match = df[
        (df['TUUR'] == tuuri_number) & 
        (df['PAEV'] == ee_paev) & 
        (df['ALATES'] <= kuupaev_obj) & 
        (df['KUNI'] >= kuupaev_obj)
    ]

    if match.empty:
        return "Tuuri ei leitud antud kuupäeval."

    rida = match.iloc[0]
    algus_str = str(rida['ALGUS'])
    lopp_str = str(rida['LOPP'])

    # 4. KELLAAJA ARVUTAMISE LOOGIKA (Südaöö parandus)
    fmt = '%H:%M'
    t1 = datetime.strptime(algus_str, fmt)
    t2 = datetime.strptime(lopp_str, fmt)

    # Kui lõppaeg on numbriliselt väiksem (nt 00:30 < 22:00), lisame ühe päeva
    if t2 <= t1:
        t2 += timedelta(days=1)

    tunnid = (t2 - t1).total_seconds() / 3600
    
    # 5. Tasu arvutamine (näide)
    tunnitasu = 10.0 # Sisesta siia oma õige tunnitasu
    kokku_tasu = tunnid * tunnitasu
    
    if rida['SPLIT'] == True:
        kokku_tasu += 5.0 # Lisa siia split-vahetuse lisatasu

    return {
        "tunnid": tunnid,
        "tasu": round(kokku_tasu, 2),
        "algus": algus_str,
        "lopp": lopp_str
    }

# KASUTAMINE:
# tulemus = arvuta_tuuri_andmed('2026-04-06', '33', 'tuurid.csv')
# print(tulemus)
