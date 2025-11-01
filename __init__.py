# Copyright (C) 2019 Antti Tikka

# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ***** END GPL LICENSE BLOCK *****

import bpy
import os

from . import addon_registration

# register_bl_classes arguments

modules_to_ignore = (
    "preferences",
    "properties",
)

classes_to_ignore = (
    "DATA_PT_modifiers",
)

panel_order = (
    "VIEW3D_PT_ml_modifiers",
    "VIEW3D_PT_ml_vertex_groups",
)

# call_register arguments

module_order = (
    "preferences",
)


addon_keymaps = []


def register():
    addon_registration.import_modules("modules")
    addon_registration.register_bl_classes(modules_to_ignore=modules_to_ignore,
                                           classes_to_ignore=classes_to_ignore,
                                           panel_order=panel_order,
                                           addon_name_for_counter=__package__)
    addon_registration.call_register(module_order=module_order)

    # === Keymap ===
    wm = bpy.context.window_manager

    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new("view3d.modifier_popup", 'SPACE', 'PRESS', alt=True)
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
        kmi = km.keymap_items.new("object.ml_modifier_add_from_search", 'W', 'PRESS', ctrl=True)
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
        kmi = km.keymap_items.new("object.add_modifier_menu", 'A', 'PRESS', shift=True)
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
        kmi = km.keymap_items.new("object.ml_modifier_copy", 'C', 'PRESS', ctrl=True)
        kmi.properties.copy = True
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
        kmi = km.keymap_items.new("object.ml_modifier_copy", 'V', 'PRESS', ctrl=True)
        kmi.properties.past = True
        addon_keymaps.append((km, kmi))

        # this only works on Windows
        if os.name == 'nt':
            km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
            kmi = km.keymap_items.new("object.ml_mouse_hover_op", 'A', 'PRESS', ctrl=True)
            kmi.properties.type = 'apply modifier'
            addon_keymaps.append((km, kmi))

            km = wm.keyconfigs.addon.keymaps.new(name='Property Editor', space_type='PROPERTIES')
            kmi = km.keymap_items.new("object.ml_mouse_hover_op", 'X', 'PRESS', ctrl=True)
            kmi.properties.type = 'remove modifier'
            addon_keymaps.append((km, kmi))

def unregister():
    # === Keymap ===
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    addon_registration.call_unregister(module_order=list(reversed(module_order)))
    addon_registration.unregister_bl_classes(addon_name_for_counter=__package__)
