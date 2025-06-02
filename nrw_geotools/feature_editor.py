# nrw_geotools/feature_editor.py

import copy
from IPython.display import clear_output as ipython_clear_output
import ipyleaflet # For isinstance checks

# Import from within the package
from . import config as app_config
from . import state as app_state
from .ui_manager import update_all_button_states

def start_edit_selected_feature(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    feature_to_edit_info = None
    selected_count = 0
    # Find the single selected feature
    for layer_name, features_in_layer in app_state.selected_features_by_layer.items():
        if features_in_layer:
            selected_count += len(features_in_layer)
            if len(features_in_layer) == 1 and feature_to_edit_info is None:
                temp_id = list(features_in_layer.keys())[0]
                layer_obj_check = m.find_layer(layer_name) # Check layer type here
                if layer_obj_check and isinstance(layer_obj_check, ipyleaflet.GeoJSON):
                    for f_on_map in layer_obj_check.data['features']:
                        if f_on_map['properties'].get('_temp_id') == temp_id:
                            feature_to_edit_info = {
                                'layer_name': layer_name,
                                '_temp_id': temp_id,
                                'feature_dict_on_map': copy.deepcopy(f_on_map)
                            }
                            break 
                if feature_to_edit_info and feature_to_edit_info.get('layer_name') == layer_name:
                    break
            elif len(features_in_layer) > 1: # More than one selected in a layer
                selected_count = 2 # Mark as more than one overall
                break
    
    if selected_count != 1 or not feature_to_edit_info:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            if selected_count == 0: print("No feature selected to edit.")
            elif selected_count > 1: print("Error: Select exactly one feature to edit.")
            else: print("Selected feature not found on map or its layer is not GeoJSON.")
        update_all_button_states(app_context)
        return

    app_state.is_editing_feature = True
    app_state.feature_being_edited_info = {
        'layer_name': feature_to_edit_info['layer_name'],
        '_temp_id': feature_to_edit_info['_temp_id'],
        'original_feature_dict': copy.deepcopy(feature_to_edit_info['feature_dict_on_map']),
    }

    feature_for_draw_control = copy.deepcopy(feature_to_edit_info['feature_dict_on_map'])
    feature_for_draw_control['properties']['style'] = copy.deepcopy(app_config.EDIT_MODE_STYLE)

    m.draw_control.clear()
    m.draw_control.data = [feature_for_draw_control]

    source_layer_obj = m.find_layer(feature_to_edit_info['layer_name'])
    if source_layer_obj and isinstance(source_layer_obj, ipyleaflet.GeoJSON): # Explicit check
        source_layer_data_features = list(source_layer_obj.data.get('features', []))
        found_in_source = False
        for i, f_dict in enumerate(source_layer_data_features):
            if f_dict['properties'].get('_temp_id') == feature_to_edit_info['_temp_id']:
                hidden_f_dict = copy.deepcopy(f_dict)
                hidden_f_dict['properties']['style'] = copy.deepcopy(app_config.HIDDEN_STYLE)
                source_layer_data_features[i] = hidden_f_dict
                found_in_source = True
                break
        if found_in_source:
            source_layer_obj.data = {"type": "FeatureCollection", "features": source_layer_data_features}
        # else: warning already handled if feature_to_edit_info couldn't be built
    elif source_layer_obj:
        print(f"Warning: Source layer {feature_to_edit_info['layer_name']} is not a GeoJSON layer, cannot hide feature.")


    with editing_status_output_widget:
        ipython_clear_output(wait=True)
        print(f"EDITING GEOMETRY for feature '{feature_to_edit_info['_temp_id']}' from layer '{feature_to_edit_info['layer_name']}'.")
        print("Use map's Draw Toolbar: 'Edit layers' tool, then click feature to move/reshape.")
        print("Click 'Apply Feature Edits' or 'Cancel Feature Edits' when done.")
    update_all_button_states(app_context)


def apply_feature_edits(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    if not app_state.is_editing_feature or not app_state.feature_being_edited_info:
        # ... (no change to this part) ...
        return

    edited_geometry_on_map = None
    if m.draw_control.data and len(m.draw_control.data) > 0:
        edited_geometry_on_map = m.draw_control.data[0]['geometry']
    
    if not edited_geometry_on_map:
        # ... (no change to this part) ...
        return

    original_info = app_state.feature_being_edited_info
    target_layer_obj = m.find_layer(original_info['layer_name'])

    if target_layer_obj and isinstance(target_layer_obj, ipyleaflet.GeoJSON): # Explicit check
        target_layer_data_features = list(target_layer_obj.data.get('features', []))
        found_and_updated = False
        for i, f_dict_target in enumerate(target_layer_data_features):
            if f_dict_target['properties'].get('_temp_id') == original_info['_temp_id']:
                final_updated_feature = copy.deepcopy(original_info['original_feature_dict'])
                final_updated_feature['geometry'] = edited_geometry_on_map
                final_updated_feature['properties']['style'] = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                target_layer_data_features[i] = final_updated_feature
                
                if original_info['layer_name'] in app_state.selected_features_by_layer and \
                   original_info['_temp_id'] in app_state.selected_features_by_layer[original_info['layer_name']]:
                    del app_state.selected_features_by_layer[original_info['layer_name']][original_info['_temp_id']]
                if original_info['layer_name'] in app_state.original_styles_by_layer and \
                   original_info['_temp_id'] in app_state.original_styles_by_layer[original_info['layer_name']]:
                    del app_state.original_styles_by_layer[original_info['layer_name']][original_info['_temp_id']]
                found_and_updated = True
                break
        
        if found_and_updated:
            target_layer_obj.data = {"type": "FeatureCollection", "features": target_layer_data_features}
            with editing_status_output_widget:
                ipython_clear_output(wait=True)
                print(f"Applied geometry changes to feature {original_info['_temp_id']} in layer '{original_info['layer_name']}'.")
        else:
            with editing_status_output_widget:
                ipython_clear_output(wait=True)
                print(f"Error: Original feature (to update) not found in layer '{original_info['layer_name']}'.")
    elif target_layer_obj:
         with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print(f"Error: Target layer '{original_info['layer_name']}' is not a GeoJSON layer.")
    else:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print(f"Error: Target layer '{original_info['layer_name']}' not found on map.")

    m.draw_control.clear()
    app_state.is_editing_feature = False
    app_state.feature_being_edited_info = None
    update_all_button_states(app_context)


def cancel_feature_edits(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    if not app_state.is_editing_feature or not app_state.feature_being_edited_info:
        return

    original_info = app_state.feature_being_edited_info
    target_layer_obj = m.find_layer(original_info['layer_name'])

    if target_layer_obj and isinstance(target_layer_obj, ipyleaflet.GeoJSON): # Explicit check
        target_layer_data_features = list(target_layer_obj.data.get('features', []))
        found_and_restored = False
        for i, f_dict in enumerate(target_layer_data_features):
            if f_dict['properties'].get('_temp_id') == original_info['_temp_id']:
                feature_to_restore = copy.deepcopy(original_info['original_feature_dict'])
                original_pre_selection_style = app_state.original_styles_by_layer.get(original_info['layer_name'], {}).get(original_info['_temp_id'])
                if original_pre_selection_style:
                     feature_to_restore['properties']['style'] = copy.deepcopy(original_pre_selection_style)
                else:
                     feature_to_restore['properties']['style'] = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                target_layer_data_features[i] = feature_to_restore
                found_and_restored = True
                break
        if found_and_restored:
            target_layer_obj.data = {"type": "FeatureCollection", "features": target_layer_data_features}
        # else: Warning about not finding feature

    elif target_layer_obj:
        print(f"Warning: Target layer {original_info['layer_name']} is not GeoJSON, cannot restore feature style correctly.")


    if original_info['layer_name'] in app_state.selected_features_by_layer and \
       original_info['_temp_id'] in app_state.selected_features_by_layer[original_info['layer_name']]:
        del app_state.selected_features_by_layer[original_info['layer_name']][original_info['_temp_id']]

    m.draw_control.clear()
    app_state.is_editing_feature = False
    app_state.feature_being_edited_info = None
    
    if widgets: 
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print("Feature editing cancelled. Original feature state restored and deselected.")
    update_all_button_states(app_context)