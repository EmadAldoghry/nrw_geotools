# nrw_geotools/feature_cutter.py

import copy
import shapely.geometry
import shapely.ops
import uuid
from IPython.display import clear_output as ipython_clear_output
import ipyleaflet

# Import from within the package
from . import config as app_config
from . import state as app_state
from .ui_manager import update_all_button_states

def _perform_actual_cut_logic(cutting_line_geojson_feature, app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    # This function is called only when a valid LineString is drawn during cut mode.
    # Flags app_state.is_cutting_operation_active and app_state._cutting_draw_handler_active_flag are true.

    try:
        cutter_geom = shapely.geometry.shape(cutting_line_geojson_feature['geometry'])
        if not cutter_geom.is_valid or cutter_geom.is_empty:
            with editing_status_output_widget:
                # ipython_clear_output(wait=True) # Keep previous messages
                print("  Error: Cutting line geometry is invalid or empty. Cut operation aborted.")
                print("  Cut mode remains active. Draw a new valid line or cancel.")
            m.draw_control.clear() # Clear the invalid cutting line
            return # Stay in cutting mode
    except Exception as e:
        with editing_status_output_widget:
            # ipython_clear_output(wait=True)
            print(f"  Error creating cutting geometry from drawn line: {e}. Cut operation aborted.")
            print("  Cut mode remains active. Draw a new valid line or cancel.")
        m.draw_control.clear() # Clear the problematic drawing
        return # Stay in cutting mode

    with editing_status_output_widget:
        # ipython_clear_output(wait=True) # Keep previous "LineString drawn..."
        print(f"Processing cut with drawn line for {len(app_state.features_to_be_cut_info)} feature(s)...")
        # print(f"DEBUG: Cutter geometry WKT: {cutter_geom.wkt[:100]}...")

    all_newly_created_split_features_by_layer = {}
    successfully_cut_ids_by_layer = {layer_name: set() for layer_name in app_state.selected_features_by_layer.keys()}


    for target_info in app_state.features_to_be_cut_info:
        target_layer_name = target_info['layer_name']
        target_id = target_info['_temp_id']
        target_feature_dict = target_info['feature_dict'] # This is a deepcopy
        # print(f"DEBUG: Processing target feature ID: {target_id} from layer: {target_layer_name}")

        # Initialize layer in results if not present
        if target_layer_name not in all_newly_created_split_features_by_layer:
            all_newly_created_split_features_by_layer[target_layer_name] = []

        original_pre_selection_style = app_state.original_styles_by_layer.get(target_layer_name, {}).get(
                                        target_id, copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE))

        try:
            target_geom = shapely.geometry.shape(target_feature_dict['geometry'])
            if not target_geom.is_valid:
                target_geom = target_geom.buffer(0) # Try to fix

            if not target_geom.is_valid or target_geom.is_empty:
                print(f"  Skipping invalid/empty geometry for feature {target_id}. It will be kept as is.")
                feature_to_keep = copy.deepcopy(target_feature_dict)
                feature_to_keep['properties']['style'] = original_pre_selection_style
                all_newly_created_split_features_by_layer[target_layer_name].append(feature_to_keep)
                continue

            properties_for_parts = copy.deepcopy(target_feature_dict['properties'])
            properties_for_parts.pop('style', None) # New parts get default style
            
            split_geometries = shapely.ops.split(target_geom, cutter_geom)
            # print(f"DEBUG: split_geometries for {target_id}: {type(split_geometries)}")
            # if hasattr(split_geometries, 'geoms'):
            #     print(f"DEBUG: Number of geoms in split: {len(split_geometries.geoms)}")

            num_parts_created = 0
            if hasattr(split_geometries, 'geoms') and split_geometries.geoms: # A GeometryCollection
                for part_geom in split_geometries.geoms:
                    # print(f"DEBUG: Part for {target_id} - Valid: {part_geom.is_valid}, Empty: {part_geom.is_empty}, Type: {part_geom.geom_type}")
                    if part_geom.is_empty or not part_geom.is_valid:
                        continue
                    if part_geom.area < 1e-9: # Filter out sliver polygons (adjust threshold if needed)
                        # print(f"DEBUG: Skipping sliver polygon for {target_id}. Area: {part_geom.area}")
                        continue
                    num_parts_created += 1
                    new_split_feature = {
                        'type': 'Feature',
                        'geometry': shapely.geometry.mapping(part_geom),
                        'properties': {
                            **copy.deepcopy(properties_for_parts),
                            '_temp_id': str(uuid.uuid4()), # New ID for the new part
                            'style': copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
                        }
                    }
                    all_newly_created_split_features_by_layer[target_layer_name].append(new_split_feature)
            
            # print(f"DEBUG: num_parts_created for {target_id}: {num_parts_created}")
            if num_parts_created == 0: # Original was not split or resulted in no valid parts (e.g. only slivers)
                print(f"  Feature {target_id} was not split by the line or resulted in no valid parts. It will be kept as is.")
                feature_to_keep_unsplit = copy.deepcopy(target_feature_dict)
                feature_to_keep_unsplit['properties']['style'] = original_pre_selection_style
                all_newly_created_split_features_by_layer[target_layer_name].append(feature_to_keep_unsplit)
            elif num_parts_created > 0:
                print(f"  Feature {target_id} from layer '{target_layer_name}' cut into {num_parts_created} part(s).")
                successfully_cut_ids_by_layer.setdefault(target_layer_name, set()).add(target_id)


        except Exception as e_split:
            print(f"  Error during split operation for feature {target_id}: {e_split}. Keeping original.")
            feature_to_keep_on_error = copy.deepcopy(target_feature_dict)
            feature_to_keep_on_error['properties']['style'] = original_pre_selection_style
            all_newly_created_split_features_by_layer[target_layer_name].append(feature_to_keep_on_error)
    
    # print(f"DEBUG: all_newly_created_split_features_by_layer before map update: { {k: len(v) for k,v in all_newly_created_split_features_by_layer.items()} }")

    # Update map layers
    for layer_name_update, new_or_preserved_features in all_newly_created_split_features_by_layer.items():
        target_layer_obj_update = m.find_layer(layer_name_update)
        if target_layer_obj_update and isinstance(target_layer_obj_update, ipyleaflet.GeoJSON):
            current_features_on_map_data = list(target_layer_obj_update.data.get('features', []))
            
            # IDs of original features that were targeted for cutting in this specific layer
            ids_of_originals_targeted_in_this_layer = {
                info['_temp_id'] for info in app_state.features_to_be_cut_info 
                if info['layer_name'] == layer_name_update
            }
            
            # Filter out the original features that were targeted
            features_to_retain_from_original_layer = [
                f for f in current_features_on_map_data
                if f['properties'].get('_temp_id') not in ids_of_originals_targeted_in_this_layer
            ]
            
            # Combine retained features with new/preserved ones
            final_features_for_layer = features_to_retain_from_original_layer + new_or_preserved_features
            # print(f"DEBUG: Updating layer {layer_name_update} with {len(final_features_for_layer)} features.")
            
            target_layer_obj_update.data = {"type": "FeatureCollection", "features": final_features_for_layer}
        elif target_layer_obj_update:
            print(f"  Warning: Layer {layer_name_update} found but is not a GeoJSON layer. Type: {type(target_layer_obj_update)}")
        else:
            print(f"  Warning: Layer {layer_name_update} (where cut features were) not found on map for update.")

    # Clean up selection state for features that were successfully cut and replaced
    for layer_name, ids_cut in successfully_cut_ids_by_layer.items():
        if layer_name in app_state.selected_features_by_layer:
            for temp_id in ids_cut:
                if temp_id in app_state.selected_features_by_layer[layer_name]:
                    del app_state.selected_features_by_layer[layer_name][temp_id]
                if temp_id in app_state.original_styles_by_layer.get(layer_name, {}):
                    del app_state.original_styles_by_layer[layer_name][temp_id]
            if not app_state.selected_features_by_layer[layer_name]: # if dict becomes empty
                del app_state.selected_features_by_layer[layer_name]
                if layer_name in app_state.original_styles_by_layer:
                     del app_state.original_styles_by_layer[layer_name]


    # Reset state and draw tools as cutting is now complete
    app_state.is_cutting_operation_active = False
    app_state._cutting_draw_handler_active_flag = False

    default_shape_options = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
    if 'clickable' not in default_shape_options : default_shape_options['clickable'] = True # Ensure clickable for general use

    m.draw_control.polyline = {'shapeOptions': default_shape_options}
    m.draw_control.polygon = {'shapeOptions': default_shape_options}
    m.draw_control.rectangle = {'shapeOptions': default_shape_options}
    m.draw_control.circle = {'shapeOptions': default_shape_options}
    m.draw_control.circlemarker = {'shapeOptions': default_shape_options}
    m.draw_control.marker = {} # Or your default marker settings

    m.draw_control.clear() # Clear the cutting line itself from the draw_control's temporary layer
    app_state.features_to_be_cut_info.clear()

    with editing_status_output_widget:
        # ipython_clear_output(wait=True) # Appends to "LineString drawn..."
        print("Cut operation finished. New parts are not automatically selected.")
        print("Selections related to successfully cut items have been cleared.")

    update_all_button_states(app_context)


