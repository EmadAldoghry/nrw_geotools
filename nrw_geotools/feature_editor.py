# nrw_geotools/feature_editor.py

import copy
from IPython.display import clear_output as ipython_clear_output

# Import from within the package
from . import config as app_config
from . import state as app_state
from .ui_manager import update_all_button_states

def start_edit_selected_feature(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    feature_to_edit_info = None
    # Find the single selected feature
    selected_count = 0
    for layer_name, features_in_layer in app_state.selected_features_by_layer.items():
        if features_in_layer:
            selected_count += len(features_in_layer)
            if len(features_in_layer) == 1 and feature_to_edit_info is None: # Take the first single selection
                temp_id = list(features_in_layer.keys())[0]
                layer_obj = m.find_layer(layer_name)
                if layer_obj:
                    for f_on_map in layer_obj.data['features']:
                        if f_on_map['properties'].get('_temp_id') == temp_id:
                            feature_to_edit_info = {
                                'layer_name': layer_name,
                                '_temp_id': temp_id,
                                'feature_dict_on_map': copy.deepcopy(f_on_map)
                            }
                            break # Found feature on map
                if feature_to_edit_info and feature_to_edit_info.get('layer_name') == layer_name: # Ensure it's from current loop
                    break # Found the one selected feature
            elif len(features_in_layer) > 1:
                break # More than one in a layer, or already found one in another

    if selected_count != 1 or not feature_to_edit_info:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            if selected_count == 0:
                print("No feature selected to edit.")
            elif selected_count > 1:
                print("Error: Select exactly one feature to edit.")
            else: # feature_to_edit_info is None, but selected_count was 1
                print("Selected feature not found on map (this is unexpected).")
        update_all_button_states(app_context) # Ensure buttons reflect no-edit state
        return

    app_state.is_editing_feature = True
    app_state.feature_being_edited_info = {
        'layer_name': feature_to_edit_info['layer_name'],
        '_temp_id': feature_to_edit_info['_temp_id'],
        'original_feature_dict': copy.deepcopy(feature_to_edit_info['feature_dict_on_map']),
    }

    # Prepare the feature for the draw control
    feature_for_draw_control = copy.deepcopy(feature_to_edit_info['feature_dict_on_map'])
    feature_for_draw_control['properties']['style'] = copy.deepcopy(app_config.EDIT_MODE_STYLE)

    # Clear draw control and add the feature to edit
    m.draw_control.clear()
    m.draw_control.data = [feature_for_draw_control] # Add as a list containing the feature

    # Hide the original feature in its source layer by changing its style
    source_layer_obj = m.find_layer(feature_to_edit_info['layer_name'])
    if source_layer_obj:
        updated_features_in_source_layer = []
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
        else:
            with editing_status_output_widget: # Print warning if not found, but continue
                 print(f"Warning: Feature {feature_to_edit_info['_temp_id']} not found in source layer {feature_to_edit_info['layer_name']} to hide.")


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
        with editing_status_output_widget:
            ipython_clear_output(wait=True); print("Not in editing mode or no feature info available.")
        return

    edited_geometry_on_map = None
    if m.draw_control.data and len(m.draw_control.data) > 0:
        # The edited feature is the first (and should be only) item in draw_control.data
        edited_geometry_on_map = m.draw_control.data[0]['geometry']
    
    if not edited_geometry_on_map:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print("Error: Could not retrieve edited geometry from DrawControl.")
        # Don't automatically cancel here, let user decide or try again
        # cancel_feature_edits(app_context) # Decided against auto-cancel
        return

    original_info = app_state.feature_being_edited_info
    target_layer_obj = m.find_layer(original_info['layer_name'])

    if target_layer_obj:
        target_layer_data_features = list(target_layer_obj.data.get('features', []))
        found_and_updated = False
        for i, f_dict_target in enumerate(target_layer_data_features):
            if f_dict_target['properties'].get('_temp_id') == original_info['_temp_id']:
                # This is the (previously hidden) feature in the original layer
                final_updated_feature = copy.deepcopy(original_info['original_feature_dict'])
                final_updated_feature['geometry'] = edited_geometry_on_map
                
                # Restore its original style (before it was selected for editing)
                # Check if it was selected before edit, if so, it should remain selected style.
                # However, typical workflow is edit -> apply -> deselected with default style.
                # Let's assume it should go back to default or its original pre-selection style.
                # For simplicity, let's set it to DEFAULT_FEATURE_STYLE.
                # If it was selected before editing, its original style is in original_styles_by_layer
                # But since editing clears selection for that one feature, this is complex.
                # Best to revert to default style and clear its selection status.

                final_updated_feature['properties']['style'] = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                target_layer_data_features[i] = final_updated_feature
                
                # Clear selection state for this feature if it existed
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
                print(f"Error: Original feature (to update) not found in layer '{original_info['layer_name']}'. This is unexpected.")
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
        # if widgets: # Check if widgets exist to prevent error during initial call
        #     with editing_status_output_widget: ipython_clear_output(wait=True); print("Not in editing mode.")
        return

    original_info = app_state.feature_being_edited_info
    target_layer_obj = m.find_layer(original_info['layer_name'])

    if target_layer_obj:
        target_layer_data_features = list(target_layer_obj.data.get('features', []))
        found_and_restored = False
        for i, f_dict in enumerate(target_layer_data_features):
            if f_dict['properties'].get('_temp_id') == original_info['_temp_id']:
                # Restore the original feature completely, including its style before edit started.
                # The original_feature_dict stored in feature_being_edited_info
                # should have the style it had just before edit mode was entered (i.e., SELECTED_STYLE).
                # After canceling, we want to revert it to its pre-selection style and deselect it.
                
                feature_to_restore = copy.deepcopy(original_info['original_feature_dict']) # This had SELECTED_STYLE
                
                # Get its original style *before it was selected for editing*
                original_pre_selection_style = app_state.original_styles_by_layer.get(original_info['layer_name'], {}).get(original_info['_temp_id'])
                
                if original_pre_selection_style:
                     feature_to_restore['properties']['style'] = copy.deepcopy(original_pre_selection_style)
                else:
                     # If for some reason it wasn't in original_styles (e.g. if it was a new drawn feature not yet selected)
                     # default to DEFAULT_FEATURE_STYLE
                     feature_to_restore['properties']['style'] = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)

                target_layer_data_features[i] = feature_to_restore
                found_and_restored = True
                break
        
        if found_and_restored:
            target_layer_obj.data = {"type": "FeatureCollection", "features": target_layer_data_features}
        else:
             with editing_status_output_widget:
                  print(f"Warning: Feature {original_info['_temp_id']} not found in layer {original_info['layer_name']} to restore. This is unexpected.")

    # Clear this feature from selection states as it's no longer selected for edit
    if original_info['layer_name'] in app_state.selected_features_by_layer and \
       original_info['_temp_id'] in app_state.selected_features_by_layer[original_info['layer_name']]:
        del app_state.selected_features_by_layer[original_info['layer_name']][original_info['_temp_id']]
        # The corresponding entry in original_styles_by_layer will be naturally handled by `clear_selection` or `keep_selected` later
        # or will be removed if the selection dict for the layer becomes empty.

    m.draw_control.clear()
    app_state.is_editing_feature = False
    app_state.feature_being_edited_info = None
    
    if widgets: # Check if widgets exist
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print("Feature editing cancelled. Original feature state restored and deselected.")
    update_all_button_states(app_context)