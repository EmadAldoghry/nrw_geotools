import ipywidgets as widgets
from . import config as app_config
from . import state as app_state

def create_widgets():
    widgets_dict = {}
    widgets_dict['feature_type_dropdown'] = widgets.Dropdown(
        description='Feature Type:', style={'description_width': 'initial'},
        layout={'width': '250px'}, disabled=True
    )
    widgets_dict['discover_button'] = widgets.Button(
        description="Discover Available Feature Types", button_style='primary', layout={'width': '250px'}
    )
    widgets_dict['fetch_data_button'] = widgets.Button(
        description="Fetch Selected/All WFS Data", button_style='info', layout={'width': '250px'}, disabled=True
    )
    widgets_dict['keep_selected_button'] = widgets.Button(
        description="Keep Only Selected Features", button_style='success', layout={'width': '200px'}, disabled=True
    )
    widgets_dict['clear_selection_button'] = widgets.Button(
        description="Clear Selection", button_style='warning', layout={'width': '150px'}, disabled=True
    )
    widgets_dict['status_output_widget'] = widgets.Output(
        layout={'border': '1px solid #ccc', 'padding': '5px', 'max_height': '150px', 'overflow_y': 'auto', 'width': '98%'}
    )
    widgets_dict['editing_status_output_widget'] = widgets.Output(
        layout={'border': '1px solid #ccc', 'padding': '5px', 'margin_top': '5px', 'width': '98%', 'max_height': '100px', 'overflow_y': 'auto'}
    )
    widgets_dict['edit_selected_feature_button'] = widgets.Button(
        description="Edit Selected Feature", icon="edit", layout={'width': '180px'}, disabled=True
    )
    widgets_dict['apply_feature_edits_button'] = widgets.Button(
        description="Apply Feature Edits", icon="check", button_style='success', layout={'visibility': 'hidden'}
    )
    widgets_dict['cancel_feature_edits_button'] = widgets.Button(
        description="Cancel Feature Edits", icon="times", button_style='danger', layout={'visibility': 'hidden'}
    )
    widgets_dict['cut_selected_button'] = widgets.Button(
        description="Cut Selected w/ Line", icon="cut", layout={'width': '180px'}, disabled=True
    )
    widgets_dict['cancel_cut_button'] = widgets.Button(
        description="Cancel Cut Op", icon="ban", button_style='info', layout={'visibility': 'hidden'}
    )
    widgets_dict['remove_selected_button'] = widgets.Button(
        description="Remove Selected Features", icon="trash", button_style='danger', layout={'width': '220px'}, disabled=True
    )
    widgets_dict['gml_filename_input'] = widgets.Text(
        value='output_features', placeholder='Enter GML filename (no extension)',
        description='GML Filename:', style={'description_width': 'initial'}, layout={'width': '300px'}, disabled=True
    )
    widgets_dict['save_selected_as_gml_button'] = widgets.Button(
        description="Save Selected as GML", button_style='primary', icon='save', layout={'width': '220px'}, disabled=True
    )
    return widgets_dict

def layout_widgets(widgets_dict):
    ui_line1_discovery_fetch = widgets.HBox([
        widgets_dict['discover_button'], widgets_dict['feature_type_dropdown'], widgets_dict['fetch_data_button']
    ], layout=widgets.Layout(flex_flow='row wrap', justify_content='flex-start'))

    ui_line2_selection_edit_remove = widgets.HBox([
        widgets_dict['keep_selected_button'], widgets_dict['clear_selection_button'],
        widgets_dict['remove_selected_button'], widgets_dict['edit_selected_feature_button'],
        widgets_dict['cut_selected_button']
    ], layout=widgets.Layout(flex_flow='row wrap', justify_content='flex-start', margin_top='5px'))

    ui_line3_save_actions = widgets.HBox([
        widgets_dict['gml_filename_input'], widgets_dict['save_selected_as_gml_button']
    ], layout=widgets.Layout(flex_flow='row wrap', justify_content='flex-start', margin_top='5px'))

    ui_hidden_apply_cancel_buttons = widgets.HBox([
        widgets_dict['apply_feature_edits_button'], widgets_dict['cancel_feature_edits_button'],
        widgets_dict['cancel_cut_button']
    ], layout=widgets.Layout(flex_flow='row wrap', justify_content='flex-start', margin_top='5px'))

    ui_top_controls = widgets.VBox([
        ui_line1_discovery_fetch, ui_line2_selection_edit_remove, ui_line3_save_actions,
        ui_hidden_apply_cancel_buttons, widgets_dict['editing_status_output_widget'],
        widgets_dict['status_output_widget']
    ])
    return ui_top_controls

def update_all_button_states(app_context):
    # app_context contains 'm', 'widgets', 'config', 'state'
    w = app_context['widgets']
    s = app_context['state']
    cfg = app_context['config']
    # m_map = app_context['m'] # m_map might not be needed directly here for button states

    num_map_features_selected = 0
    for layer_name, sel_dict in s.selected_features_by_layer.items():
        if (layer_name.startswith("WFS:") or layer_name == cfg.DRAWN_FEATURES_LAYER_NAME) and sel_dict:
            num_map_features_selected += len(sel_dict)

    any_selected_at_all = num_map_features_selected > 0
    an_operation_is_active = s.is_editing_feature or s.is_cutting_operation_active

    w['discover_button'].disabled = an_operation_is_active
    w['feature_type_dropdown'].disabled = an_operation_is_active or not bool(s.all_discovered_feature_types)
    w['fetch_data_button'].disabled = an_operation_is_active or not ((w['feature_type_dropdown'].value is not None) or (not s.all_discovered_feature_types and not w['feature_type_dropdown'].value))

    w['keep_selected_button'].disabled = an_operation_is_active or not any_selected_at_all
    w['clear_selection_button'].disabled = an_operation_is_active or not any_selected_at_all
    w['remove_selected_button'].disabled = an_operation_is_active or not any_selected_at_all

    w['edit_selected_feature_button'].disabled = an_operation_is_active or (num_map_features_selected != 1)
    w['apply_feature_edits_button'].layout.visibility = 'visible' if s.is_editing_feature else 'hidden'
    w['cancel_feature_edits_button'].layout.visibility = 'visible' if s.is_editing_feature else 'hidden'

    w['cut_selected_button'].disabled = an_operation_is_active or (num_map_features_selected == 0)
    w['cancel_cut_button'].layout.visibility = 'visible' if s.is_cutting_operation_active else 'hidden'

    w['save_selected_as_gml_button'].disabled = an_operation_is_active or not any_selected_at_all
    w['gml_filename_input'].disabled = an_operation_is_active or not any_selected_at_all