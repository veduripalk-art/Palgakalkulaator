import pandas as pd
from datetime import datetime, timedelta

def arvuta_tuuri_palk(algus_dt, lopp_dt, on_kahepoolne):
    baashind = 2.58
    ohtu_protsent = 0.20
    oo_protsent = 0.40
    puhkeaja_protsent = 0.20
    
    sekundid_kokku = (lopp_dt - algus_dt).total_seconds()
    tunnid_kokku = min(sekundid_kokku / 3600, 12.0)
    
    # Põhitasu
    pohitasu = tunnid_kokku * baashind
    
    # Lisatasude arvutamine (15-minutilise sammuga täpsuse huvides)
    ohtu_lisa = 0
    oo_lisa = 0
    samm = timedelta(minutes=15)
    praegune = algus_dt
    piir_dt = algus_dt + timedelta(hours=tunnid_kokku)
    
    while praegune < piir_dt:
        tund = praegune.hour
        # Õhtulisa (oletame standardit 18-22, kui on teiti, muuda siin)
        if 18 <= tund < 22:
            ohtu_lisa += (baashind * ohtu_protsent) * 0.25
        # Öölisa (22-06)
        elif tund >= 22 or tund < 6:
            oo_lisa += (baashind * oo_protsent) * 0.25
        praegune += samm
        
    # Puhkeaja tasu (kui on kahepoolne tuur, lisandub 20% kogu ajale)
    puhkeaja_tasu = 0
    if on_kahepoolne:
        puhkeaja_tasu = tunnid_kokku * (baashind * puhkeaja_protsent)
        
    kokku = pohitasu + o_lisa + oo_lisa + puhkeaja_tasu
    return round(pohitasu, 2), round(o_lisa, 2), round(oo_lisa, 2), round(puhkeaja_tasu, 2), round(kokku, 2)

def hanki_andmed(kuupaev_str, tuuri_nr, faili_tee):
    try:
        df = pd.read_csv(faili_tee).dropna(how='all')
        kpv = datetime.strptime(kuupaev_str, '%Y-%m-%d')
        tahis = ["E", "T", "K", "N", "R", "L", "P"][kpv.weekday()]
        
        # Filtreerime perioodi ja päeva
        df['ALATES'] = pd.to_datetime(df['ALATES'])
        df['KUNI'] = pd.to_datetime(df['KUNI'])
        df = df[(df['ALATES'] <= kpv) & (df['KUNI'] >= kpv)]
        
        def kontrolli_paeva(p):
            p = str(p).strip().upper()
            if p == kpv.strftime('%d.%m'): return True
            m = {'ER': [0,1,2,3,4], 'LP': [5,6], 'EP': [0,1,2,3,4,5,6]}
            return kpv.weekday() in m.get(p, [])

        match = df[df['PAEV'].apply(kontrolli_paeva) & (df['TUUR'].astype(str) == str(tuuri_nr))]
        
        if match.empty: return f"Tuuri {tuuri_nr} ei leitud ({tahis})"

        rida = match.iloc[0]
        t1 = datetime.strptime(f"{kuupaev_str} {rida['ALGUS'].strip()}", '%Y-%m-%d %H:%M')
        t2 = datetime.strptime(f"{kuupaev_str} {rida['LOPP'].strip()}", '%Y-%m-%d %H:%M')
        if t2 <= t1: t2 += timedelta(days=1)
        
        # Kontrollime, kas tuur on kahepoolne (nt sisaldab kaldkriipsu nagu 11/1)
        kahepoolne = "/" in str(tuuri_nr)
        
        pohi, ohtu, oo, puhke, kokku = arvuta_tuuri_palk(t1, t2, kahepoolne)
        
        return {
            "Kuupäev": f"{kuupaev_str} ({tahis})",
            "Tuur": tuuri_nr,
            "Tunnid": min(round((t2-t1).total_seconds()/3600, 2), 12.0),
            "Põhitasu": pohi,
            "Õhtulisa (20%)": ohtu,
            "Öölisa (40%)": oo,
            "Puhkeaja tasu (20%)": puhke,
            "KOKKU": kokku
        }
    except Exception as e:
        return f"Viga: {e}"
