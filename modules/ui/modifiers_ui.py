import numpy as np

import bpy
from bpy.props import *
from bpy.types import Menu, Panel, UIList
from ... import __package__ as base_package

# Check if the modifier layouts can be imported from Blender. If not,
# import the layouts included in this addon. This is needed for 2.90 and
# later because the modifier layouts have been moved from Python into C
# in Blender 2.90 since 5.6.2020.
from bl_ui import properties_data_modifier
if hasattr(properties_data_modifier.DATA_PT_modifiers, "ARRAY"):
    from bl_ui.properties_data_modifier import DATA_PT_modifiers
else:
    from .properties_data_modifier import DATA_PT_modifiers

from . import ml_modifier_layouts
from .ui_common import box_with_header
from ..icons import get_icons
from .. import modifier_categories
from ..utils import (
    favourite_modifiers_names_icons_types,
    get_gizmo_object_from_modifier,
    get_ml_active_object,
    is_modifier_disabled,
    is_modifier_local,
    is_edit_mesh_modifier
)


BLENDER_VERSION_MAJOR_POINT_MINOR = float(bpy.app.version_string[0:4].strip("."))

list_of_frozen_modifiers = []


# UI elements
# =======================================================================

def _favourite_modifier_buttons(layout):
    """Adds 2, 3, or 4 buttons per row according to addon preferences.
    
    Empty rows in preferences are skipped."""

    prefs = bpy.context.preferences.addons[base_package].preferences
    fav_names_icons_types = list(favourite_modifiers_names_icons_types())
    
    buttons_per_row = int(prefs.favourites_per_row)  
    show_icons = prefs.use_icons_in_favourites

    for i in range(0, len(fav_names_icons_types), buttons_per_row):
        row_modifiers = fav_names_icons_types[i:i + buttons_per_row]

        if any(mod[0] for mod in row_modifiers):
            row = layout.row(align=True)
            
            for mod in row_modifiers:
                if mod[0]:
                    icon = mod[1] if show_icons else 'NONE'
                    row.operator("object.ml_modifier_add", text=mod[0], 
                                 icon=icon).modifier_type = mod[2]
                else:
                    row.label(text="")
            
            for _ in range(buttons_per_row - len(row_modifiers)):
                row.label(text="")


def _modifier_search_and_menu(layout, object, new_menu=False):
    """Creates the modifier search and menu row.

    Returns a sub row which contains the menu so that the modifier
    extras menu can be added to that in the stack version.
    """
    ob = object
    ml_props = bpy.context.window_manager.modifier_list

    if new_menu:
        row = layout.split(factor=0.5, align=True)
    else:
        row = layout.split(factor=0.59)
    row.enabled = ob.library is None or ob.override_library is not None

    if ob.type == 'MESH':
        # row.operator("wm.search_single_menu", text="Search for Modifier", icon='VIEWZOOM').menu_idname = "OBJECT_MT_modifier_add"
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "mesh_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type in {'CURVE', 'FONT'}:
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "curve_text_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type == 'CURVES':
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "curves_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type == 'LATTICE':
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "lattice_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type == 'POINTCLOUD':
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "pointcloud_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type == 'SURFACE':
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "surface_modifiers",
                        text="", icon='VIEWZOOM')
    elif ob.type == 'VOLUME':
        row.prop_search(ml_props, "modifier_to_add_from_search", ml_props, "volume_modifiers",
                        text="", icon='VIEWZOOM')

    sub = row.row(align=new_menu)
    sub.menu("OBJECT_MT_ml_add_modifier_menu")
    sub.operator("wm.call_menu", text="", icon='ADD').name = "OBJECT_MT_modifier_add"
    return sub


def _batch_operators(layout, pcoll, use_with_stack=False):
    """Adds the the batch operators into the given layout."""
    icon = pcoll['TOGGLE_ALL_MODIFIERS_VISIBILITY']
    layout.operator("view3d.ml_toggle_all_modifiers", icon_value=icon.icon_id, text="")

    icon = pcoll['APPLY_ALL_MODIFIERS']
    layout.operator("view3d.ml_apply_all_modifiers", icon_value=icon.icon_id, text="")

    icon = pcoll['DELETE_ALL_MODIFIERS']
    layout.operator("view3d.ml_remove_all_modifiers", icon_value=icon.icon_id, text="")

    if use_with_stack:
        icon = pcoll['TOGGLE_ALL_MODIFIER_PANELS']
        layout.operator("object.ml_toggle_all_modifier_panels", icon_value=icon.icon_id, text="")


def _show_in_editmode_button(modifier, layout, pcoll, use_in_list):
    row = layout.row(align=True)

    if modifier.type in modifier_categories.DONT_SUPPORT_SHOW_IN_EDITMODE:
        empy_icon = pcoll['EMPTY_SPACE']
        row.label(text="", translate=False, icon_value=empy_icon.icon_id)
        return

    if not use_in_list:
        row.active = modifier.show_viewport

    if not modifier.show_viewport and use_in_list:
        show_in_editmode_on = pcoll['SHOW_IN_EDITMODE_ON_INACTIVE']
        show_in_editmode_off = pcoll['SHOW_IN_EDITMODE_OFF_INACTIVE']
    else:
        show_in_editmode_on = pcoll['SHOW_IN_EDITMODE_ON']
        show_in_editmode_off = pcoll['SHOW_IN_EDITMODE_OFF']

    show = modifier.show_in_editmode
    icon = show_in_editmode_on.icon_id if show else show_in_editmode_off.icon_id
    row.prop(modifier, "show_in_editmode", text="", icon_value=icon, emboss=not use_in_list)


