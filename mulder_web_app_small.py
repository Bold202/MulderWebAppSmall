import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Mulder Diagnose Tool", layout="wide")

# Prominenter Hinweis für Handy-Nutzer ganz oben!
st.info("📱 **Setup-Menü:** Tippe oben links auf den Pfeil ( **>** ), um pH-Wert, Blütetag und Nährstoffe einzustellen.")

def get_availability(nutrient, ph, temp, light):
    if nutrient in ['N', 'K', 'S']: base = np.clip((ph - 4.5) / 1.5, 0.1, 1.0)
    elif nutrient == 'P': base = np.clip(1.0 - abs(6.5 - ph) * 0.7, 0.1, 1.0)
    elif nutrient in ['Ca', 'Mg']: base = np.clip((ph - 5.0) / 1.5, 0.1, 1.0)
    elif nutrient == 'Fe': base = np.clip(1.0 - (ph - 5.5) / 2.0, 0.1, 1.0)
    elif nutrient in ['Mn', 'Zn', 'Cu', 'B']: base = np.clip(1.0 - (ph - 6.0) / 2.5, 0.1, 1.0)
    elif nutrient == 'Mo': base = np.clip((ph - 5.5) / 1.5, 0.1, 1.0)
    elif nutrient == 'Na': base = 0.8
    else: base = 0.5
        
    light_factor = np.clip(light / 100.0, 0.3, 1.2)
    
    if nutrient == 'P': return np.clip(base * np.clip((temp - 8.0) / 10.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient in ['N', 'S']: return np.clip(base * np.clip((temp - 5.0) / 15.0, 0.1, 1.0), 0.1, 1.0)
    elif nutrient == 'Mg': return np.clip(base * light_factor, 0.1, 1.0)
    elif nutrient == 'Ca': return np.clip(base * light_factor * np.clip(temp / 25.0, 0.3, 1.0), 0.1, 1.0)
    else: return np.clip(base * np.clip((temp + 5.0) / 30.0, 0.2, 1.0), 0.1, 1.0)

def get_demand(nutrient, day):
    """ Dynamischer Pflanzenbedarf je nach Blütetag (0-75) """
    if nutrient == 'N': 
        return np.clip(1.2 - (day / 70.0) * 0.8, 0.3, 1.2) # Fällt kontinuierlich ab
    elif nutrient == 'Ca': 
        return 0.8 + np.sin(np.clip(day / 30.0, 0, 1) * np.pi) * 0.6 # Peak Tag 10-20 (Stretch)
    elif nutrient == 'P': 
        return 0.7 + np.sin(np.clip((day - 10)/50.0, 0, 1) * np.pi) * 0.5 # Peak Tag 30-40
    elif nutrient == 'Mg': 
        return 0.8 + np.sin(np.clip((day - 10) / 40.0, 0, 1) * np.pi) * 0.4 # Peak Tag 25-35
    elif nutrient == 'K': 
        return 0.8 + np.sin(np.clip((day - 20)/50.0, 0, 1) * np.pi) * 0.6 # Peak Tag 40-55
    else: 
        return 1.0 # Mikronährstoffe bleiben konstant 1.0

def get_ph_zone_stress(ph):
    if 6.0 <= ph <= 7.0: return 0.3 + 0.15 * (abs(ph - 6.5) / 0.5) 
    elif 5.5 <= ph < 6.0: return 0.45 + 0.3 * ((6.0 - ph) / 0.5)
    elif 7.0 < ph <= 7.5: return 0.45 + 0.3 * ((ph - 7.0) / 0.5)
    elif ph < 5.5: return 0.75 + 0.25 * (min(5.5 - ph, 1.5) / 1.5)
    else: return 0.75 + 0.25 * (min(ph - 7.5, 2.5) / 2.5)

nutrients = ['N', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo', 'Na']
antagonisms_strong = [('Ca','K'), ('Ca','Mg'), ('Ca','P'), ('Ca','Zn'), ('Ca','Fe'), ('Ca','Mn'), 
                      ('K','Ca'), ('K','Mg'), ('Mg','Ca'), ('Mg','K'), ('P','K'), ('P','Ca'), 
                      ('P','Zn'), ('P','Cu'), ('N','K'), ('N','B'), ('Zn','Fe'), ('Fe','P'), ('Na','K'), ('Na','Ca'), ('Na','Mg')]
antagonisms_weak = [('Mn','Fe'), ('Fe','Mn'), ('Fe','Zn'), ('Cu','Zn'), ('Cu','Fe'), ('Cu','Mn')]
synergies = [('N','Mg'), ('Mg','N'), ('Mg','P'), ('P','Mg'), ('K','Fe'), ('K','Mn'), ('Mn','K')]

# --- SIDEBAR SETUP ---
st.sidebar.header("🌱 Wachstumsphase")
bluetetag = st.sidebar.slider("Blütetag", 0, 75, 15, 1)

st.sidebar.header("💧 Nährstoff-Zufuhr")
st.sidebar.caption("Das agronomische Idealmaß für Ca:Mg liegt bei ca. 3.0")
camg_ratio = st.sidebar.slider("Ca:Mg Verhältnis (Gießwasser)", 1.0, 6.0, 3.0, 0.1)

st.sidebar.header("🌡️ Umwelt-Parameter")
ph_value = st.sidebar.slider("pH-Level", 4.0, 9.0, 6.5, 0.1)
temp_value = st.sidebar.slider("Temperatur (°C)", 5.0, 35.0, 22.0, 1.0)
light_value = st.sidebar.slider("Lichtintensität (%)", 0, 100, 100, 5)


# --- BERECHNUNG ---
G = nx.DiGraph()
G.add_nodes_from(nutrients)
G.add_edges_from(antagonisms_strong, type='antagonism_strong')
G.add_edges_from(antagonisms_weak, type='antagonism_weak')
G.add_edges_from(synergies, type='synergism')

pos = nx.circular_layout(G)
node_sizes, node_colors, edge_colors, edge_widths = [], [], [], []

for node in G.nodes():
    # 1. Was ist umweltbedingt verfügbar?
    env_factor = get_availability(node, ph_value, temp_value, light_value)
    
    # 2. Was füttert der User? (Normiert auf das 3:1 Verhältnis)
    if node == 'Ca': supply = (camg_ratio / 3.0)
    elif node == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
        
    # 3. Was braucht die Pflanze gerade?
    demand = get_demand(node, bluetetag)
    
    # 4. Tatsächliche Sättigung = (Verfügbarkeit * Zufuhr) / Bedarf
    saturation = np.clip((env_factor * supply) / demand, 0.1, 1.5)
    
    node_sizes.append(2000 + (saturation * 4000))
    if saturation >= 0.8: node_colors.append('#388e3c') 
    elif saturation >= 0.5: node_colors.append('#fbc02d')
    else: node_colors.append('#d32f2f')

ph_stress = get_ph_zone_stress(ph_value)

for u, v, data in G.edges(data=True):
    env_factor = get_availability(u, ph_value, temp_value, light_value)
    if u == 'Ca': supply = (camg_ratio / 3.0)
    elif u == 'Mg': supply = (3.0 / camg_ratio)
    else: supply = 1.0
    demand = get_demand(u, bluetetag)
    
    u_saturation = np.clip((env_factor * supply) / demand, 0.1, 1.5)
    
    # Pfeilstärke wächst mit dem pH-Stress UND der Sättigungsmasse des Ausgangselements
    arrow_strength = np.clip(ph_stress * (u_saturation / 1.5), 0.1, 1.0)
    edge_widths.append(2.0 + (arrow_strength * 6.0))
    
    if data['type'] == 'antagonism_strong':
        if arrow_strength >= 0.7: edge_colors.append('#d32f2f')
        elif arrow_strength >= 0.45: edge_colors.append('#fbc02d')
        else: edge_colors.append('#9e9e9e')
    elif data['type'] == 'antagonism_weak':
        if arrow_strength >= 0.7: edge_colors.append('#757575') 
        elif arrow_strength >= 0.45: edge_colors.append('#9e9e9e')
        else: edge_colors.append('#cfcfcf') 
    elif data['type'] == 'synergism':
        if arrow_strength >= 0.7: edge_colors.append('#2e7d32') 
        elif arrow_strength >= 0.45: edge_colors.append('#4caf50') 
        else: edge_colors.append('#a5d6a7') 

# --- MAIN UI ---
st.title("Dynamisches Nährstoff-Diagnosetool")
diagram_size = st.slider("🔍 Zoom / Diagrammgröße (für Handys anpassen)", 6, 20, 11, 1)

fig, ax = plt.subplots(figsize=(diagram_size, diagram_size))

nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color=node_colors, edgecolors='#222222', linewidths=2)
nx.draw_networkx_labels(G, pos, ax=ax, font_size=int(diagram_size * 1.1), font_weight='bold')
nx.draw_networkx_edges(G, pos, ax=ax, node_size=node_sizes, edge_color=edge_colors, width=edge_widths, arrowsize=int(diagram_size * 2), connectionstyle='arc3,rad=0.15', arrows=True)

fig.patch.set_facecolor('#ffffff')
ax.axis('off')
    
st.pyplot(fig)

# --- LEGENDE ---
st.markdown("---")
st.markdown("### 📊 Legende zur Diagnose")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Knoten (Sättigung vs. Bedarf)")
    st.markdown("🟢 **Grüner Knoten:** Das Element ist optimal verfügbar und deckt den exakten Bedarf der Pflanze am aktuellen Blütetag.")
    st.markdown("🟡 **Gelber Knoten:** Warnbereich! Der Bedarf steigt (z.B. Calcium im Stretch) oder die Umwelt blockiert das Element. Das System ist auf Kante genäht.")
    st.markdown("🔴 **Roter Knoten:** Akuter Mangel! Die Pflanze saugt das Element schneller leer, als es durch das Gießwasser (Ca:Mg Ratio) oder den pH-Wert nachgeliefert wird.")

with col2:
    st.markdown("#### Pfeile (Blockaden & Förderung)")
    st.markdown("🔴 **Roter Pfeil (Toxisch):** Massive Blockade des Zielelements durch gefährliche pH-Werte oder extreme Überdosierung.")
    st.markdown("🟡 **Gelber Pfeil (Warnbereich):** Beginnende Konkurrenz. Das System gerät unter Stress.")
    st.markdown("⚪ **Grauer Pfeil (Steuernd):** Natürlicher Antagonismus. Völlig unbedenklich, reguliert das Wachstum sanft.")
    st.markdown("🟩 **Dicker dunkelgrüner Pfeil:** Starker Synergismus. **Achtung:** Gefahr der Überdosierung des geförderten Elements!")

# --- PRIVATER FOOTER ---
st.markdown("---")
st.markdown("### Über dieses Tool")
st.markdown("Dieses Diagnosetool vergleicht die thermodynamische Verfügbarkeit (pH, Temp, Licht) und deine Zufuhr (Ca:Mg) mit den dynamischen Nährstoffbedürfnissen der Pflanze im Verlauf der Blütephase.")
st.markdown("**Kontakt:** Discord `@BonsaiDaddy`")
st.caption("⚖️ **Hinweis:** Dies ist ein privates Hobby-Projekt. Das Tool dient Bildungszwecken, simuliert chemische Tendenzen und ersetzt keine Laboranalyse. Keine Haftung für Pflanzenschäden.")
