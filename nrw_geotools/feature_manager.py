import ipyleaflet
import uuid
import copy
import os
import geopandas as gpd # For saving kept features

from . import config as app_config
from . import state as app_state
from .ui_manager import update_all_button_states
from IPython.display import clear_output as ipython_clear_output

# This is the base function that will be wrapped by lambdas for specific layers
def on_geojson_feature_click_callback_base(feature, layer_name, event_details, app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']
    editing_status_output_widget = widgets['editing_status_output_widget']

    if app_state.is_editing_feature or app_state.is_cutting_operation_active:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print("Apply or cancel current edit/cut operation before selecting other features.")
        return

    if not isinstance(feature, dict) or 'properties' not in feature or \
       not isinstance(feature.get('properties'), dict) or \
       '_temp_id' not in feature.get('properties', {}):
        with status_output_widget:
            print(f"Warn: Click on malformed feature in '{layer_name}'.")
        return

    event_temp_id = feature['properties']['_temp_id']
    layer_object = m.find_layer(layer_name)
    if not layer_object or not isinstance(layer_object, ipyleaflet.GeoJSON):
        with status_output_widget:
            print(f"Error: Could not find GeoJSON layer '{layer_name}'.")
        return

    current_layer_features_list = list(layer_object.data.get('features', []))
    target_feature_from_data = None
    target_feature_index = -1
    for i, f_in_data in enumerate(current_layer_features_list):
        if isinstance(f_in_data, dict) and 'properties' in f_in_data and \
           isinstance(f_in_data['properties'], dict) and f_in_data['properties'].get('_temp_id') == event_temp_id:
            target_feature_from_data = f_in_data
            target_feature_index = i
            break
    
    if not target_feature_from_data:
        with status_output_widget:
            print(f"Warn: No feature with _temp_id {event_temp_id} in {layer_name} data. Map object might be out of sync.")
        return

    if layer_name not in app_state.selected_features_by_layer:
        app_state.selected_features_by_layer[layer_name] = {}
        app_state.original_styles_by_layer[layer_name] = {}

    modified_feature_for_update = copy.deepcopy(target_feature_from_data)
    if event_temp_id in app_state.selected_features_by_layer[layer_name]:
        del app_state.selected_features_by_layer[layer_name][event_temp_id]
        original_style = app_state.original_styles_by_layer[layer_name].pop(event_temp_id, copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE))
        modified_feature_for_update['properties']['style'] = original_style
    else:
        app_state.selected_features_by_layer[layer_name][event_temp_id] = copy.deepcopy(target_feature_from_data)
        app_state.original_styles_by_layer[layer_name][event_temp_id] = copy.deepcopy(target_feature_from_data['properties'].get('style', copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)))
        modified_feature_for_update['properties']['style'] = copy.deepcopy(app_config.SELECTED_STYLE)
    
    current_layer_features_list[target_feature_index] = modified_feature_for_update
    layer_object.data = {"type": "FeatureCollection", "features": current_layer_features_list} # This triggers map update
    update_all_button_states(app_context)