def _use_apply_on_spline_button(modifier, layout, pcoll, use_in_list):
    row = layout.row(align=True)

    if modifier.type not in modifier_categories.SUPPORT_USE_APPLY_ON_SPLINE:
        empy_icon = pcoll['EMPTY_SPACE']
        row.label(text="", translate=False, icon_value=empy_icon.icon_id)
        return

    use_apply_on_spline_on = pcoll['USE_APPLY_ON_SPLINE_ON']
    use_apply_on_spline_off = pcoll['USE_APPLY_ON_SPLINE_OFF']
    apply_on = modifier.use_apply_on_spline
    icon = use_apply_on_spline_on.icon_id if apply_on else use_apply_on_spline_off.icon_id
    row.prop(modifier, "use_apply_on_spline", text="", icon_value=icon, emboss=not use_in_list)


def _show_on_cage_button(object, modifier, layout, pcoll, use_in_list):
    support_show_on_cage = modifier_categories.SUPPORT_SHOW_ON_CAGE

    if modifier.type not in support_show_on_cage:
        return False

    mods = object.modifiers
    mod_index = mods.find(modifier.name)

    # Check if some modifier before this has show_in_editmode on
    # and doesn't have show_on_cage setting.
    is_before_show_in_editmode_on = False
    end_index = np.clip(mod_index, 1, 99)

    for mod in mods[0:end_index]:
        if mod.show_in_editmode and mod.type not in support_show_on_cage:
            is_before_show_in_editmode_on = True
            break

    if is_before_show_in_editmode_on:
        return False

    # Check if some modifier after this has show_in_editmode and
    # show_on_cage both on and also is visible in the viewport.
    is_after_show_on_cage_on = False

    for mod in mods[(mod_index + 1):(len(mods))]:
        if (mod.show_viewport and mod.show_in_editmode and mod.show_on_cage):
            is_after_show_on_cage_on = True
            break

    # Button
    row = layout.row(align=True)
    show_on_cage_on = pcoll['SHOW_ON_CAGE_ON']
    show_on_cage_off = pcoll['SHOW_ON_CAGE_OFF']

    if (not modifier.show_viewport or not modifier.show_in_editmode
            or is_after_show_on_cage_on):
        if use_in_list:
            show_on_cage_on = pcoll['SHOW_ON_CAGE_ON_INACTIVE']
            show_on_cage_off = pcoll['SHOW_ON_CAGE_OFF_INACTIVE']
        else:
            row.active = False

    icon = show_on_cage_on.icon_id if modifier.show_on_cage else show_on_cage_off.icon_id
    row.prop(modifier, "show_on_cage", text="", icon_value=icon, emboss=not use_in_list)

    return True


def _pin_to_last_buttons(object, modifier, layout, pcoll, use_in_list):
    mods = object.modifiers
    has_pin_to_last = False
    prefs = bpy.context.preferences.addons[base_package].preferences
    
    if not prefs.alwayse_show_use_pin_to_last:
        for mod in mods:
            if mod.use_pin_to_last:
                has_pin_to_last = True
                break
    else: 
        has_pin_to_last = True

    if not has_pin_to_last:
        return
    # Button
    row = layout.row(align=True)
    icon_pinned = "PINNED"
    icon_unpinned = "UNPINNED"

    icon = icon_pinned if modifier.use_pin_to_last else icon_unpinned
    row.prop(modifier, "use_pin_to_last", text="", icon=icon, emboss=not use_in_list)


def _curve_properties_context_change_button(layout, pcoll, use_in_list):
    sub = layout.row(align=True)
    empy_icon = pcoll['EMPTY_SPACE']

    if use_in_list:
        sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
    else:
        sub.operator("wm.properties_context_change", icon='PROPERTIES',
                     emboss=False).context = "PHYSICS"


def _mesh_properties_context_change_button(modifier, layout, use_in_list):
    if bpy.context.area.type != 'PROPERTIES' or use_in_list:
        return False

    if bpy.app.version[0] == 2 and bpy.app.version[1] < 82:
        have_phys_context_button = {
            'CLOTH',
            'COLLISION',
            'FLUID_SIMULATION',
            'DYNAMIC_PAINT',
            'SMOKE',
            'SOFT_BODY'
        }
    else:
        have_phys_context_button = {
            'CLOTH',
            'COLLISION',
            'FLUID',
            'DYNAMIC_PAINT',
            'SOFT_BODY'
        }

    if modifier.type in have_phys_context_button:
        row = layout.row(align=True)
        row.operator("wm.properties_context_change", icon='PROPERTIES',
                     emboss=False).context = "PHYSICS"
        return True

    if modifier.type == 'PARTICLE_SYSTEM':
        row = layout.row(align=True)
        row.operator("wm.properties_context_change", icon='PROPERTIES',
                     emboss=False).context = "PARTICLES"
        return True

    return False


