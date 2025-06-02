import requests
import geopandas as gpd
from pyproj import Transformer
from owslib.wfs import WebFeatureService
from IPython.display import clear_output as ipython_clear_output
import xml.etree.ElementTree as ET
import json
import os
import shutil
import ipyleaflet
import uuid
import copy


# Import from within the package
from . import config as app_config
from . import state as app_state
from . import utils
from .ui_manager import update_all_button_states # For convenience
from .feature_manager import on_geojson_feature_click_callback_base # Will define this in feature_manager

def discover_feature_types(app_context):
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']

    with status_output_widget:
        ipython_clear_output(wait=True)
        print("Discovering feature types...")
        app_state.all_discovered_feature_types = []
        try:
            wfs = WebFeatureService(url=app_config.WFS_CAPABILITIES_URL.split('?')[0], version='2.0.0', timeout=30)
            app_state.all_discovered_feature_types = [content.id for content in wfs.contents]
        except Exception as e_owslib:
            print(f"OWSLib discovery failed: {e_owslib}. Trying direct XML parsing...")
            try:
                response_caps = requests.get(app_config.WFS_CAPABILITIES_URL, timeout=30)
                response_caps.raise_for_status()
                root = ET.fromstring(response_caps.content)
                namespaces = {'wfs': 'http://www.opengis.net/wfs/2.0'}
                if not root.findall('.//wfs:FeatureType', namespaces):
                    namespaces = {'wfs': 'http://www.opengis.net/wfs'}
                for ft_node in root.findall('.//wfs:FeatureType', namespaces):
                    name_el = ft_node.find('wfs:Name', namespaces)
                    if name_el is not None and name_el.text:
                        app_state.all_discovered_feature_types.append(name_el.text)
            except Exception as e_xml:
                print(f"Error parsing WFS Capabilities XML: {e_xml}")
                return

        if app_state.all_discovered_feature_types:
            opts = [app_config.FETCH_ALL_BUTTON_LABEL] + sorted(list(set(app_state.all_discovered_feature_types)))
            widgets['feature_type_dropdown'].options = opts
            widgets['feature_type_dropdown'].value = app_config.FETCH_ALL_BUTTON_LABEL
            print(f"Discovery complete: {len(app_state.all_discovered_feature_types)} types. Select/fetch.")
        else:
            print("No feature types discovered.")
    update_all_button_states(app_context)


