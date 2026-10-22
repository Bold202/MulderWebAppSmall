import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Mulder Environment App", layout="wide")

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

ideal_targets = {'Ca': 90.0, 'Mg': 30.0}

st.sidebar.header("Umwelt-Parameter")
ph_value = st.sidebar.slider("pH-Level", 4.0, 9.0, 6.5, 0.1)
temp_value = st.sidebar.slider("Temperatur (°C)", 5.0, 35.0, 22.0, 1.0)
light_value = st.sidebar.slider("Lichtintensität (%)", 0, 100, 100, 5)

st.sidebar.header("Steuerung")
combined_view = st.sidebar.checkbox("Leitungswasser-Kombination aktivieren", value=False)

st.sidebar.subheader("Leitungswasser-Werte")
st.sidebar.caption("Ideal: Ca 90 mg/L | Mg 30 mg/L (3:1 Verhältnis)")

inputs = {}
col1, col2 = st.sidebar.columns(2)
with col1:
    inputs['Ca'] = st.number_input("Ca (Calcium)", min_value=0.0, value=90.0, step=1.0)
with col2:
    inputs['Mg'] = st.number_input("Mg (Magnesium)", min_value=0.0, value=30.0, step=1.0)

for n in nutrients:
    if n not in inputs: inputs[n] = ideal_targets.get(n, 100.0)

G = nx.DiGraph()
G.add_nodes_from(nutrients)
G.add_edges_from(antagonisms_strong, type='antagonism_strong')
G.add_edges_from(antagonisms_weak, type='antagonism_weak')
G.add_edges_from(synergies, type='synergism')

pos = nx.circular_layout(G)
node_sizes, node_colors, edge_colors, edge_widths = [], [], [], []

for node in G.nodes():
    env_factor = get_availability(node, ph_value, temp_value, light_value)
    target = ideal_targets.get(node, 100.0)
    input_factor = np.clip(inputs[node] / target, 0.0, 1.5) 
    
    actual_val = env_factor * input_factor if combined_view else env_factor
    
    node_sizes.append(2000 + (actual_val * 4000))
    if actual_val >= 0.75: node_colors.append('#388e3c') 
    elif actual_val >= 0.45: node_colors.append('#fbc02d')
    else: node_colors.append('#d32f2f')

ph_stress = get_ph_zone_stress(ph_value)

for u, v, data in G.edges(data=True):
    env_factor = get_availability(u, ph_value, temp_value, light_value)
    target = ideal_targets.get(u, 100.0)
    input_factor = np.clip(inputs[u] / target, 0.0, 1.5)
    u_actual = env_factor * input_factor if combined_view else env_factor
    
    arrow_strength = np.clip(ph_stress * u_actual, 0.1, 1.0)
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

fig, ax = plt.subplots(figsize=(13, 13))

nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color=node_colors, edgecolors='#222222', linewidths=2)
nx.draw_networkx_labels(G, pos, ax=ax, font_size=13, font_weight='bold')
nx.draw_networkx_edges(G, pos, ax=ax, node_size=node_sizes, edge_color=edge_colors, width=edge_widths, arrowsize=25, connectionstyle='arc3,rad=0.15', arrows=True)

fig.patch.set_facecolor('#ffffff')
ax.axis('off')

st.title("Dynamisches Nährstoff-Netzwerk")
if combined_view:
    st.subheader(f"Status: Kombiniert (pH {ph_value} | {temp_value}°C | Licht {light_value}%)")
else:
    st.subheader(f"Status: Umweltfaktoren (pH {ph_value} | {temp_value}°C | Licht {light_value}%)")
    
st.pyplot(fig)

# --- NEU: LEGENDE ---
st.markdown("---")
st.markdown("### 📊 Legende zur Interpretation")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Antagonismen (Blockaden)")
    st.markdown("🔴 **Roter Pfeil (Toxisch):** Massive Blockade des Zielelements. Tritt bei extremen pH-Werten oder sehr starker Überdosierung auf. Akuter Handlungsbedarf.")
    st.markdown("🟡 **Gelber Pfeil (Warnbereich):** Beginnende Konkurrenz durch unvorteilhafte pH-Werte oder leichte Nährstoffungleichgewichte. Das System gerät unter Stress.")
    st.markdown("⚪ **Grauer Pfeil (Steuernd):** Natürlicher Antagonismus im pH-Wohlfühlbereich. Völlig unbedenklich. Das System reguliert das Wachstum sanft selbst.")

with col2:
    st.markdown("#### Synergismen (Förderung) & Masse")
    st.markdown("🟢 **Hell-/Mittelgrüner Pfeil:** Gesunder Synergismus. Die Aufnahme des Zielelements wird optimal und harmonisch unterstützt.")
    st.markdown("🟩 **Dicker dunkelgrüner Pfeil:** Starker Synergismus. **Achtung:** Es besteht die Gefahr der Überdosierung oder toxischen Anreicherung des geförderten Elements, da die Schleusen unkontrolliert geöffnet werden!")
    st.markdown("📏 **Pfeildicke (Druck & Masse):** Je dicker der Pfeil, desto massiver ist der Einfluss (die pure Ionenmasse), die von einem Element auf das andere drückt.")

# --- PRIVATER FOOTER ---
st.markdown("---")
st.markdown("### Über dieses Tool")
st.markdown("Dieses interaktive Mulder-Diagramm veranschaulicht die Ionenkonkurrenz und Nährstoffverfügbarkeit in Echtzeit. Die Pfeildicke und -farbe reagieren dynamisch auf kritische pH-Verschiebungen und Temperatureinflüsse.")
st.markdown("**Kontakt:** Discord `@BonsaiDaddy`")
st.caption("⚖️ **Hinweis:** Dies ist ein rein privates Hobby-Projekt. Das Tool dient ausschließlich Bildungszwecken und simuliert chemische Tendenzen. Es ersetzt keine Laboranalyse und es wird keine Haftung für Pflanzenschäden übernommen.")

st.markdown("---")
st.caption("⚖️ **Rechtlicher Hinweis:** Dieses Tool dient ausschließlich Bildungs- und Veranschaulichungszwecken. Es simuliert thermodynamische und chemische Tendenzen, ersetzt jedoch keine professionelle Boden- oder Laboranalyse. Es wird keine Haftung für Ernteausfälle oder Pflanzenschäden übernommen.")
#st.caption("[Impressum](https://deine-hauptseite.de/impressum) | [Datenschutz](https://deine-hauptseite.de/datenschutz)")
