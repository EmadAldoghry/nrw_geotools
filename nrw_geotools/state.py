      
# --- Global state for the application ---

# WFS related
all_discovered_feature_types = []

# Feature selection
selected_features_by_layer = {}
original_styles_by_layer = {}

# Editing state
is_editing_feature = False
feature_being_edited_info = None  # Dict: {'layer_name', '_temp_id', 'original_feature_dict'}

# Cutting state
is_cutting_operation_active = False
features_to_be_cut_info = []  # List of dicts: {'layer_name', '_temp_id', 'feature_dict'}
_cutting_draw_handler_active_flag = False # Internal flag for draw handler management

# Drawn features layer reference
drawn_features_layer = None # Will hold the ipyleaflet.GeoJSON layer object

# For GML Filename context (bbox part)
min_x_25832_fname_global = None
min_y_25832_fname_global = None

    