# This is called BY the master_on_draw_handler when appropriate (cutting mode active)
def _cutting_mode_draw_handler(control_instance, action, geo_json, app_context):
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    # Master handler should ensure flags are set, but double check
    if not app_state.is_cutting_operation_active or not app_state._cutting_draw_handler_active_flag:
        control_instance.clear() # Clear unexpected drawing
        return

    if action == 'created':
        drawn_feature_geojson = geo_json
        if drawn_feature_geojson.get('geometry', {}).get('type') == 'LineString':
            with editing_status_output_widget:
                # ipython_clear_output(wait=True) # Clears "Draw a line..."
                print("LineString drawn for cut. Processing...") # Message before starting the logic
            _perform_actual_cut_logic(drawn_feature_geojson, app_context)
            # After _perform_actual_cut_logic, cutting mode is deactivated.
        else:
            with editing_status_output_widget:
                # ipython_clear_output(wait=True)
                print("Incorrect geometry for cut. Expected a LineString (a simple line).")
                print("Cut mode still active. Draw a new line or click 'Cancel Cut Op'.")
            control_instance.clear() # Remove the incorrect geometry from draw_control's temp layer
            # Stay in cutting mode, user needs to draw a line or cancel.
            
    elif action in ['deleted', 'canceled', 'drawstop']: # User cancelled drawing from toolbar
        with editing_status_output_widget:
            # ipython_clear_output(wait=True)
            print("Drawing for cut cancelled/stopped via toolbar.")
            print("Cut mode still active. Draw a new line or click 'Cancel Cut Op'.")
        control_instance.clear() # Clear any partial drawing from draw_control's temp layer

