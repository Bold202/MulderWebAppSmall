import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Mulder Diagnose Tool", layout="wide")

st.info("📱 **Setup-Menü:** Tippe oben links auf den Pfeil ( **>** ), um pH-Wert, Blütetag und Verhältnisse einzustellen.")

def get_availability(nutrient, ph, temp, light):
    if nutrient == 'N': 
        base = np.clip(1.0 - max(0.0, 5.8 - ph) * 0.5 - max(0.0, ph - 7.5) * 0.5, 0.1, 1.0)
    elif nutrient in ['K', 'S']: 
        base = np.clip((ph - 4.5) / 1.5, 0.1, 1.0)
    elif nutrient == 'P': 
        base = np.clip(1.0 - abs(6.7 - ph) * 0.65, 0.1, 1.0)
    elif nutrient == 'Ca': 
        base = np.clip(1.0 - max(0.0, 6.0 - ph) * 0.6 - max(0.0, ph - 7.6) * 0.6, 0.1, 1.0)
    elif nutrient == 'Mg': 
        base = np.clip(1.0 - max(0.0, 5.8 - ph) * 0.6 - max(0.0, ph - 8.0) * 0.6, 0.1, 1.0)
    elif nutrient == 'Fe': 
        base = np.clip(1.0 - max(0.0, ph - 5.5) * 0.45, 0.1, 1.0)
    elif nutrient in ['Mn', 'Zn', 'Cu', 'B']: 
        base = np.clip(1.0 - max(0.0, 5.2 - ph) * 0.5 - max(0.0, ph - 6.6) * 0.45, 0.1, 1.0)
    elif nutrient == 'Mo': 
        base = np.clip((ph - 5.0) / 2.0, 0.1, 1.0)
    elif nutrient == 'Na': 
        base = 0.8
    else: 
        base = 0.5
        
    light_factor = np.clip(light / 100.0, 0.3, 1.2)
    
    if nutrient == 'P': 
        return np.clip(base * np.clip((temp - 8.0) / 10.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient in ['N', 'S']: 
        return np.clip(base * np.clip((temp - 5.0) / 15.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient == 'Mg': 
        return np.clip(base * light_factor, 0.1, 1.0)
    elif nutrient == 'Ca': 
        return np.clip(base * light_factor * np.clip(temp / 24.0, 0.3, 1.0), 0.1, 1.0)
    else: 
        return np.clip(base * np.clip((temp + 5.0) / 27.0, 0.2, 1.0), 0.1, 1.0)

def get_demand(nutrient, day):
    if nutrient == 'N': return np.clip(1.2 - (day / 70.0) * 0.8, 0.3, 1.2) 
    elif nutrient == 'Ca': return 0.8 + np.sin(np.clip(day / 30.0, 0, 1) * np.pi) * 0.55 
    elif nutrient == 'P': return 0.7 + np.sin(np.clip((day - 10) / 50.0, 0, 1) * np.pi) * 0.5 
    elif nutrient == 'Mg': return 0.8 + np.sin(np.clip((day - 8) / 42.0, 0, 1) * np.pi) * 0.45 
    elif nutrient == 'K': return 0.75 + np.sin(np.clip((day - 18) / 52.0, 0, 1) * np.pi) * 0.6 
    else: return 1.0 

def get_ph_zone_stress(ph):
    if 6.0 <= ph <= 7.0: return 0.35 + 0.10 * (abs(ph - 6.5) / 0.5) 
    elif 5.5 <= ph < 6.0: return 0.45 + 0.30 * ((6.0 - ph) / 0.5)
    elif 7.0 < ph <= 7.5: return 0.45 + 0.30 * ((ph - 7.0) / 0.5)
    elif ph < 5.5: return 0.75 + 0.25 * (min(5.5 - ph, 1.5) / 1.5)
    else: return 0.75 + 0.25 * (min(ph - 7.5, 2.5) / 2.5)

nutrients = ['N', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo', 'Na']

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

for node in G.nodes():
    env_factor = get_availability(node, ph_value, temp_value, light_value)
    
    if node == 'Ca': supply = (camg_ratio / 3.0)
    elif node == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
        
    demand = get_demand(node, bluetetag)
    saturation = np.clip((env_factor * supply) / demand, 0.1, 2.0)
    
    # 25% kleinere Basisgrößen
    node_sizes.append(1500 + (saturation * 3000))
    
    # NEU: Überschuss-Warnung! Perfekt ist nur 0.85 bis 1.15
    if 0.85 <= saturation <= 1.15: 
        node_colors.append('#388e3c') # Perfekt (Grün)
    elif 0.55 <= saturation < 0.85 or 1.15 < saturation <= 1.4: 
        node_colors.append('#fbc02d') # Gelb (Leichter Mangel oder beginnender Überschuss)
    else: 
        node_colors.append('#d32f2f') # Rot (Akuter Mangel ODER toxischer Überschuss)

ph_stress = get_ph_zone_stress(ph_value)

for u, v, data in G.edges(data=True):
    env_factor = get_availability(u, ph_value, temp_value, light_value)
    if u == 'Ca': supply = (camg_ratio / 3.0)
    elif u == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
    
    ion_mass = env_factor * supply
    
    if data['type'] in ['antagonism_strong', 'antagonism_weak']:
        arrow_strength = np.clip(ion_mass * ph_stress * (supply ** 0.5), 0.1, 1.0)
        # NEU: Halbierte Basis-Dicke (1.0 statt 2.0)
        edge_widths.append(1.0 + (arrow_strength * 6.0))
        
        if data['type'] == 'antagonism_strong':
            if arrow_strength >= 0.68: edge_colors.append('#d32f2f')
            elif arrow_strength >= 0.42: edge_colors.append('#fbc02d')
            else: edge_colors.append('#9e9e9e')
        else:
            if arrow_strength >= 0.68: edge_colors.append('#616161') 
            elif arrow_strength >= 0.42: edge_colors.append('#9e9e9e')
            else: edge_colors.append('#cfcfcf') 
            
    elif data['type'] == 'synergism':
        # NEU: Synergismus ist im Standard blass. Explodiert nur bei massivem Überschuss.
        arrow_strength = np.clip((ion_mass - 0.7) * 0.8, 0.1, 1.0)
        edge_widths.append(1.0 + (arrow_strength * 5.0))
        
        if arrow_strength >= 0.70: edge_colors.append('#1b5e20') 
        elif arrow_strength >= 0.30: edge_colors.append('#4caf50') 
        else: edge_colors.append('#e8f5e9') # Unauffällig blassgrün

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
    st.markdown("🟢 **Grüner Knoten:** Perfekte Balance (85 % – 115 % Deckung).")
    st.markdown("🟡 **Gelber Knoten:** Warnbereich! Leichter Mangel oder beginnender Überschuss.")
    st.markdown("🔴 **Roter Knoten:** Alarm! Akuter Mangel ODER toxischer Überschuss (das Element flutet die Pflanze).")

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
