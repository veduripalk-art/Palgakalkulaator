import pandas as pd
from datetime import datetime, timedelta

def arvuta_lisatasud(algus_dt, lopp_dt, tunnitasu):
    """Arvutab ainult õhtu- ja öötundide lisatasud."""
    ohtu_lisa = 0
    oo_lisa = 0
    samm = timedelta(minutes=15)
    
    praegune = algus_dt
    while praegune < lopp_dt:
        tund = praegune.hour
        
        # Õhtulisa (18:00 - 22:00) -> 10%
        if 18 <= tund < 22:
            ohtu_lisa += (tunnitasu * 0.1) * 0.25
            
        # Öölisa (22:00 - 06:00) -> 25%
        if tund >= 22 or tund < 6:
            oo_lisa += (tunnitasu * 0.25) * 0.25
            
        praegune += samm
        
    return round(ohtu_lisa, 2), round(oo_lisa, 2)

def hanki_tuuri_andmed(kuupaev_str, tuuri_nr, faili_tee, tunnitasu):
    try:
        df = pd.read_csv(faili_tee).dropna(how='all')
        kpv = datetime.strptime(kuupaev_str, '%Y-%m-%d')
        
        # Nädalapäeva tähised
        tahised = ["E", "T", "K", "N", "R", "L", "P"]
        tahis = tahised[kpv.weekday()]
        
        # 1. Filtreerime perioodi (ALATES ja KUNI)
        df['ALATES'] = pd.to_datetime(df['ALATES'])
        df['KUNI'] = pd.to_datetime(df['KUNI'])
        df = df[(df['ALATES'] <= kpv) & (df['KUNI'] >= kpv)]

        # 2. Otsime õiget päeva tähist (ER, LP, EP või täpne kuupäev)
        def paeva_match(tabeli_paev):
            tabeli_paev = str(tabeli_paev).strip().upper()
            if tabeli_paev == kpv.strftime('%d.%m'): return True
            maatriks = {
                'ER': [0, 1, 2, 3, 4], 
                'LP': [5, 6], 
                'EP': [0, 1, 2, 3, 4, 5, 6],
                'E': [0], 'T': [1], 'K': [2], 'N': [3], 'R': [4]
            }
            return kpv.weekday() in maatriks.get(tabeli_paev, [])

        match = df[df['PAEV'].apply(paeva_match) & (df['TUUR'].astype(str) == str(tuuri_nr))]

        if match.empty:
            return f"Tuuri {tuuri_nr} ei leitud päeval {tahis}"

        rida = match.iloc[0]
        
        # 3. Kellaajad ja 12h piirang
        algus_str = rida['ALGUS'].strip()
        lopp_str = rida['LOPP'].strip()
        t1 = datetime.strptime(f"{kuupaev_str} {algus_str}", '%Y-%m-%d %H:%M')
        t2 = datetime.strptime(f"{kuupaev_str} {lopp_str}", '%Y-%m-%d %H:%M')
        
        if t2 <= t1: 
            t2 += timedelta(days=1)

        tunnid = (t2 - t1).total_seconds() / 3600
        if tunnid > 12.0: 
            tunnid = 12.0
            t2 = t1 + timedelta(hours=12)

        # 4. Arvutused
        o_lisa, oo_lisa = arvuta_lisatasud(t1, t2, tunnitasu)
        pohitasu = round(tunnid * tunnitasu, 2)
        kokku = round(pohitasu + o_lisa + oo_lisa, 2)

        return {
            "Kuupäev": f"{kuupaev_str} ({tahis})",
            "Tuur": tuuri_nr,
            "Tunnid": tunnid,
            "Põhitasu": pohitasu,
            "Õhtulisa (10%)": o_lisa,
            "Öölisa (25%)": oo_lisa,
            "TASU KOKKU": kokku
        }
    except Exception as e:
        return f"Viga: {e}"