def _classic_modifier_visibility_buttons(modifier, layout, pcoll, use_in_list=False):
    """Classic flipped order of properties. This handles the modifier visibility buttons
    (and also the properties_context_change button) to match the behaviour of the regular UI .

    When called, adds those buttons, for the given modifier, in their
    correct state, to the specified (sub-)layout.

    Note: some modifiers show show_on_cage in the regular UI only if,
    for example, an object to use for deforming is specified. Eg.
    Armatature modifier requires an armature object to be specified in
    order to show the button. This function doesn't take that into
    account but instead shows the button always in those cases. It's
    easier to achieve and hardly makes a difference.
    """
    empy_icon = pcoll['EMPTY_SPACE']

    # Main layout
    row = layout.row(align=True)
    row.scale_x = 1.0 if use_in_list else 1.2

    # show_render and show_viewport
    sub = row.row(align=True)

    is_edit_mesh_modifies = is_edit_mesh_modifier(modifier)

    if is_edit_mesh_modifies:
        sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
    
    if not modifier in list_of_frozen_modifiers and not is_edit_mesh_modifies:
        # Hide visibility toggles for collision modifier as they are not
        # used in the regular UI either (apparently can cause problems
        # in some scenes).
        if modifier.type == 'COLLISION':
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
        else:
            sub.prop(modifier, "show_render", text="", emboss=not use_in_list)
            sub.prop(modifier, "show_viewport", text="", emboss=not use_in_list)
        
        # show_in_editmode
        _show_in_editmode_button(modifier, row, pcoll, use_in_list)

        ob = get_ml_active_object()

        # No use_apply_on_spline or show_on_cage for lattices
        if ob.type == 'LATTICE':
            return

        # use_apply_on_spline or properties_context_change
        if ob.type != 'MESH':
            if modifier.type == 'SOFT_BODY':
                _curve_properties_context_change_button(row, pcoll, use_in_list)
            else:
                _use_apply_on_spline_button(modifier, row, pcoll, use_in_list)
            return

        # show_on_cage or properties_context_change
        show_on_cage_added = _show_on_cage_button(ob, modifier, row, pcoll, use_in_list)
        context_change_added = False
        if not show_on_cage_added:
            context_change_added = _mesh_properties_context_change_button(modifier, row, use_in_list)

        # Make icons align nicely if neither show_on_cage nor
        # properties_context_change was added.
        if not show_on_cage_added and not context_change_added:
            sub = row.row(align=True)
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)

        # #pin to last
        _pin_to_last_buttons(ob, modifier, row, pcoll, use_in_list)
        return


def _modifier_visibility_buttons(modifier, layout, pcoll, use_in_list=False):
    """This handles the modifier visibility buttons (and also the
    properties_context_change button) to match the behaviour of the
    regular UI .

    When called, adds those buttons, for the given modifier, in their
    correct state, to the specified (sub-)layout.

    Note: some modifiers show show_on_cage in the regular UI only if,
    for example, an object to use for deforming is specified. Eg.
    Armatature modifier requires an armature object to be specified in
    order to show the button. This function doesn't take that into
    account but instead shows the button always in those cases. It's
    easier to achieve and hardly makes a difference.
    """
    empy_icon = pcoll['EMPTY_SPACE']

    # Main layout
    row = layout.row(align=True)
    row.scale_x = 1.0 if use_in_list else 1.2

    # show_render and show_viewport
    sub = row.row(align=True)

    is_edit_mesh_modifies = is_edit_mesh_modifier(modifier)

    if is_edit_mesh_modifies:
        sub.label(text="", translate=False, icon_value=empy_icon.icon_id)

    if not modifier in list_of_frozen_modifiers and not is_edit_mesh_modifies:
        # Hide visibility toggles for collision modifier as they are not
        # used in the regular UI either (apparently can cause problems
        # in some scenes).
        ob = get_ml_active_object()

        # show_on_cage or properties_context_change
        show_on_cage_added = _show_on_cage_button(ob, modifier, sub, pcoll, use_in_list)
        context_change_added = False
        # Make icons align nicely if neither show_on_cage nor
        # properties_context_change was added.
        if not show_on_cage_added and not context_change_added:
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)

        if not show_on_cage_added:
            context_change_added = _mesh_properties_context_change_button(modifier, sub, use_in_list)

        # show_in_editmode
        _show_in_editmode_button(modifier, sub, pcoll, use_in_list)

        if modifier.type == 'COLLISION':
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
            sub.label(text="", translate=False, icon_value=empy_icon.icon_id)
        else:
            sub.prop(modifier, "show_viewport", text="", emboss=not use_in_list)
            sub.prop(modifier, "show_render", text="", emboss=not use_in_list)
        

        # No use_apply_on_spline or show_on_cage for lattices
        if ob.type == 'LATTICE':
            return

        # use_apply_on_spline or properties_context_change
        if ob.type != 'MESH':
            if modifier.type == 'SOFT_BODY':
                _curve_properties_context_change_button(row, pcoll, use_in_list)
            else:
                _use_apply_on_spline_button(modifier, row, pcoll, use_in_list)
            return
            
        # #pin to last
        _pin_to_last_buttons(ob, modifier, row, pcoll, use_in_list)
        return


def _gizmo_object_settings(layout):
    ob = get_ml_active_object()
    active_mod_index = ob.ml_modifier_active_index
    active_mod = ob.modifiers[active_mod_index]
    gizmo_ob = get_gizmo_object_from_modifier(active_mod)

    # Avoid an error when the gizmo is deleted when using the popup
    # because in that case the popover doesn't get closed when running
    # an operator. This label is also shown in the Modifier Extras menu
    # when the layout style is stack.
    if not gizmo_ob:
        layout.label(text="No gizmo")
        return

    layout.prop(gizmo_ob, "name", text="")

    if gizmo_ob.type == 'EMPTY':
        layout.prop(gizmo_ob, "empty_display_type", text="")
        layout.prop(gizmo_ob, "empty_display_size", text="Display Size")

    layout.separator()

    layout.operator("object.ml_gizmo_object_reset_transform", text="Reset Transform")

    layout.label(text="Location:")
    col = layout.column()
    col.prop(gizmo_ob, "location", text="")

    layout.label(text="Rotation:")
    col = layout.column()
    col.prop(gizmo_ob, "rotation_euler", text="")

    layout.label(text="Parent")

    is_ob_parented_to_gizmo = True if ob.parent == gizmo_ob else False
    is_gizmo_parented_to_ob = True if gizmo_ob.parent == ob else False

    col = layout.column(align=True)

    sub = col.row()
    if is_ob_parented_to_gizmo:
        sub.enabled = False
    depress = is_gizmo_parented_to_ob
    unset = is_gizmo_parented_to_ob
    sub.operator("object.ml_gizmo_object_parent_set", text="Gizmo To Active Object",
                    depress=depress).unset = unset

    sub = col.row()
    if is_gizmo_parented_to_ob:
        sub.enabled = False
    depress = is_ob_parented_to_gizmo
    unset = is_ob_parented_to_gizmo
    sub.operator("object.ml_gizmo_object_child_set", text="Active Object To Gizmo",
                    depress=depress).unset = unset

    layout.separator()

    op = layout.operator("object.ml_select", text="Select Gizmo")
    op.object_name = gizmo_ob.name
    op.unhide_object = True

    if gizmo_ob.type in {'EMPTY', 'LATTICE'} and "_Gizmo" in gizmo_ob.name:
        layout.operator("object.ml_gizmo_object_delete")


