import bpy
from bpy.props import *
from bpy.types import Operator

from ..utils import get_ml_active_object, is_modifier_local

target = None
source_object_name = ""
modifier_name = ""

class OBJECT_OT_ml_modifier_copy(Operator):
    bl_idname = "object.ml_modifier_copy"
    bl_label = "Copy Modifier"
    bl_description = "Duplicate modifier at the same position in the stack"
    bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}

    copy: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})  # type: ignore
    past: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})  # type: ignore

    @classmethod
    def poll(cls, context):
        ob = get_ml_active_object()

        if not ob:
            return False

        if ob.override_library:
            return True
        
        if ob.modifiers:
            mod = ob.modifiers[ob.ml_modifier_active_index]
            return is_modifier_local(ob, mod)
        else:
            return True
     
    def execute(self, context):
        global target, modifier_name, source_object_name

        if not self.past:
            ob = get_ml_active_object()
            mod = ob.modifiers[ob.ml_modifier_active_index]

        if context.space_data.context == 'MODIFIER':
            if self.past:
                if source_object_name and modifier_name:
                    source = bpy.data.objects.get(source_object_name)

                    if source == context.active_object:
                        bpy.ops.object.modifier_copy(modifier=modifier_name)

                    if source:
                        target = context.selected_objects

                        try:
                            with bpy.context.temp_override(object=source, selected_objects=(target)):
                                bpy.ops.object.modifier_copy_to_selected(modifier=modifier_name)
                            self.report({'INFO'}, "Pasted Modifier: " + str(modifier_name))
                        except:
                            pass
                            self.report({'WARNING'}, "Pasted Failed: Modifier: " + str(modifier_name) + " - Object: " + str(source_object_name) + " does not Exist or has changed Name")
                            return {'CANCELLED'}
                        return {'FINISHED'}
                    else:
                        self.report({'WARNING'}, "Pasted Failed: Modifier: " + str(modifier_name) + " - Object: " + str(source_object_name) + " does not Exist or has changed Name")
                        return {'CANCELLED'}
                else:
                    self.report({'WARNING'}, "No Modifier in Clipboard")
                    return {'CANCELLED'}

            elif self.copy:
                modifier_name = mod.name
                source_object_name = ob.name
                self.report({'INFO'}, "Copied Modifier: " + str(mod.name))
                return {'FINISHED'}
        else:
            print("Copy/Past Modifiers, not in Modifier Tab - CANCELLED")
            return {'PASS_THROUGH'}
                
        # Make copying modifiers possible when an object is pinned
        
        ### Draise - removed for Blender 4.0.0 compatibility

        #override = context.copy()
        #override['object'] = ob

        with context.temp_override(id=ob): ### Draise - added "with" for Blender 4.0.0 compatibility
            bpy.ops.object.modifier_copy('INVOKE_DEFAULT', modifier=mod.name)
        return {'FINISHED'}