def start_cut_selected_features(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    app_state.features_to_be_cut_info.clear()
    has_polygons_to_cut = False

    # Collect all valid, selected polygon/multipolygon features
    for layer_name_sel, sel_ids_in_layer in app_state.selected_features_by_layer.items():
        if not sel_ids_in_layer:
            continue
        
        layer_obj = m.find_layer(layer_name_sel)
        if layer_obj and isinstance(layer_obj, ipyleaflet.GeoJSON):
            for temp_id_sel in sel_ids_in_layer.keys():
                feature_to_check = None
                for f_on_map in layer_obj.data.get('features', []):
                    if f_on_map['properties'].get('_temp_id') == temp_id_sel:
                        feature_to_check = f_on_map
                        break
                
                if feature_to_check:
                    geom_type = feature_to_check.get('geometry', {}).get('type', '').lower()
                    if 'polygon' in geom_type: # Catches Polygon and MultiPolygon
                        app_state.features_to_be_cut_info.append({
                            'layer_name': layer_name_sel,
                            '_temp_id': temp_id_sel,
                            'feature_dict': copy.deepcopy(feature_to_check)
                        })
                        has_polygons_to_cut = True
                    # else: # Optional: message for non-polygons
                    #     print(f"  Note: Feature {temp_id_sel} from {layer_name_sel} is a {geom_type}, not Polygon/MultiPolygon. Skipping for cut.")
                # else: # Should ideally not happen if selection state is consistent
                #     print(f"Warning: Selected feature {temp_id_sel} from layer {layer_name_sel} not found on map. Skipping.")
    
    if not has_polygons_to_cut:
        with editing_status_output_widget:
            ipython_clear_output(wait=True)
            print("No suitable (Polygon/MultiPolygon) features currently selected to cut.")
        update_all_button_states(app_context)
        return

    # Set states and configure draw_control for polyline ONLY
    app_state.is_cutting_operation_active = True
    app_state._cutting_draw_handler_active_flag = True # Master handler will use this

    m.draw_control.clear() # Clear any previous drawings from draw_control's temporary layer
    
    # Configure draw_control for polyline only for this operation
    m.draw_control.polyline = {'shapeOptions': {'color': 'red', 'weight': 3, 'opacity': 0.7, 'clickable': True}}
    m.draw_control.polygon = {} # Disable other drawing tools temporarily
    m.draw_control.circlemarker = {}
    m.draw_control.rectangle = {}
    m.draw_control.circle = {}
    m.draw_control.marker = {}

    # The master_on_draw_handler registered in main_notebook.ipynb will now
    # delegate to _cutting_mode_draw_handler based on the flags set above.

    with editing_status_output_widget:
        ipython_clear_output(wait=True)
        print(f"CUT MODE ACTIVATED: {len(app_state.features_to_be_cut_info)} Polygon/MultiPolygon feature(s) targeted.")
        print("Draw a POLYLINE (a simple line) on the map to cut the selected feature(s).")
        print("Use the polyline tool from the draw toolbar. Click 'Cancel Cut Op' to exit.")
    update_all_button_states(app_context)


def cancel_cut_operation(app_context): # This is the function imported by callbacks.py
    m = app_context['m']
    widgets = app_context['widgets']
    editing_status_output_widget = widgets['editing_status_output_widget']

    if not app_state.is_cutting_operation_active: # Only act if truly in cut mode
        # It's possible this is called by _perform_actual_cut_logic's cleanup path
        # after flags are already reset. In that case, just ensure draw tools are reset.
        pass # Allow tool reset below even if flags are already false.

    with editing_status_output_widget:
        ipython_clear_output(wait=True)
        print("Cut operation cancelled or concluded.")

    # Reset state flags
    app_state.is_cutting_operation_active = False
    app_state._cutting_draw_handler_active_flag = False

    # Reset draw_control to default drawing tools enabled
    default_shape_options = copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE)
    if 'clickable' not in default_shape_options : default_shape_options['clickable'] = True

    m.draw_control.polyline = {'shapeOptions': default_shape_options}
    m.draw_control.polygon = {'shapeOptions': default_shape_options}
    m.draw_control.rectangle = {'shapeOptions': default_shape_options}
    m.draw_control.circle = {'shapeOptions': default_shape_options}
    m.draw_control.circlemarker = {'shapeOptions': default_shape_options} 
    m.draw_control.marker = {} # Or your default marker options

    m.draw_control.clear() # Clear any leftover cutting line from draw_control's temporary layer
    app_state.features_to_be_cut_info.clear() # Clear the list of features targeted for cutting
    
    # Selections made prior to initiating the cut operation should generally remain.
    # The `update_all_button_states` will reflect button states based on current selections.
    update_all_button_states(app_context)