def _modifier_extras_button(context, layout, use_in_popup=False):
    """Adds the correct popover for the current area type into the given
    layout.

    This is needed because the content of the popover can be different
    depending on the layout style. The popover, sidebar and Properties
    Editor each have a separate setting to choose between a list or a
    stack layout.
    """
    area_type = context.area.type

    if use_in_popup:
        layout.popover("OBJECT_PT_ml_modifier_extras_for_popup", icon='DOWNARROW_HLT', text="")
    elif area_type == 'PROPERTIES':
        layout.popover("OBJECT_PT_ml_modifier_extras_for_properties_editor", icon='DOWNARROW_HLT',
                       text="")
    elif area_type == 'VIEW_3D':
        layout.popover("OBJECT_PT_ml_modifier_extras_for_sidebar", icon='DOWNARROW_HLT', text="")


def _modifier_menu_mesh(layout):
    col = layout.column()
    col.label(text="Edit")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.MESH_EDIT_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.MESH_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Deform")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.MESH_DEFORM_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Physics")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.MESH_SIMULATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_curve(layout):
    col = layout.column()
    col.label(text="Edit")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_EDIT_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_TEXT_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Deform")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_DEFORM_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Physics")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_SIMULATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_curves(layout):
    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVES_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_surface(layout):
    col = layout.column()
    col.label(text="Edit")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_EDIT_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.SURFACE_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Deform")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_DEFORM_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Physics")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.CURVE_SURFACE_TEXT_SIMULATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_lattice(layout):
    col = layout.column()
    col.label(text="Edit")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.LATTICE_EDIT_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Deform")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.LATTICE_DEFORM_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Physics")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.LATTICE_SIMULATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_pointcloud(layout):
    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.POINTCLOUD_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


def _modifier_menu_volume(layout):
    col = layout.column()
    col.label(text="Generate")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.VOLUME_GENERATE_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod

    col = layout.column()
    col.label(text="Deform")
    col.separator(factor=0.3)
    for name, icon, mod in modifier_categories.VOLUME_DEFORM_NAMES_ICONS_TYPES:
        col.operator("object.ml_modifier_add", text=name, icon=icon).modifier_type = mod


class OBJECT_MT_ml_add_modifier_menu(Menu):
    bl_label = "Add Modifier"
    bl_description = "Add a procedural operation/effect to the active object"

    def draw(self, context):
        layout = self.layout
        # Set the invoke method to be called for ml_modifier_add so the
        # "Add Modifier from Menu" operator can also support affecting
        # the behavior by holding keys down while pressing a button.
        layout.operator_context = 'INVOKE_DEFAULT'
        row = layout.row()
        row.alignment = 'LEFT'

        ob = get_ml_active_object()

        if ob.type == 'MESH':
            _modifier_menu_mesh(row)
        elif ob.type in {'CURVE', 'FONT'}:
            _modifier_menu_curve(row)
        elif ob.type == 'CURVES':
            _modifier_menu_curves(row)
        elif ob.type == 'LATTICE':
            _modifier_menu_lattice(row)
        elif ob.type == 'POINTCLOUD':
            _modifier_menu_pointcloud(row)
        elif ob.type == 'SURFACE':
            _modifier_menu_surface(row)
        elif ob.type == 'VOLUME':
            _modifier_menu_volume(row)


def draw_time_props(self, context):
    layout = self.layout
    
    if bpy.context.space_data.context == 'MODIFIER':
        layout.separator()
        row = layout.row()
        row.prop(bpy.context.scene, "show_timings", text="Show Timings")
        row.prop(bpy.context.scene, "compact_timing", text="In Seconds")
        row = layout.row()
        row.prop(bpy.context.scene, "total_time", text="Show Total Time")

def time_to_string(t):
    if bpy.context.scene.compact_timing == False:
        # If modifier is disabled, show 0.0 ms
        if t == 0.0015:
            return f'0.0 ms'
        # Formats time in seconds to the nearest unit
        units = {3600.: 'h', 60.: 'min', 1.: 'sec', .001: 'ms'}
        for factor in units.keys():
            if t >= factor:
                value = f'{t/factor:.3g}'
                if len(value) > 4:  # Ensure max 6 characters including unit
                    value = f'{t/factor:.2g}'
                return f'{value} {units[factor]}'

        if t >= 1e-4:
            return f'{t/factor:.2g} {units[factor]}'
        else:
            return f'<0.1 ms'
    else:
        #if modifer is disabled, show 0.0s
        if t == 0.0015:
            return f'0.0s'
        # Format it .s if under a minute with max one decimal
        if t < 60:
            if t < 0.1:
                if t < 0.01:
                    return f'<.01s'
                else:
                #round to 2 decimals instead of 1
                    return str(round(t, 2)) + "s"
    
            elif t < 10:
                return str(round(t, 1)) + "s"
            else:
                return str(round(t, 1)) + "s"
        elif t < 3600:
            return str(round(t/60, 0)) + "min"
        else:
            return str(round(t/3600, 0)) + "h"


