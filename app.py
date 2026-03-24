import pandas as pd
from datetime import datetime, timedelta

def normalize_day(day_str, target_date_obj):
    """Tuvastab, kas rida sobib nädalapäeva või konkreetse kuupäeva järgi."""
    if pd.isna(day_str): return False
    
    day_str = str(day_str).strip().upper()
    target_day_index = target_date_obj.weekday() # 0=E, 1=T... 6=P
    target_date_short = target_date_obj.strftime('%d.%m') # Nt '06.04'

    # 1. Kontrollime täpset kuupäeva (nt '06.04')
    if day_str == target_date_short:
        return True

    # 2. Kontrollime nädalapäeva vahemikke
    mapping = {
        'E': [0], 'T': [1], 'K': [2], 'N': [3], 'R': [4], 'L': [5], 'P': [6],
        'ER': [0, 1, 2, 3, 4],
        'E-R': [0, 1, 2, 3, 4],
        'LP': [5, 6],
        'L-P': [5, 6],
        'EP': [0, 1, 2, 3, 4, 5, 6],
        'E-P': [0, 1, 2, 3, 4, 5, 6],
        'EN': [0, 1, 2, 3],
        'E-N': [0, 1, 2, 3],
        'TR': [1, 2, 3, 4],
        'T-R': [1, 2, 3, 4]
    }
    
    allowed_days = mapping.get(day_str, [])
    return target_day_index in allowed_days

def arvuta_tuuri_andmed(sisestatud_kuupäev, tuuri_number, faili_tee):
    try:
        # Loeme faili ja eemaldame tühjad read, et vältida loading-stucki
        df = pd.read_csv(faili_tee).dropna(how='all')
        
        kuupaev_obj = datetime.strptime(sisestatud_kuupäev, '%Y-%m-%d')
        paevade_nimed = ["Esmaspäev (E)", "Teisipäev (T)", "Kolmapäev (K)", 
                         "Neljapäev (N)", "Reede (R)", "Laupäev (L)", "Pühapäev (P)"]
        nimega_paev = paevade_nimed[kuupaev_obj.weekday()]

        # Filtreerime kuupäeva vahemiku järgi
        df['ALATES'] = pd.to_datetime(df['ALATES'], errors='coerce')
        df['KUNI'] = pd.to_datetime(df['KUNI'], errors='coerce')
        df = df.dropna(subset=['ALATES', 'KUNI'])
        
        mask = (df['ALATES'] <= kuupaev_obj) & (df['KUNI'] >= kuupaev_obj)
        df_periood = df[mask].copy()

        # Leiame õige rea nädalapäeva loogikaga
        df_periood['match'] = df_periood['PAEV'].apply(lambda x: normalize_day(x, kuupaev_obj))
        match = df_periood[(df_periood['TUUR'].astype(str) == str(tuuri_number)) & (df_periood['match'] == True)]

        if match.empty:
            return {"viga": f"Tuuri {tuuri_number} ei leitud päeval {nimega_paev}"}

        rida = match.iloc[0]
        
        # Kellaja arvutus
        fmt = '%H:%M'
        t1 = datetime.strptime(str(rida['ALGUS']).strip(), fmt)
        t2 = datetime.strptime(str(rida['LOPP']).strip(), fmt)

        if t2 <= t1:
            t2 += timedelta(days=1)

        tunnid = (t2 - t1).total_seconds() / 3600
        
        # PIIRANG: Max 12h
        if tunnid > 12.0:
            tunnid = 12.0

        return {
            "kuupäev": f"{sisestatud_kuupäev} ({nimega_paev})",
            "tuur": tuuri_number,
            "tunnid": round(tunnid, 2),
            "algus": rida['ALGUS'],
            "lopp": rida['LOPP']
        }
    except Exception as e:
        return {"viga": f"Süsteemi viga: {str(e)}"}
