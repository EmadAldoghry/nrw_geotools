import os
import uuid

# --- Configuration ---
MAP_CENTER_NRW = [51.47, 7.55]
INITIAL_ZOOM = 10
WMS_DISPLAY_MAX_ZOOM = 24
WMS_SERVICE_URL = "https://www.wms.nrw.de/geobasis/wms_nw_dop"
DOWNLOAD_DIR = "wfs_downloaded_data"
GML_OUTPUT_DIR = "gml_output"
DRAWN_FEATURES_LAYER_NAME = "User Drawn Features"
MAX_FEATURES_PER_TYPE_FETCH = 50

WFS_CAPABILITIES_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_aaa-modell-basiert?SERVICE=WFS&REQUEST=GetCapabilities"
WFS_GETFEATURE_BASE_URL = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_aaa-modell-basiert"

SELECTED_STYLE = {'color': 'yellow', 'weight': 3, 'fillColor': 'yellow', 'fillOpacity': 0.7}
DEFAULT_FEATURE_STYLE = {'color': '#3388ff', 'weight': 2, 'fillOpacity': 0.1, 'opacity': 0.6}
EDIT_MODE_STYLE = {'color': 'lime', 'weight': 4, 'fillColor': 'lime', 'fillOpacity': 0.5, 'dashArray': '8, 8', 'clickable': True}
HIDDEN_STYLE = {'opacity': 0, 'fillOpacity': 0, 'weight': 0, 'stroke': False, 'fill': False, 'clickable': False}

FETCH_ALL_BUTTON_LABEL = "Fetch ALL Discovered WFS Features"

def ensure_directories():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    if not os.path.exists(GML_OUTPUT_DIR):
        os.makedirs(GML_OUTPUT_DIR)

ensure_directories()