def fetch_wfs_data(app_context):
    m = app_context['m']
    widgets = app_context['widgets']
    status_output_widget = widgets['status_output_widget']
    
    app_state.selected_features_by_layer.clear()
    app_state.original_styles_by_layer.clear()

    with status_output_widget:
        ipython_clear_output(wait=True)
        print("Initiating WFS data fetch...")
        current_map_bbox_wgs84 = m.get_bbox()
        if not current_map_bbox_wgs84 or len(current_map_bbox_wgs84) != 4:
            print("Error: Invalid map bounds.")
            return

        try:
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
            min_x_25832_fname, min_y_25832_fname = transformer.transform(current_map_bbox_wgs84[0], current_map_bbox_wgs84[1])
            max_x_25832, max_y_25832 = transformer.transform(current_map_bbox_wgs84[2], current_map_bbox_wgs84[3])
            bbox_req_str = f"{min_x_25832_fname},{min_y_25832_fname},{max_x_25832},{max_y_25832}"
            srs_name_req = "urn:ogc:def:crs:EPSG::25832"
            app_state.min_x_25832_fname_global, app_state.min_y_25832_fname_global = min_x_25832_fname, min_y_25832_fname
        except Exception as e_proj:
            print(f"Warn: BBOX reproj error: {e_proj}. Using WGS84 (lat,lon order for BBOX).")
            bbox_req_str = f"{current_map_bbox_wgs84[1]},{current_map_bbox_wgs84[0]},{current_map_bbox_wgs84[3]},{current_map_bbox_wgs84[2]}"
            srs_name_req = "urn:ogc:def:crs:EPSG::4326"
            app_state.min_x_25832_fname_global, app_state.min_y_25832_fname_global = current_map_bbox_wgs84[0], current_map_bbox_wgs84[1]

        selected_option = widgets['feature_type_dropdown'].value
        types_to_fetch = app_state.all_discovered_feature_types if selected_option == app_config.FETCH_ALL_BUTTON_LABEL else ([selected_option] if selected_option else [])
        
        if not types_to_fetch:
            print("Error: No feature type selected/available.")
            return
        if selected_option == app_config.FETCH_ALL_BUTTON_LABEL and not app_state.all_discovered_feature_types:
            print("Error: Discover types first.")
            return

        for layer_name_rem in m.get_layer_names():
            if layer_name_rem.startswith("WFS:"):
                layer_rem = m.find_layer(layer_name_rem)
                if layer_rem:
                    m.remove_layer(layer_rem)

        max_feat = app_config.MAX_FEATURES_PER_TYPE_FETCH
        total_added, successful_count = 0, 0
        failed_details = {}

        for idx, ft_fetch in enumerate(types_to_fetch):
            print(f"Processing: {ft_fetch.split(':')[-1]} ({idx+1}/{len(types_to_fetch)})... (max {max_feat} features)")
            params = {
                "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                "TYPENAMES": ft_fetch, "BBOX": bbox_req_str, "SRSNAME": srs_name_req, "COUNT": max_feat
            }
            sane_name = ft_fetch.replace(':', '_').replace('/', '_')
            out_geojson_path = os.path.join(app_config.DOWNLOAD_DIR, f"{sane_name}_bbox_{app_state.min_x_25832_fname_global:.0f}_{app_state.min_y_25832_fname_global:.0f}.geojson")
            tmp_gml, gdf_data = None, None
            try:
                resp = requests.get(app_config.WFS_GETFEATURE_BASE_URL, params=params, timeout=120)
                resp.raise_for_status()
                ctype = resp.headers.get('content-type', '').lower()

                with utils.suppress_stdout_stderr():
                    if 'gml' in ctype or 'xml' in ctype:
                        if b"<ows:ExceptionReport" in resp.content or b"<ServiceExceptionReport" in resp.content or b"<wfs:ExceptionReport" in resp.content:
                            failed_details[ft_fetch] = "Server OGC Exception (XML)"
                            err_fname = os.path.join(app_config.DOWNLOAD_DIR, f"err_{sane_name}.xml")
                            with open(err_fname, 'wb') as f_err: f_err.write(resp.content)
                            continue
                        tmp_gml = os.path.join(app_config.DOWNLOAD_DIR, f"tmp_{sane_name}.gml")
                        with open(tmp_gml, 'wb') as f_gml: f_gml.write(resp.content)
                        try:
                            gdf_data = gpd.read_file(tmp_gml)
                        except Exception as e_gml:
                            failed_details[ft_fetch] = f"GMLReadErr:{type(e_gml).__name__}"
                            prob_fname = os.path.join(app_config.DOWNLOAD_DIR, f"prob_{sane_name}.gml")
                            shutil.copy(tmp_gml, prob_fname)
                            continue
                    elif 'json' in ctype or 'geojson' in ctype:
                        json_resp = resp.json()
                        if json_resp.get("type") == "FeatureCollection" and "features" in json_resp:
                            crs_json = json_resp.get('crs', {}).get('properties', {}).get('name', srs_name_req)
                            gdf_data = gpd.GeoDataFrame.from_features(json_resp["features"], crs=crs_json)
                        else:
                            raw_json_p = os.path.join(app_config.DOWNLOAD_DIR, f"{sane_name}_raw.json")
                            with open(raw_json_p, 'w') as f_json_raw: json.dump(json_resp, f_json_raw, indent=2)
                            failed_details[ft_fetch] = "NonStdJSON"
                            continue
                    else:
                        failed_details[ft_fetch] = f"UnexpCType:{ctype}"
                        raw_dat_p = os.path.join(app_config.DOWNLOAD_DIR, f"{sane_name}_raw.dat")
                        with open(raw_dat_p, 'wb') as f_raw: f_raw.write(resp.content)
                        continue
                
                if gdf_data is not None and not gdf_data.empty:
                    if gdf_data.crs and gdf_data.crs.to_string().upper() != "EPSG:4326":
                        try:
                            gdf_data = gdf_data.to_crs("EPSG:4326")
                        except Exception as e_reproj_gdf:
                            print(f"  Warn: GDF reproj to EPSG:4326 failed for {ft_fetch}: {e_reproj_gdf}.")
                            failed_details[ft_fetch] = f"GDFReprojErr:{type(e_reproj_gdf).__name__}"
                            continue
                    
                    geojson_processed_data = gdf_data.__geo_interface__
                    for feature_dict_item in geojson_processed_data['features']:
                        feature_dict_item['properties']['_temp_id'] = str(uuid.uuid4())
                        feature_dict_item['properties'].setdefault('style', copy.deepcopy(app_config.DEFAULT_FEATURE_STYLE))
                    
                    try:
                        gpd.GeoDataFrame.from_features(geojson_processed_data['features'], crs="EPSG:4326").to_file(out_geojson_path, driver="GeoJSON", encoding='utf-8')
                    except Exception as e_save:
                        print(f"  Warn: Save GeoJSON fail for {ft_fetch}: {e_save}")
                    
                    layer_title = f"WFS: {ft_fetch.split(':')[-1]}"
                    geo_layer = ipyleaflet.GeoJSON(
                        data=geojson_processed_data,
                        name=layer_title,
                        style={}, # Individual feature styles will override this
                        hover_style=copy.deepcopy(app_config.SELECTED_STYLE)
                    )
                    # Crucial: Use a lambda to capture layer_title and pass app_context
                    geo_layer.on_click(
                        lambda feature, layer_name_captured=layer_title, **kwargs_from_leaflet:
                            on_geojson_feature_click_callback_base(feature, layer_name_captured, kwargs_from_leaflet, app_context)
                    )
                    m.add_layer(geo_layer)
                    total_added += len(gdf_data)
                    successful_count += 1
            except requests.exceptions.HTTPError as e_http:
                failed_details[ft_fetch] = f"HTTPErr:{e_http}"
            except Exception as e_gen:
                failed_details[ft_fetch] = f"Err:{type(e_gen).__name__}-{str(e_gen)[:100]}"
            finally:
                if tmp_gml and os.path.exists(tmp_gml):
                    try:
                        os.remove(tmp_gml)
                    except OSError:
                        pass
        
        print(f"\n--- Summary ---")
        print(f"Added {successful_count} layer(s), ~{total_added} features.")
        if failed_details:
            print(f"Failed for {len(failed_details)} types:")
            for k, v in failed_details.items():
                print(f"  - {k.split(':')[-1]}: {v}")
        print(f"Data in '{app_config.DOWNLOAD_DIR}'. Click on features to select/deselect.")
    update_all_button_states(app_context)