def handle_draw_control_actions(draw_control_instance, action, geo_json, app_context):
    # m = app_context['m'] # Not directly used, but app_state.drawn_features_layer is
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']
    # app_state.drawn_features_layer is assumed to be initialized and valid
    
    if app_state.is_editing_feature:
        return
    if app_state.is_cutting_operation_active and app_state._cutting_draw_handler_active_flag: # Check flag for cutting draw
        return

    if action == 'created':
        with status_output_widget:
            print(f"Draw control: action='created'. Geometry type: {geo_json['geometry']['type']}")

        if app_state.drawn_features_layer is None: # Should have been initialized
             from .map_setup import initialize_drawn_features_layer_on_map # Lazy import
             from .callbacks import get_drawn_features_click_handler # Lazy import for click handler
             # This is a fallback, ideally it's initialized once.
             # The click handler needs to be constructed carefully with app_context.
             app_state.drawn_features_layer = initialize_drawn_features_layer_on_map(
                 app_context['m'], 
                 get_drawn_features_click_handler(app_context) # Pass app_context to handler factory
             )
             if app_state.drawn_features_layer is None:
                print("CRITICAL ERROR: drawn_features_layer is None after re-initialization attempt!")
                return

        new_feature = copy.deepcopy(geo_json)
        new_feature['properties'] = new_feature.get('properties', {})
        new_feature['properties']['_temp_id'] = str(uuid.uuid4())
        new_feature['properties']['style'] = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
        
        updated_features_list = list(app_state.drawn_features_layer.data.get('features', []))
        updated_features_list.append(new_feature)
        
        app_state.drawn_features_layer.data = {
            "type": "FeatureCollection",
            "features": updated_features_list
        }
        
        draw_control_instance.clear() # Clear the drawing from the draw_control's temporary layer
        
        with status_output_widget:
            print(f"Feature with _temp_id {new_feature['properties']['_temp_id']} added to '{app_config.DRAWN_FEATURES_LAYER_NAME}'. Layer now has {len(updated_features_list)} features.")
        update_all_button_states(app_context)

    elif action == 'edited':
        with status_output_widget:
             print(f"Draw control: action='edited' (geometry: {geo_json.get('geometry', {}).get('type')}). Internal draw_control edit.")
             # Note: This 'edited' is from the main draw control, not our feature editor
             
    elif action == 'deleted':
        with status_output_widget:
            print("Draw control: action='deleted'. Drawing deleted/cancelled from toolbar.")
        draw_control_instance.clear()


