# nrw_geotools/callbacks.py
from IPython.display import clear_output as ipython_clear_output

# Import core logic functions from other modules
from .wfs_handler import discover_feature_types, fetch_wfs_data
from .feature_manager import handle_draw_control_actions # General handler
from .feature_manager import (
    on_geojson_feature_click_callback_base,
    keep_selected_features,
    clear_selection,
    remove_selected_features
)
from .feature_editor import (
    start_edit_selected_feature,
    apply_feature_edits,
    cancel_feature_edits
)
from .feature_cutter import (
    start_cut_selected_features,
    cancel_cut_operation, # This is the fixed import name
    _cutting_mode_draw_handler # This is the specialized cutter draw logic
)
from .file_operations import save_selected_as_gml
from . import config as app_config
from . import state as app_state # Import app_state here


# --- Wrapper callback functions ---

# WFS Callbacks
def on_discover_button_clicked(app_context):
    discover_feature_types(app_context)

def on_fetch_data_button_clicked(app_context):
    fetch_wfs_data(app_context)

# Feature Management Callbacks
def master_on_draw_handler(draw_control_instance, action, geo_json, app_context):
    # Check app_state directly without needing to pass it everywhere if it's imported
    # Or ensure app_context['state'] is used if preferred. Let's use app_context['state'] for consistency.
    current_app_state = app_context['state']

    if current_app_state.is_editing_feature:
        # Editing mode has its own way of handling draw control data (usually through m.draw_control.data directly)
        # The general draw handler should probably ignore 'created' events during an active edit session.
        # The 'edited' events from the toolbar are still useful.
        if action == 'edited':
             with app_context['widgets']['status_output_widget']:
                 print(f"Draw control: action='edited' during feature edit. Geometry: {geo_json.get('geometry', {}).get('type')}")
        return # Or handle specific edit-related draw events if necessary

    elif current_app_state.is_cutting_operation_active and current_app_state._cutting_draw_handler_active_flag:
        # If in cutting mode, delegate to the cutting draw handler
        _cutting_mode_draw_handler(draw_control_instance, action, geo_json, app_context)
    else:
        # Otherwise, use the general feature creation handler
        handle_draw_control_actions(draw_control_instance, action, geo_json, app_context)

# This function helps create the specific lambda needed for on_click events for GeoJSON layers
def get_geojson_click_handler(app_context, layer_name_for_handler):
    return lambda feature, **kwargs: on_geojson_feature_click_callback_base(
        feature, layer_name_for_handler, kwargs, app_context
    )

def on_keep_selected_button_clicked(app_context):
    keep_selected_features(app_context)

def on_clear_selection_button_clicked(app_context):
    clear_selection(app_context)

def on_remove_selected_button_clicked(app_context):
    remove_selected_features(app_context)

# Feature Editing Callbacks
def on_edit_selected_feature_button_clicked(app_context):
    start_edit_selected_feature(app_context)

def on_apply_feature_edits_button_clicked(app_context):
    apply_feature_edits(app_context)

def on_cancel_feature_edits_button_clicked(app_context):
    cancel_feature_edits(app_context)

# Feature Cutting Callbacks
def on_cut_selected_button_clicked(app_context):
    start_cut_selected_features(app_context) # This will register _cutting_mode_draw_handler

def on_cancel_cut_button_clicked(app_context):
    cancel_cut_operation(app_context)

# Special draw handler for cutting mode
def cutting_draw_handler_wrapper(app_context):
    # This returns the actual handler function that ipyleaflet expects,
    # but with app_context baked in.
    def actual_handler(control_instance, action, geo_json):
        _cutting_mode_draw_handler(control_instance, action, geo_json, app_context) # This looks good
    return actual_handler


# File Operations Callbacks
def on_save_gml_button_clicked(app_context):
    save_selected_as_gml(app_context)

# You might need a dummy function for buttons that don't have an action yet
def dummy_callback(app_context):
    w = app_context['widgets']
    with w['status_output_widget']:
        ipython_clear_output(wait=True)
        print("This button's action is not yet fully implemented in the new package structure.")