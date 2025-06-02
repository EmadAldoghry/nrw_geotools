import leafmap
import ipyleaflet
from . import config as app_config # Use app_config to avoid clash with a potential local 'config' variable

def create_map():
    m = leafmap.Map(
        center=app_config.MAP_CENTER_NRW,
        zoom=app_config.INITIAL_ZOOM,
        height="900px",
        width="1420px",
        draw_control=True,
        measure_control=True,
        fullscreen_control=True,
        attribution_control=True,
    )
    if hasattr(m, 'draw_control'):
        m.draw_control.edit = True
        m.draw_control.remove = True
    return m

def add_initial_layers(m):
    if m.layers and isinstance(m.layers[0], ipyleaflet.TileLayer):
        basemap_layer = m.layers[0]
        basemap_layer.max_zoom = app_config.WMS_DISPLAY_MAX_ZOOM
        if "openstreetmap" in basemap_layer.url.lower() and hasattr(basemap_layer, 'max_native_zoom'):
            basemap_layer.max_native_zoom = 19

    m.add_wms_layer(
        url=app_config.WMS_SERVICE_URL, layers='nw_dop_rgb', name='Orthophoto NRW (RGB)',
        attribution='Geobasis NRW', format='image/png', transparent=True,
        shown=True, version='1.3.0', max_zoom=app_config.WMS_DISPLAY_MAX_ZOOM
    )
    m.add_wms_layer(
        url=app_config.WMS_SERVICE_URL, layers='nw_dop_cir', name='Orthophoto NRW (CIR)',
        attribution='Geobasis NRW', format='image/png', transparent=True,
        shown=False, version='1.3.0', max_zoom=app_config.WMS_DISPLAY_MAX_ZOOM
    )
    m.add_basemap(basemap="Google Satellite", transparent=True, opacity=0.1)

def initialize_drawn_features_layer_on_map(m, on_click_callback):
    """
    Initializes or retrieves the drawn features layer on the map.
    The on_click_callback should be a function that takes (feature, **kwargs)
    and correctly calls the main on_geojson_feature_click with the app_context.
    """
    from . import state as app_state # Local import to avoid circular issues at module load time

    layer_name = app_config.DRAWN_FEATURES_LAYER_NAME
    existing_layer = m.find_layer(layer_name)

    if existing_layer:
        app_state.drawn_features_layer = existing_layer
    else:
        app_state.drawn_features_layer = ipyleaflet.GeoJSON(
            data={"type": "FeatureCollection", "features": []},
            name=layer_name,
            style={},
            hover_style=app_config.SELECTED_STYLE.copy()
        )
        # The callback here needs to be wrapped to include layer_name and app_context
        # This will be handled by the caller providing a pre-wrapped lambda
        app_state.drawn_features_layer.on_click(on_click_callback)
        m.add_layer(app_state.drawn_features_layer)
    return app_state.drawn_features_layer