def keep_selected_features(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']

    with status_output_widget:
        ipython_clear_output(wait=True)
        print("Processing 'Keep Selected'...")
        kept_any = False
        layers_to_remove_objs = []
        current_relevant_layer_names = [
            name for name in m.get_layer_names() 
            if name.startswith("WFS:") or name == app_config.DRAWN_FEATURES_LAYER_NAME
        ]

        for lname_iter in current_relevant_layer_names:
            layer_obj_iter = m.find_layer(lname_iter)
            if not layer_obj_iter or not isinstance(layer_obj_iter, ipyleaflet.GeoJSON):
                continue

            if lname_iter in app_state.selected_features_by_layer and app_state.selected_features_by_layer[lname_iter]:
                kept_feats_this_layer = []
                for temp_id_kept, _ in app_state.selected_features_by_layer[lname_iter].items():
                    current_feature_on_map = None
                    for f_map in layer_obj_iter.data['features']: # Iterate through features currently on map
                        if f_map['properties'].get('_temp_id') == temp_id_kept:
                            current_feature_on_map = copy.deepcopy(f_map)
                            break
                    if current_feature_on_map:
                        # Revert to original style before selection, or default if not found
                        original_style_for_this_feature = app_state.original_styles_by_layer[lname_iter].get(
                            temp_id_kept, copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                        )
                        current_feature_on_map['properties']['style'] = original_style_for_this_feature
                        kept_feats_this_layer.append(current_feature_on_map)
                
                layer_obj_iter.data = {"type": "FeatureCollection", "features": kept_feats_this_layer}
                
                if lname_iter.startswith("WFS:"):
                    sane_kept_name = lname_iter.replace('WFS: ', '').replace(':', '_').replace('/', '_')
                    bbox_fname_part = (
                        f"bbox_{app_state.min_x_25832_fname_global:.0f}_{app_state.min_y_25832_fname_global:.0f}"
                        if app_state.min_x_25832_fname_global is not None else "filtered"
                    )
                    kept_fpath = os.path.join(app_config.DOWNLOAD_DIR, f"kept_{sane_kept_name}_{bbox_fname_part}.geojson")
                    try:
                        gpd.GeoDataFrame.from_features(kept_feats_this_layer, crs="EPSG:4326").to_file(
                            kept_fpath, driver="GeoJSON", encoding='utf-8'
                        )
                        print(f"  Saved kept WFS for {lname_iter} to {kept_fpath}")
                    except Exception as e_sk:
                        print(f"  Warn: Save kept WFS fail for {lname_iter}: {e_sk}")
                else: # Drawn features layer
                     print(f"  Kept selected features in '{lname_iter}'.")
                kept_any = True
            else: # No selection in this layer
                if lname_iter.startswith("WFS:"): # Remove WFS layer if nothing selected in it
                    layers_to_remove_objs.append(layer_obj_iter)
                elif lname_iter == app_config.DRAWN_FEATURES_LAYER_NAME and not layer_obj_iter.data['features']:
                    # Optionally clear drawn features layer if empty, or leave it
                    pass 
        
        for layer_rem_obj in layers_to_remove_objs:
            if layer_rem_obj in m.layers: # Check if still on map
                m.remove_layer(layer_rem_obj)
                print(f"  Removed '{layer_rem_obj.name}' (WFS layer with no selections).")
        
        print("Kept selected features and updated layers." if kept_any else "No features selected; WFS layers with no selections cleared.")
        app_state.selected_features_by_layer.clear()
        app_state.original_styles_by_layer.clear()
    update_all_button_states(app_context)


def clear_selection(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']

    with status_output_widget:
        ipython_clear_output(wait=True)
        if not app_state.selected_features_by_layer:
            print("No features are currently selected.")
            update_all_button_states(app_context)
            return

        changed_any_layer = False
        for lname_clear, sel_ids_in_layer_clear in app_state.selected_features_by_layer.items():
            if not sel_ids_in_layer_clear:
                continue
            
            layer_obj_clear = m.find_layer(lname_clear)
            if layer_obj_clear and isinstance(layer_obj_clear, ipyleaflet.GeoJSON):
                new_data_features_list = list(layer_obj_clear.data['features']) # Make a mutable copy
                changed_in_this_layer = False
                for i_feat_clear, f_in_l_clear in enumerate(new_data_features_list):
                    temp_id_clear = f_in_l_clear['properties'].get('_temp_id')
                    if temp_id_clear and temp_id_clear in sel_ids_in_layer_clear:
                        # Revert to the style stored when it was selected
                        original_style_to_revert = app_state.original_styles_by_layer[lname_clear].get(
                            temp_id_clear, copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                        )
                        reverted_feature_dict = copy.deepcopy(f_in_l_clear)
                        reverted_feature_dict['properties']['style'] = original_style_to_revert
                        new_data_features_list[i_feat_clear] = reverted_feature_dict
                        changed_in_this_layer = True
                
                if changed_in_this_layer:
                    layer_obj_clear.data = {"type": "FeatureCollection", "features": new_data_features_list}
                    changed_any_layer = True
        
        app_state.selected_features_by_layer.clear()
        app_state.original_styles_by_layer.clear()
        print("Selection cleared and styles reverted." if changed_any_layer else "No effective selections to clear.")
    update_all_button_states(app_context)


def remove_selected_features(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']

    with status_output_widget:
        ipython_clear_output(wait=True)
        if not app_state.selected_features_by_layer:
            print("No features are currently selected to remove.")
            update_all_button_states(app_context)
            return

        removed_count = 0
        affected_layers = set()
        
        # Iterate over a copy because we are modifying app_state.selected_features_by_layer implicitly later by clearing it
        selected_features_copy = copy.deepcopy(app_state.selected_features_by_layer)

        for layer_name, sel_ids_in_layer in selected_features_copy.items():
            if not sel_ids_in_layer:
                continue
            
            layer_obj = m.find_layer(layer_name)
            if layer_obj and isinstance(layer_obj, ipyleaflet.GeoJSON):
                current_features_on_map = list(layer_obj.data.get('features', []))
                ids_to_remove_this_layer = set(sel_ids_in_layer.keys())
                
                new_features_for_layer = [
                    f for f in current_features_on_map 
                    if f['properties'].get('_temp_id') not in ids_to_remove_this_layer
                ]
                
                if len(new_features_for_layer) < len(current_features_on_map):
                    layer_obj.data = {"type": "FeatureCollection", "features": new_features_for_layer}
                    removed_count_this_layer = len(current_features_on_map) - len(new_features_for_layer)
                    removed_count += removed_count_this_layer
                    affected_layers.add(layer_name)
                    print(f"  Removed {removed_count_this_layer} feature(s) from layer '{layer_name}'.")
            else:
                print(f"  Warning: Layer '{layer_name}' not found or not GeoJSON, cannot remove features.")
        
        app_state.selected_features_by_layer.clear()
        app_state.original_styles_by_layer.clear()
        
        if removed_count > 0:
            print(f"Total {removed_count} selected feature(s) removed from the map.")
        else:
            print("No features were effectively removed (e.g., already removed or layer not found).")
            
    update_all_button_states(app_context)