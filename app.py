# Otsingu parandus get_matching_rows funktsioonis:
def get_matching_rows(df, tuur_nimi, valitud_kuupaev):
    # Võtame kõik selle nimega tuurid, eirates kuupäeva piirangut testimiseks
    potentsiaalsed = df[df['TUUR'].str.contains(tuur_nimi, na=False)]
    if potentsiaalsed.empty: return None
    
    wd = valitud_kuupaev.weekday()
    kp_str = valitud_kuupaev.strftime("%d.%m")
    
    # Puhastame tabeli päeva tähise tühikutest ja teeme suureks
    potentsiaalsed['PAEV_CLEAN'] = potentsiaalsed['PAEV'].str.strip().upper()
    
    # 1. Täpne kuupäev
    match = potentsiaalsed[potentsiaalsed['PAEV_CLEAN'].str.contains(kp_str, na=False)]
    if not match.empty: return match.iloc[0]
    
    # 2. Loogilised tähised
    otsitavad = ["DEFAULT"]
    if wd <= 4: otsitavad.append("ER")
    if wd >= 5: otsitavad.append("LP")
    
    for o in reversed(otsitavad):
        match = potentsiaalsed[potentsiaalsed['PAEV_CLEAN'] == o]
        if not match.empty: return match.iloc[0]
        
    return potentsiaalsed.iloc[0] # Kui midagi ei leia, võta esimene rida