def _get_all_modifier_times():
    global prev_ms_times

    obj = get_ml_active_object()

    depsgraph = bpy.context.view_layer.depsgraph
    ob_eval = obj.evaluated_get(depsgraph)

    if bpy.context.scene.total_time:
        times = []
        total = 0
        for mod_eval in ob_eval.modifiers:
            t = _get_modifier_times(mod_eval)
            times += [t]
            total += t
        total_text = 'Total:'
        total_time = total_text + ' ' + time_to_string(sum(times))
        return total_time
    
    
prev_ms_times = {}

def _get_modifier_times(mod): # we should not call it per modifier, but only once per object
    global prev_ms_times
    obj = get_ml_active_object()

    depsgraph = bpy.context.view_layer.depsgraph
    ob_eval = obj.evaluated_get(depsgraph)

    ms_times = ob_eval.modifiers[mod.name].execution_time

    if not mod.show_viewport or not mod.show_in_editmode and bpy.context.mode == 'EDIT_MESH':
        #the number when a modifier is disabled and should be 0.0 ms
        ms_times = 0.0015
    else:
        if ms_times >= 1e-4:
            obj_name = obj.name
            if obj_name not in prev_ms_times:
                prev_ms_times[obj_name] = {}
            prev_ms_times[obj_name][mod.name] = ms_times
        else:
            obj_name = bpy.context.object.name
            if obj_name in prev_ms_times and mod.name in prev_ms_times[obj_name]:
                ms_times = prev_ms_times[obj_name][mod.name]
    return ms_times
    
