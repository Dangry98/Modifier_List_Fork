import bpy

# Check if the modifier layouts can be imported from Blender. If not,
# import the layouts included in this addon. This is needed for 2.90 and
# later because the modifier layouts have been moved from Python into C
# in Blender 2.90 since 5.6.2020.
from bl_ui import properties_data_modifier
if hasattr(properties_data_modifier.DATA_PT_modifiers, "ARRAY"):
    from bl_ui.properties_data_modifier import DATA_PT_modifiers
else:
    from .properties_data_modifier import DATA_PT_modifiers

from..utils import get_gizmo_object_from_modifier


def BOOLEAN(layout, ob, md):
    context = bpy.context
    mp = DATA_PT_modifiers(context)
    mp.BOOLEAN(layout, ob, md)

    if ((md.operand_type == 'OBJECT' and not md.object)
            or (md.operand_type == 'COLLECTION' and not md.collection)):
        return

    layout.separator()
    layout.separator()

    if md.operand_type == 'OBJECT':
        row = layout.row(align=True)
        row.label(text="Boolean Object:")
        op = row.operator("object.ml_select", text="Select")
        op.object_name = md.object.name
        op.unhide_object = True

        is_hidden = md.object.hide_get()
        icon = 'HIDE_ON' if is_hidden else 'HIDE_OFF'
        text = "Hide"
        if is_hidden:
            text = "Show"
        row.operator("object.ml_toggle_visibility_on_view_layer",
                     text=text, icon=icon).object_name = md.object.name

        layout.separator()

        row = layout.row(align=True)
        row.label(text="Display As:")
        row.prop(md.object, "display_type", text="")

        layout.separator()

        row = layout.row(align=True)
        row.label(text="Shading:")
        op = row.operator("object.ml_smooth_shading_set", text="Smooth")
        op.object_name = md.object.name
        op.shade_smooth = True

        op = row.operator("object.ml_smooth_shading_set", text="Auto Smooth")
        op.object_name = md.object.name
        op.auto_smooth = True

        for mod in md.object.modifiers:
            if mod.name == 'Smooth by Angle':
                row = layout.row(align=True)
                row.label(text="Smooth by Angle:")  
                row.prop(mod, '["Input_1"]', text="Angle")
                break
            
        op = row.operator("object.ml_smooth_shading_set", text="Flat")
        op.object_name = md.object.name
        op.shade_smooth = False


    elif md.operand_type == 'COLLECTION':
        layout.label(text="Boolean Collection:")

        layout.separator()

        # some collections are nested in other collections, so we need to take that into account
        def find_layer_collection(layer_coll, coll_name):
            if layer_coll.name == coll_name:
                return layer_coll
            for child in layer_coll.children:
                found = find_layer_collection(child, coll_name)
                if found:
                    return found
            return None

        layer_collection = find_layer_collection(context.view_layer.layer_collection, md.collection.name)
        layout.prop(layer_collection, "hide_viewport", text="Hide")

        layout.separator()

        layout.label(text="Set Objects To Display As:")

        row = layout.row(align=True)

        op = row.operator("collection.objects_display_type_set", text="Textured")
        op.collection_name = md.collection.name
        op.display_type = 'TEXTURED'

        op = row.operator("collection.objects_display_type_set", text="Solid")
        op.collection_name = md.collection.name
        op.display_type = 'SOLID'

        op = row.operator("collection.objects_display_type_set", text="Wire")
        op.collection_name = md.collection.name
        op.display_type = 'WIRE'

        op = row.operator("collection.objects_display_type_set", text="Bounds")
        op.collection_name = md.collection.name
        op.display_type = 'BOUNDS'

        layout.separator()

        op = layout.operator("collection.ml_objects_smooth_shading_set",
                             text="Shade Objects Smooth")
        op.collection_name = md.collection.name
        op.shade_smooth = True

        op = layout.operator("collection.ml_objects_smooth_shading_set", text="Shade Objects Flat")
        op.collection_name = md.collection.name
        op.shade_smooth = False

        layout.separator()

        op = layout.operator("collection.ml_select_objects", text="Select Objects")
        op.collection_name = md.collection.name


def LATTICE(layout, ob, md):
    context = bpy.context
    gizmo_ob = get_gizmo_object_from_modifier(md)

    if gizmo_ob:
        lat = gizmo_ob.data

        row = layout.row()
        row.enabled = not gizmo_ob.hide_viewport
        depress = gizmo_ob.mode == 'EDIT'
        if context.area.type == 'PROPERTIES':
            row.operator("object.lattice_toggle_editmode_prop_editor", text="Edit Lattice",
                         depress=depress)
        else:
            row.operator("object.lattice_toggle_editmode", text="Edit Lattice", depress=depress)

        layout.separator()

        row = layout.row()

        sub = row.column(align=True)
        sub.prop(lat, "points_u")
        sub.prop(lat, "points_v")
        sub.prop(lat, "points_w")

        sub = row.column(align=True)
        sub.prop(lat, "interpolation_type_u", text="")
        sub.prop(lat, "interpolation_type_v", text="")
        sub.prop(lat, "interpolation_type_w", text="")

        layout.separator()

        layout.prop(lat, "use_outside", text="Outside Only")

        layout.separator()

    mp = DATA_PT_modifiers(context)
    mp.LATTICE(layout, ob, md)
