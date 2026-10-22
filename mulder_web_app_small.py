import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Mulder Diagnose Tool", layout="wide")

st.info("📱 **Setup-Menü:** Tippe oben links auf den Pfeil ( **>** ), um pH-Wert, Blütetag und Verhältnisse einzustellen.")

def get_availability(nutrient, ph, temp, light):
    # 1. pH-Basisverfügbarkeit (beidseitig kalibriert nach den pH-Referenztafeln)
    if nutrient == 'N': 
        # Ideal 6.0 - 7.5, Abfall im stark sauren (<5.5) und alkalischen (>8.0) Bereich
        base = np.clip(1.0 - max(0.0, 5.8 - ph) * 0.5 - max(0.0, ph - 7.5) * 0.5, 0.1, 1.0)
    elif nutrient in ['K', 'S']: 
        # Ab pH 6.0 voll verfügbar, knickt nur unter 5.5 ein
        base = np.clip((ph - 4.5) / 1.5, 0.1, 1.0)
    elif nutrient == 'P': 
        # Enges Optimum zwischen 6.2 und 7.2, starker Lockout darunter und darüber
        base = np.clip(1.0 - abs(6.7 - ph) * 0.65, 0.1, 1.0)
    elif nutrient == 'Ca': 
        # Optimum 6.0 - 7.8, fällt unter 6.0 und über 8.0 stark ab
        base = np.clip(1.0 - max(0.0, 6.0 - ph) * 0.6 - max(0.0, ph - 7.6) * 0.6, 0.1, 1.0)
    elif nutrient == 'Mg': 
        # Optimum 6.0 - 8.2, fällt unter 6.0 und über 8.2 ab
        base = np.clip(1.0 - max(0.0, 5.8 - ph) * 0.6 - max(0.0, ph - 8.0) * 0.6, 0.1, 1.0)
    elif nutrient == 'Fe': 
        # Hochverfügbar im Sauren, fällt ab pH 6.0 steil ab
        base = np.clip(1.0 - max(0.0, ph - 5.5) * 0.45, 0.1, 1.0)
    elif nutrient in ['Mn', 'Zn', 'Cu', 'B']: 
        # Optimum 5.2 - 6.8, knickt bei extremem Säuregrad (<5.0) und ab 7.0 ein
        base = np.clip(1.0 - max(0.0, 5.2 - ph) * 0.5 - max(0.0, ph - 6.6) * 0.45, 0.1, 1.0)
    elif nutrient == 'Mo': 
        # Verfügbarkeit steigt erst ab pH 6.0+ richtig an
        base = np.clip((ph - 5.0) / 2.0, 0.1, 1.0)
    elif nutrient == 'Na': 
        base = 0.8
    else: 
        base = 0.5
        
    # 2. Thermodynamik & Licht (Transpirationssog / Mikrobiologie)
    light_factor = np.clip(light / 100.0, 0.3, 1.2)
    
    if nutrient == 'P': 
        # Physikalische Diffusionssperre im kalten Substrat (<14°C)
        return np.clip(base * np.clip((temp - 8.0) / 10.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient in ['N', 'S']: 
        # Mikrobielle Umsetzung temperaturabhängig
        return np.clip(base * np.clip((temp - 5.0) / 15.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient == 'Mg': 
        # Direkt gekoppelt an Chlorophyll-Aktivität (Licht)
        return np.clip(base * light_factor, 0.1, 1.0)
    elif nutrient == 'Ca': 
        # Passiver Transport im Xylem-Massenstrom (Licht + Wärme)
        return np.clip(base * light_factor * np.clip(temp / 24.0, 0.3, 1.0), 0.1, 1.0)
    else: 
        return np.clip(base * np.clip((temp + 5.0) / 27.0, 0.2, 1.0), 0.1, 1.0)

def get_demand(nutrient, day):
    """ Relativer Pflanzenbedarf über die Blütephase (Tag 0 bis 75) """
    if nutrient == 'N': return np.clip(1.2 - (day / 70.0) * 0.8, 0.3, 1.2) 
    elif nutrient == 'Ca': return 0.8 + np.sin(np.clip(day / 30.0, 0, 1) * np.pi) * 0.55 # Stretch-Peak (Zellwandbau)
    elif nutrient == 'P': return 0.7 + np.sin(np.clip((day - 10) / 50.0, 0, 1) * np.pi) * 0.5 # Blütenanlage
    elif nutrient == 'Mg': return 0.8 + np.sin(np.clip((day - 8) / 42.0, 0, 1) * np.pi) * 0.45 # Mittlere Blüte
    elif nutrient == 'K': return 0.75 + np.sin(np.clip((day - 18) / 52.0, 0, 1) * np.pi) * 0.6 # Blütenmasse-Peak
    else: return 1.0 

def get_ph_zone_stress(ph):
    """ Steuert die Aggressivität der Antagonismen außerhalb des pH-Pufferbereichs (6.0 - 7.0) """
    if 6.0 <= ph <= 7.0: return 0.35 + 0.10 * (abs(ph - 6.5) / 0.5) 
    elif 5.5 <= ph < 6.0: return 0.45 + 0.30 * ((6.0 - ph) / 0.5)
    elif 7.0 < ph <= 7.5: return 0.45 + 0.30 * ((ph - 7.0) / 0.5)
    elif ph < 5.5: return 0.75 + 0.25 * (min(5.5 - ph, 1.5) / 1.5)
    else: return 0.75 + 0.25 * (min(ph - 7.5, 2.5) / 2.5)

nutrients = ['N', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo', 'Na']

# Exakt abgeglichen mit dem Referenz-Wirkungsgefüge
antagonisms_strong = [
    ('Ca','K'), ('Ca','Mg'), ('Ca','P'), ('Ca','Zn'), ('Ca','Mn'), ('Ca','B'),
    ('K','Ca'), ('K','Mg'), ('K','Na'),
    ('P','Ca'), ('P','Zn'),
    ('Mn','N')
]
antagonisms_weak = [
    ('Ca','Fe'), ('Mn','Fe'), ('Zn','Fe'), ('Cu','Fe'), ('Cu','Mn'),
    ('P','Cu'), ('P','K'), ('K','B'), ('N','K'), ('N','B'), ('Fe','P')
]
synergies = [
    ('N','Mg'), ('P','Mg'), ('Mg','P'), ('K','Fe'), ('K','Mn'), ('Mn','S'), ('S','N')
]

st.sidebar.header("🌱 Wachstumsphase")
bluetetag = st.sidebar.slider("Blütetag", 0, 75, 15, 1)

st.sidebar.header("💧 Verhältnisse (Gießwasser)")
st.sidebar.caption("Das physiologische Idealverhältnis für Ca:Mg liegt bei ca. 3:1")
camg_ratio = st.sidebar.slider("Ca:Mg Verhältnis", 1.0, 6.0, 3.0, 0.1)

st.sidebar.header("🌡️ Umwelt-Parameter")
ph_value = st.sidebar.slider("pH-Level", 4.0, 9.0, 6.5, 0.1)
temp_value = st.sidebar.slider("Temperatur (°C)", 5.0, 35.0, 22.0, 1.0)
light_value = st.sidebar.slider("Lichtintensität (%)", 0, 100, 100, 5)

G = nx.DiGraph()
G.add_nodes_from(nutrients)
G.add_edges_from(antagonisms_strong, type='antagonism_strong')
G.add_edges_from(antagonisms_weak, type='antagonism_weak')
G.add_edges_from(synergies, type='synergism')

pos = nx.circular_layout(G)
node_sizes, node_colors, edge_colors, edge_widths = [], [], [], []

# 1. KNOTEN: Interne Pflanzen-Bilanz = (Verfügbarkeit * Zufuhr) / Bedarf
for node in G.nodes():
    env_factor = get_availability(node, ph_value, temp_value, light_value)
    
    if node == 'Ca': supply = (camg_ratio / 3.0)
    elif node == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
        
    demand = get_demand(node, bluetetag)
    saturation = np.clip((env_factor * supply) / demand, 0.1, 1.5)
    
    node_sizes.append(2000 + (saturation * 4000))
    if saturation >= 0.8: node_colors.append('#388e3c') 
    elif saturation >= 0.55: node_colors.append('#fbc02d')
    else: node_colors.append('#d32f2f')

ph_stress = get_ph_zone_stress(ph_value)

# 2. PFEILE: Reine Ionen-Konkurrenz im Wurzelraum (unabhängig vom Blütetag-Bedarf)
for u, v, data in G.edges(data=True):
    env_factor = get_availability(u, ph_value, temp_value, light_value)
    if u == 'Ca': supply = (camg_ratio / 3.0)
    elif u == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
    
    # Aktive Ionenmasse an der Wurzeloberfläche
    ion_mass = env_factor * supply
    
    if data['type'] in ['antagonism_strong', 'antagonism_weak']:
        # Antagonismus eskaliert bei pH-Stress ODER massiver Überdosierung (supply > 1.0)
        arrow_strength = np.clip(ion_mass * ph_stress * (supply ** 0.4), 0.1, 1.0)
        edge_widths.append(2.0 + (arrow_strength * 6.0))
        
        if data['type'] == 'antagonism_strong':
            if arrow_strength >= 0.68: edge_colors.append('#d32f2f')
            elif arrow_strength >= 0.42: edge_colors.append('#fbc02d')
            else: edge_colors.append('#9e9e9e')
        else:
            if arrow_strength >= 0.68: edge_colors.append('#616161') 
            elif arrow_strength >= 0.42: edge_colors.append('#9e9e9e')
            else: edge_colors.append('#cfcfcf') 
            
    elif data['type'] == 'synergism':
        # Synergismus skaliert direkt mit der real verfügbaren Masse des Geber-Elements
        arrow_strength = np.clip(ion_mass * 0.55, 0.1, 1.0)
        edge_widths.append(2.0 + (arrow_strength * 6.0))
        
        if arrow_strength >= 0.70: edge_colors.append('#1b5e20') # Überförderung (z.B. bei starkem Überschuss)
        elif arrow_strength >= 0.40: edge_colors.append('#4caf50') # Optimaler Synergismus
        else: edge_colors.append('#c8e6c9') # Abgeschwächt durch Mangel des Geber-Elements

st.title("Dynamisches Nährstoff-Diagnosetool")

fig, ax = plt.subplots(figsize=(12, 12))

nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color=node_colors, edgecolors='#222222', linewidths=2)
nx.draw_networkx_labels(G, pos, ax=ax, font_size=13, font_weight='bold')
nx.draw_networkx_edges(G, pos, ax=ax, node_size=node_sizes, edge_color=edge_colors, width=edge_widths, arrowsize=25, connectionstyle='arc3,rad=0.15', arrows=True)

fig.patch.set_facecolor('#ffffff')
ax.axis('off')
    
st.pyplot(fig, use_container_width=False)

st.markdown("---")
st.markdown("### 📊 Legende zur Diagnose")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Knoten (Pflanzen-Sättigung vs. Bedarf)")
    st.markdown("🟢 **Grüner Knoten:** Verfügbarkeit und Zufuhr decken den relativen Bedarf der Pflanze am gewählten Blütetag.")
    st.markdown("🟡 **Gelber Knoten:** Grenzbereich. Entweder steigt der Bedarf stark an (z.B. Ca im Stretch, K in der Hochblüte) oder Umweltfaktoren bremsen die Aufnahme.")
    st.markdown("🔴 **Roter Knoten:** Relatives Defizit! Die Pflanze verbraucht mehr, als durch pH-Wert, Temperatur oder Ca:Mg-Verhältnis nachgeliefert werden kann.")

with col2:
    st.markdown("#### Pfeile (Wurzelraum-Dynamik)")
    st.markdown("🔴 **Roter Pfeil (Toxische Blockade):** Aktive Verdrängung des Zielelements an der Wurzel durch falschen pH-Wert oder extremes Ca:Mg-Ungleichgewicht.")
    st.markdown("🟡 **Gelber Pfeil (Warnbereich):** Erhöhte Ionenkonkurrenz im Substrat.")
    st.markdown("⚪ **Grauer Pfeil (Steuernd):** Natürliches Gleichgewicht im pH-Pufferbereich (6,0–7,0).")
    st.markdown("🟢 **Mittelgrüner Pfeil:** Aktiver Synergismus unterstützt die Aufnahme des Zielelements.")
    st.markdown("🟩 **Dunkelgrüner Pfeil:** Überförderung durch massiven Überschuss des Geber-Elements.")

st.markdown("---")
st.markdown("### Über dieses Tool")
st.markdown("Dieses Diagnosetool stellt die relativen Wechselwirkungen zwischen Umweltparametern (pH, Temperatur, Licht), Ionenkonkurrenz und dem dynamischen Bedarf im Blüteverlauf dar.")
st.markdown("**Kontakt:** Discord `@BonsaiDaddy`")
st.caption("⚖️ **Hinweis:** Privates Hobby-Projekt zu Bildungszwecken. Das Modell bildet ausschließlich relative Tendenzen ab, liefert keine quantitativen Düngeempfehlungen und ersetzt keine Substrat- oder Wasseranalyse.")
