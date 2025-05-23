import bpy
from bpy.types import Panel
from bl_ui.properties_data_modifier import DATA_PT_modifiers as original_DATA_PT_modifiers

from .modifiers_ui import modifiers_ui_with_list, modifiers_ui_with_stack
from ..utils import get_ml_active_object, object_type_has_modifiers
from ... import __package__ as base_package


class DATA_PT_modifiers(Panel):
    bl_label = "Modifiers"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "modifier"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        ob = get_ml_active_object()
        if ob is not None:
            if object_type_has_modifiers(ob) or ob.type == 'GREASEPENCIL':  # Grease Pencil has not been added to pop up and panel duo to no support for list
                return True
        return False

    def draw(self, context):
        layout = self.layout

        prefs = bpy.context.preferences.addons[base_package].preferences

        if prefs.properties_editor_style == 'LIST' and context.object.type != 'GREASEPENCIL': # Grease Pencil has not been added to list
            modifiers_ui_with_list(context, layout, new_menu=False)
        else:
            modifiers_ui_with_stack(context, layout)


def register_DATA_PT_modifiers(self, context):
    """Callback function for enabling/disabling Modifier List layout
    in properties panel.
    """
    from bpy.utils import register_class, unregister_class

    prefs = bpy.context.preferences.addons[base_package].preferences
    use_properties_editor = prefs.use_properties_editor

    if use_properties_editor:
        try:
            if original_DATA_PT_modifiers.is_registered:
                unregister_class(original_DATA_PT_modifiers)
            register_class(DATA_PT_modifiers)
        except ValueError:
            pass
    else:
        try:
            unregister_class(DATA_PT_modifiers)
            register_class(original_DATA_PT_modifiers)
        except RuntimeError:
            pass


def reregister_DATA_PT_modifiers(self, context):
    """Callback function for re-registering Modifier List layout in
    Property Editor.

    This is needed because there is a bug in Blender that causes the
    modifier stack to stay visible even after it no longer should be
    drawn (after switching the layout style from stack to list).
    """
    from bpy.utils import register_class, unregister_class

    try:
        unregister_class(DATA_PT_modifiers)
        register_class(DATA_PT_modifiers)
    except RuntimeError:
        pass


def register():
    prefs = bpy.context.preferences.addons[base_package].preferences
    use_properties_editor = prefs.use_properties_editor

    if use_properties_editor:
        from bpy.utils import register_class

        try:
            register_class(DATA_PT_modifiers)
        except ValueError:
            pass


def unregister():
    from bpy.utils import register_class, unregister_class

    try:
        unregister_class(DATA_PT_modifiers)
        register_class(original_DATA_PT_modifiers)
    except RuntimeError:
        pass