class OBJECT_UL_modifier_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        global list_of_frozen_modifiers
        prefs = bpy.context.preferences.addons[base_package].preferences
        show_times = bpy.context.scene.show_timings

        mod = item
        over_100ms = False
        if show_times:
                text_modifier_left = _get_modifier_times(mod)
                if text_modifier_left > 0.1:
                    over_100ms = True
                text_modifier_left = time_to_string(text_modifier_left)
        else:
            text_modifier_left = ""

        is_edit_mesh_modifies = is_edit_mesh_modifier(mod)
        no_edit_mesh_modifier_found = True

        for i, m in enumerate(data.modifiers):
            if m.type == 'NODES' and m.node_group:
                if "Edit Mesh" in m.node_group.name:
                    edit_mesh_last_index = i
                    # get all modifers before the last edit mesh modifier
                    list_of_frozen_modifiers = [m for m in data.modifiers[:edit_mesh_last_index] if not m.show_viewport]
                    no_edit_mesh_modifier_found = False
        
        if no_edit_mesh_modifier_found:
            list_of_frozen_modifiers = []

        pcoll = get_icons()
        empy_icon = pcoll['EMPTY_SPACE']
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if mod:       
                row = layout.row()
                row.alert = is_modifier_disabled(mod)

                if not is_edit_mesh_modifies:
                    row.label(text="", translate=False, icon_value=layout.icon(mod))
                else:
                    row.label(text="", translate=False, icon="EDITMODE_HLT")

                if show_times:
                    row_label = row.row(align=True)
                    row_label.scale_x = 0.65
                    if over_100ms:
                        row_label.alert = True
                    row_label.label(text=text_modifier_left)
                
                layout.prop(mod, "name", text="", emboss=False)
                # only draw after the last edit mesh modifier
                if is_edit_mesh_modifies and mod not in list_of_frozen_modifiers:
                    layout.label(text="", translate=False, icon_value=empy_icon.icon_id)
                    layout.label(text="", translate=False, icon_value=empy_icon.icon_id)

                if not mod in list_of_frozen_modifiers:
                    if prefs.classic_display_order:
                        _classic_modifier_visibility_buttons(mod, layout, get_icons(), use_in_list=True)
                    else:
                        _modifier_visibility_buttons(mod, layout, get_icons(), use_in_list=True)
                else:
                    layout.label(text="", translate=False, icon_value=empy_icon.icon_id)
                    layout.label(text="", translate=False, icon_value=empy_icon.icon_id)
                    layout.enabled = False
                    layout.label(text="", translate=False, icon="FREEZE")

                    # row.label(text="", translate=False, icon="EDITMODE_HLT")
                    # is_frozen = False
                    # if mod in list_of_frozen_modifiers:
                    #     row.enabled = False
                    #     is_frozen = True

                    # row.prop(mod, "name", text=text_modifier_left, emboss=False)

                    # # row = layout.row(align=True)
                    # # sub = row.row(align=True)
                    # # sub.enabled = True  
                    # # icon_toggle = "RESTRICT_VIEW_ON"
                    # # if mod.show_render:
                    # #     icon_toggle = "RESTRICT_VIEW_OFF"
                    # pcoll = get_icons()
                    # empy_icon = pcoll['EMPTY_SPACE']
                    
                    # froze_row = row.row(align=True)
                    # froze_row.enabled = False
                    # if is_frozen:
                    #     # row.enabled = False
                    #     froze_row.label(text="", translate=False, icon="FREEZE")
                    # else:
                        # froze_row.label(text="", translate=False, icon_value=empy_icon.icon_id)

                    # future toggle mode?
                    # sub.operator("object.toggle_edit_mesh_visibility", text="", icon=icon_toggle, emboss = False).mod_name = mod.name
                    # sub.operator("object.edit_mesh_clear", text="", icon='X', emboss = False)
                    
                    # if not mod in list_of_frozen_modifiers: # does not work if clicking if not active modifier!
                    #     sub.operator("object.edit_mesh_clear", text="", icon='X', emboss = False)
                    # sub.label(text="", icon_value=empy_icon.icon_id)

            else:   
                layout.label(text="", translate=False, icon_value=icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


    def register():
        bpy.types.Scene.show_timings = bpy.props.BoolProperty(default=True)
        bpy.types.Scene.compact_timing = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.total_time = bpy.props.BoolProperty(default=False)
        bpy.types.PROPERTIES_PT_options.prepend(draw_time_props)
        
    def unregister():
        bpy.types.PROPERTIES_PT_options.remove(draw_time_props)
        del bpy.types.Scene.show_timings
        del bpy.types.Scene.compact_timing
        del bpy.types.Scene.total_time

class ShowNodeGroupInModifiersList(bpy.types.Operator):
    bl_idname = "object.geometry_node_show_node_group"
    bl_label = "Show Node Group"

    def execute(self, context):
        active_mod_index = context.object.ml_modifier_active_index
        if context.object.type == 'MESH':
            if bpy.context.object.modifiers[active_mod_index].show_group_selector == False:
                bpy.context.object.modifiers[active_mod_index].show_group_selector = True
            else:
                bpy.context.object.modifiers[active_mod_index].show_group_selector = False
        return {'FINISHED'}

class ModifierExtrasBase:
    bl_label = "Modifier Extras"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        ml_props = context.window_manager.modifier_list
        pcoll = get_icons()
        ob = get_ml_active_object()
        active_mod = ob.modifiers[ob.ml_modifier_active_index] if ob.modifiers else None

        class_name = type(self).__name__
        layout_style_is_stack = any((
            (class_name.endswith("popup") and prefs.popup_style == 'STACK'),
            (class_name.endswith("sidebar") and prefs.sidebar_style == 'STACK'),
            (class_name.endswith("properties_editor") and prefs.properties_editor_style == 'STACK')
        ))

        layout = self.layout
        layout.ui_units_x = 11

        layout.operator("object.show_references_popup", icon ='PRESET')
        if layout_style_is_stack:
            if not prefs.show_batch_ops_in_main_layout_with_stack_style:
                row = layout.row(align=True)
                row.scale_x = 50
                _batch_operators(row, pcoll, use_with_stack=layout_style_is_stack)
                layout.separator()

            if ob.type in {'CURVE', 'FONT', 'LATTICE', 'MESH', 'SURFACE'} and active_mod:
                if (active_mod.type in modifier_categories.HAVE_GIZMO_PROPERTY
                        or active_mod.type == 'UV_PROJECT'):
                    row, box = box_with_header(layout, "Gizmo", ml_props,
                                               "gizmo_object_settings_expand")

                    gizmo_ob = get_gizmo_object_from_modifier(active_mod)

                    sub = row.row()
                    sub.scale_x = 1.2
                    sub.enabled = ob.library is None

                    if not gizmo_ob:
                        icon = pcoll['ADD_GIZMO']
                        sub.operator("object.ml_gizmo_object_add", text="",
                                     icon_value=icon.icon_id).modifier = active_mod.name
                    else:
                        depress = not gizmo_ob.hide_viewport
                        sub.operator("object.ml_gizmo_object_toggle_visibility", text="",
                                     icon='EMPTY_ARROWS', depress=depress)

                    if ml_props.gizmo_object_settings_expand:
                        _gizmo_object_settings(box)

                    layout.separator()
        else:
            if active_mod:
                col = layout.column()
                pinned_ob = context.scene.modifier_list.pinned_object
                if (class_name.endswith("popup") or class_name.endswith("sidebar")) and pinned_ob:
                    col.enabled = False
                if BLENDER_VERSION_MAJOR_POINT_MINOR >= 3.5:
                    if active_mod.type == 'NODES' and active_mod.node_group:
                        col.operator("object.geometry_nodes_move_to_nodes")
                        if BLENDER_VERSION_MAJOR_POINT_MINOR >= 4.0:
                            col.prop(active_mod, "show_group_selector", toggle=True)
                        # if BLENDER_VERSION_MAJOR_POINT_MINOR >= 4.2:
                        #     col.prop(active_mod, "use_pin_to_last", text="Pin to Last", icon='PINNED')
                    

                col.operator("object.modifier_copy_to_selected").modifier = active_mod.name
            else:
                row = layout.row()
                row.enabled = False
                row.operator("object.modifier_copy_to_selected")

        layout.separator()

        layout.label(text="Syncronize Modifiers Between Instances:")
        layout.operator("object.ml_sync_active_modifier_between_instances", text="Active Only")
        layout.operator("object.ml_sync_all_modifiers_between_instances", text="All")

        layout.separator()

        layout.operator("wm.ml_favourite_modifiers_configuration_popup")

        # Style setting is currently only shown for Properties Editor
        # because template_modifiers() doesn't currently work outside of
        # Properties Editor: https://developer.blender.org/T88655.
        if class_name.endswith("properties_editor"):
            layout.prop(prefs, "properties_editor_style", expand=True)


class OBJECT_PT_ml_modifier_extras_for_popup(Panel, ModifierExtrasBase):
    pass


class OBJECT_PT_ml_modifier_extras_for_sidebar(Panel, ModifierExtrasBase):
    pass


class OBJECT_PT_ml_modifier_extras_for_properties_editor(Panel, ModifierExtrasBase):
    pass


class OBJECT_PT_ml_gizmo_object_settings(Panel):
    bl_label = "Gizmo Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        layout = self.layout

        ob = get_ml_active_object()

        # Avoid an error when a lattice gizmo is seleted when using the
        # popup because in that case the popover doesn't get closed when
        # running an operator.
        if not ob.modifiers:
            return

        _gizmo_object_settings(layout)


# UI
# =======================================================================

def modifiers_ui_with_list(context, layout, num_of_rows=False, use_in_popup=False, new_menu=False):
    ob = get_ml_active_object()
    active_mod_index = ob.ml_modifier_active_index
    if ob.modifiers:
        active_mod = ob.modifiers[active_mod_index]
        is_edit_mesh_modifies = is_edit_mesh_modifier(active_mod)
        
    prefs = bpy.context.preferences.addons[base_package].preferences
    pcoll = get_icons()


    if ob.modifiers:
        # This makes operators work without passing the active modifier
        # to them manually as an argument.
        layout.context_pointer_set("modifier", ob.modifiers[ob.ml_modifier_active_index])

    # === Favourite modifiers ===
    col = layout.column(align=True)
    _favourite_modifier_buttons(col)


    # # === Modifier search and menu ===
    if prefs.show_search_and_menu_bar:
        col = layout.column()
        _modifier_search_and_menu(col, ob, new_menu)


    # === Total Timing Text ===
    if bpy.context.scene.total_time:
        col.label(text=_get_all_modifier_times())


    # === Modifier list ===
    layout.template_list("OBJECT_UL_modifier_list", "", ob, "modifiers",
                         ob, "ml_modifier_active_index", rows=num_of_rows,
                         sort_reverse=prefs.reverse_list)

    # When sub.scale_x is 1.5 and the area/region is narrow, the buttons
    # don't align properly, so some manual work is needed.
    if use_in_popup:
        align_button_groups = prefs.popup_width <= 250
    elif context.area.type == 'VIEW_3D':
        align_button_groups = context.region.width <= 283
    else:
        align_button_groups = context.area.width <= 291

    row = layout.row(align=align_button_groups)

    # === Modifier batch operators and modifier extras menu ===
    sub = row.row(align=True)
    sub.scale_x = 3 if align_button_groups else 1.34
    _batch_operators(sub, pcoll)
    # === if no modifiers on active object, text "no modifiers, add with shift a" ===   
    if not new_menu:
        if not ob.modifiers:
            row = layout.row()
            row.label(text="Add New Modifier Shift + A")

    sub_sub = sub.row(align=True)
    sub_sub.scale_x = 0.65 if align_button_groups else 0.85
    _modifier_extras_button(context, sub_sub, use_in_popup=use_in_popup)

    global list_of_frozen_modifiers

    # === List manipulation ===
    if ob.modifiers:
        if active_mod not in list_of_frozen_modifiers and not is_edit_mesh_modifies:
            sub = row.row(align=True)
            sub.scale_x = 3 if align_button_groups else 1.5
            if not align_button_groups:
                sub.alignment = 'RIGHT'

            move_up_icon = 'TRIA_DOWN' if prefs.reverse_list else 'TRIA_UP'
            move_down_icon = 'TRIA_UP' if prefs.reverse_list else 'TRIA_DOWN'

            if not prefs.reverse_list:
                sub.operator("object.ml_modifier_move_up", icon=move_up_icon, text="")
                sub.operator("object.ml_modifier_move_down", icon=move_down_icon, text="")
            else:
                sub.operator("object.ml_modifier_move_down", icon=move_down_icon, text="")
                sub.operator("object.ml_modifier_move_up", icon=move_up_icon, text="")

            sub.operator("object.ml_modifier_remove", icon='REMOVE', text="")

            col = layout.column()

            # === get if the obj is a Duplicate Linked Modifiers Object ===  
            obj = bpy.context.object

            def select_linked_modifier_instance(context, object_name, layout):
                op = layout.operator("object.ml_select", text="Select")
                op.object_name = object_name
                op.unhide_object = True

            if obj.modifiers:
                mod = obj.modifiers[0]
                if len(obj.modifiers) == 1:
                    if mod.name == "Duplicate Linked Modifiers":
                        for item in mod.node_group.interface.items_tree:
                            if item.in_out == "INPUT" and item.identifier == 'Socket_2': 
                                if mod[item.identifier]:
                                    object_name = mod[item.identifier].name
                                    obj = bpy.data.objects[object_name]
                                    column = layout.column()
                                    lay = column  
                                    row = lay.row(align = True)
                                    row.alignment = 'LEFT'
                                    
                                    row.label(text="Linked Modifier Instance of: " + object_name, icon="LINKED")
                                    select_linked_modifier_instance(context, object_name, row)
                else:
                    if "Duplicate Linked Modifiers" in obj.modifiers:
                        for item in mod.node_group.interface.items_tree:
                            if item.in_out == "INPUT" and item.identifier == 'Socket_2': 
                                if mod[item.identifier]:
                                    object_name = mod[item.identifier].name
                                    obj = bpy.data.objects[object_name]
                                    column = layout.column()
                                    lay = column
                                    row = lay.row(align = True)
                                    row.alignment = 'LEFT'
                                    row.label(text="Overridden Modifier Instance of: " + object_name, icon="UNLINKED")
                                    select_linked_modifier_instance(context, object_name, row)
                            if item.in_out == "INPUT" and item.identifier == 'Socket_3': 
                                is_instance = mod[item.identifier]
                                if is_instance:
                                    row = layout.row(align = True)
                                    row.alignment = 'LEFT'
                                    row.label(text="Instanced, Modifiers may not work", icon="ERROR")
                                    row.prop(mod, f'["{"Socket_3"}"]', text="As Instance")

            #warn if the object has a object constraint modifier and switch it to stack instead of list to avoide crash and bugs
            if ob.constraints:
                col.label(text="Unsuported Constraint on Object! Switch to Stack to avoid bugs!", icon='ERROR')
                prefs = bpy.context.preferences.addons[base_package].preferences
                col.row().prop(prefs, "properties_editor_style", expand=True)
        else:
            row = layout.row()

        # === Modifier settings ===
        if not ob.modifiers:
            return
        active_mod = ob.modifiers[active_mod_index]
        all_mods = modifier_categories.ALL_MODIFIERS_NAMES_ICONS_TYPES
        active_mod_icon = next(icon for _, icon, mod in all_mods if mod == active_mod.type)

        col = layout.column(align=True)

        # === General settings ===
        box = col.box()
        
        if prefs.show_general_settings_region:
            row = box.row()

            sub = row.row()
            if not is_edit_mesh_modifies and active_mod not in list_of_frozen_modifiers: 
                sub.alert = is_modifier_disabled(active_mod)
                sub.label(text="", icon=active_mod_icon)
                sub.prop(active_mod, "name", text="")
                if prefs.classic_display_order:
                    _classic_modifier_visibility_buttons(active_mod, row, pcoll)
                else:
                    _modifier_visibility_buttons(active_mod, row, pcoll)
            elif not is_edit_mesh_modifies:
                sub.label(text="", icon=active_mod_icon)
                sub.prop(active_mod, "name", text="")
                sub.label(text="Frozen Modifier", icon='FREEZE')
            elif is_edit_mesh_modifies and active_mod in list_of_frozen_modifiers:
                sub.label(text="Edit Mesh Modifier", icon='EDITMODE_HLT')
                sub.label(text="Frozen Modifier", icon='FREEZE')
            else:
                sub.label(text="Edit Mesh Modifier", icon='EDITMODE_HLT')


        row = box.row()

        sub = row.row(align=True)

        if active_mod.type == 'PARTICLE_SYSTEM':
            ps = active_mod.particle_system
            if ps.settings.render_type in {'COLLECTION', 'OBJECT'}:
                sub.operator("object.duplicates_make_real", text="Convert")
            elif ps.settings.render_type == 'PATH':
                sub.operator("object.modifier_convert", text="Convert").modifier = active_mod.name
        elif not is_edit_mesh_modifies and not active_mod in list_of_frozen_modifiers and prefs.show_apply_copy_pin_bar:
            sub.scale_x = 5
            icon = pcoll['APPLY_MODIFIER']
            sub.operator("object.ml_modifier_apply", text="", icon_value=icon.icon_id)

            if active_mod.type in modifier_categories.SUPPORT_APPLY_AS_SHAPE_KEY:
                icon = pcoll['APPLY_MODIFIER_AS_SHAPEKEY']
                sub.operator("object.ml_modifier_apply_as_shapekey", text="",
                            icon_value=icon.icon_id)
                icon = pcoll['SAVE_MODIFIER_AS_SHAPEKEY']
                sub.operator("object.ml_modifier_save_as_shapekey", text="",
                                icon_value=icon.icon_id)

            if active_mod.type not in modifier_categories.DONT_SUPPORT_COPY:
                sub.operator("object.ml_modifier_copy", text="", icon='DUPLICATE')
            
            #if active_mod.use_pin_to_last:
            sub.prop(active_mod, "use_pin_to_last", text="", icon='PINNED')

        # === Gizmo object settings ===
        if ob.type in {'CURVE', 'FONT', 'LATTICE', 'MESH', 'SURFACE'} and not active_mod in list_of_frozen_modifiers and prefs.show_apply_copy_pin_bar:
            if (active_mod.type in modifier_categories.HAVE_GIZMO_PROPERTY
                    or active_mod.type == 'UV_PROJECT'):
                gizmo_ob = get_gizmo_object_from_modifier(active_mod)

                sub = row.row(align=True)
                sub.alignment = 'RIGHT'
                sub.enabled = ob.library is None

                if not gizmo_ob:
                    sub_sub = sub.row()
                    sub_sub.scale_x = 4
                    icon = pcoll['ADD_GIZMO']
                    sub_sub.operator("object.ml_gizmo_object_add", text="", icon_value=icon.icon_id
                                ).modifier = active_mod.name
                else:
                    sub_sub = sub.row(align=True)
                    sub_sub.scale_x = 1.2
                    depress = not gizmo_ob.hide_viewport
                    sub_sub.operator("object.ml_gizmo_object_toggle_visibility", text="",
                                    icon='EMPTY_ARROWS', depress=depress)
                    sub.popover("OBJECT_PT_ml_gizmo_object_settings", text="")

        # === Modifier specific settings ===
        box = col.box()
        # Disable layout for linked modifiers here manually so in custom
        # layouts all operators/settings are greyed out.
        box.enabled = ob.library is None

        # A column is needed here to keep the layout more compact,
        # because in a box separators give an unnecessarily big space.
        col = box.column()

        # Some modifiers have an improved layout with additional settings.
        have_custom_layout = (
            'BOOLEAN',
            'LATTICE'
        )

        if active_mod.type in have_custom_layout:
            getattr(ml_modifier_layouts, active_mod.type)(col, ob, active_mod)
        else:
            mp = DATA_PT_modifiers(context)
            getattr(mp, active_mod.type)(col, ob, active_mod)


def modifiers_ui_with_stack(context, layout, use_in_popup=False):
    ob = get_ml_active_object()
    prefs = bpy.context.preferences.addons[base_package].preferences
    pcoll = get_icons()

    greacepencil = False
    if ob.type == 'GREASEPENCIL':
        greacepencil = True

    if ob.modifiers:
        # This makes operators work without passing the active modifier
        # to them manually as an argument.
        layout.context_pointer_set("modifier", ob.modifiers[ob.ml_modifier_active_index])

    if not greacepencil: # need to make workaround for 4.3, DATA_PT_gpencil_modifiers does not exist anymore
        # === Favourite modifiers ===
        col = layout.column(align=True)
        _favourite_modifier_buttons(col)

        # === Modifier search and menu and modifier extras menu ===
        if prefs.show_search_and_menu_bar:
            col = layout.column()
            row = _modifier_search_and_menu(col, ob)
            _modifier_extras_button(context, row, use_in_popup=use_in_popup)


        # === Modifier batch operators ===
        if prefs.show_batch_ops_in_main_layout_with_stack_style:
            row = layout.row(align=True)
            row.scale_x = 50
            _batch_operators(row, pcoll, use_with_stack=True)
        if not prefs.show_search_and_menu_bar:
            if not ob.modifiers:
                layout.label(text="Add New Modifier Shift + A")
    else:
        layout.operator("wm.call_menu", text="Add Modifier", icon='ADD').name = "OBJECT_MT_modifier_add"
    # === Modifier stack ===
    layout.template_modifiers()
