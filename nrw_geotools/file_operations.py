# nrw_geotools/file_operations.py

import os
import copy
import geopandas as gpd
import ipyleaflet

# Import from within the package
from . import config as app_config
from . import state as app_state
from . import utils # For sanitize_filename
from .ui_manager import update_all_button_states
from IPython.display import clear_output as ipython_clear_output # Added for consistency
from .feature_manager import clear_selection # To call after successful save

def save_selected_as_gml(app_context):
    m = app_context['m'] # Map object
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']
    gml_filename_input_widget = widgets['gml_filename_input']

    with status_output_widget:
        ipython_clear_output(wait=True)
        
        has_any_selection = False
        for sel_dict in app_state.selected_features_by_layer.values():
            if sel_dict:
                has_any_selection = True
                break
        
        if not has_any_selection:
            print("No features are currently selected to save.")
            update_all_button_states(app_context)
            return

        filename_base = gml_filename_input_widget.value.strip()
        if not filename_base:
            print("Error: Please enter a filename for the GML output.")
            return

        sane_filename_base = utils.sanitize_filename(filename_base)
        if not sane_filename_base or (sane_filename_base == "output_features" and filename_base != "output_features"): # Check if sanitization changed it to default
            print(f"Warning: Invalid filename, using default: '{sane_filename_base}'")
            # gml_filename_input_widget.value = sane_filename_base # Optional

        gml_filename_with_ext = f"{sane_filename_base}.gml" if not sane_filename_base.lower().endswith(".gml") else sane_filename_base
        gml_filepath = os.path.join(app_config.GML_OUTPUT_DIR, gml_filename_with_ext)

        all_selected_geojson_features = []
        for layer_name, sel_dict in app_state.selected_features_by_layer.items():
            if not sel_dict:
                continue
            
            layer_obj = m.find_layer(layer_name)
            if layer_obj and isinstance(layer_obj, ipyleaflet.GeoJSON): 
                for feature_on_map in layer_obj.data.get('features', []):
                    if feature_on_map['properties'].get('_temp_id') in sel_dict:
                        all_selected_geojson_features.append(copy.deepcopy(feature_on_map))
            elif layer_obj: # Layer exists but is not GeoJSON
                 print(f"Warning: Layer '{layer_name}' for selection found but is not a GeoJSON layer. Type: {type(layer_obj)}")
            else: # Layer not found
                print(f"Warning: Layer '{layer_name}' for selection not found on map.")


        if not all_selected_geojson_features:
            print("Error: Could not retrieve selected features (e.g., layers removed or data inconsistent).")
            update_all_button_states(app_context)
            return

        try:
            gdf_selected = gpd.GeoDataFrame.from_features(all_selected_geojson_features, crs="EPSG:4326")
            
            gdf_for_gml = gdf_selected.copy()
            if 'style' in gdf_for_gml.columns:
                gdf_for_gml = gdf_for_gml.drop(columns=['style'])
            # if '_temp_id' in gdf_for_gml.columns:
            #     gdf_for_gml = gdf_for_gml.drop(columns=['_temp_id'])

            print(f"Reprojecting {len(gdf_for_gml)} features to EPSG:25832 for GML output...")
            gdf_selected_25832 = gdf_for_gml.to_crs("EPSG:25832")

            print(f"Attempting to save to GML file: {gml_filepath}")
            os.makedirs(app_config.GML_OUTPUT_DIR, exist_ok=True)
            
            gdf_selected_25832.to_file(gml_filepath, driver="GML")
            
            print(f"Successfully saved {len(gdf_selected_25832)} selected feature(s) to '{gml_filepath}' in EPSG:25832.")
            
            clear_selection(app_context)

        except Exception as e_gml_save:
            print(f"Error saving GML file: {type(e_gml_save).__name__}: {e_gml_save}")
            update_all_button_states(app_context)