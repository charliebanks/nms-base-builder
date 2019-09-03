# Header Info ---
bl_info = {
    "name": "No Mans Sky Base Builder",
    "description": "A tool to assist with base building in No Mans Sky",
    "author": "Charlie Banks",
    "version": (0, 9, 5),
    "blender": (2, 80, 0),
    "location": "3D View > Tools",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Game Engine",
}
import cProfile
import importlib
import json
import os
import sys

import bpy
import bpy.utils
import bpy.utils.previews
import mathutils
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup

from . import curve
from . import material as _material
from . import parts, power, presets, snap, utils

importlib.reload(utils)
importlib.reload(power)
importlib.reload(parts)
importlib.reload(presets)
importlib.reload(snap)
importlib.reload(curve)
importlib.reload(_material)

PART_BUILDER = parts.PartBuilder()
PRESET_BUILDER = presets.PresetBuilder(PART_BUILDER)
SNAPPER = snap.Snapper()

FILE_PATH = os.path.dirname(os.path.realpath(__file__))
GHOSTED_JSON = os.path.join(FILE_PATH, "resources", "ghosted.json")
GHOSTED_ITEMS = utils.load_dictionary(GHOSTED_JSON)

# Setting Support Methods ---
def ShowMessageBox(message="", title="Message Box", icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)

def part_switch(self, context):
    """Toggle method for switching between parts and presets."""
    scene = context.scene
    part_list = "presets" if self.enum_switch == {"PRESETS"} else "parts"

    if self.enum_switch not in [{"PRESETS"}]:
        refresh_ui_part_list(scene, part_list, pack=list(self.enum_switch)[0])
    else:
        refresh_ui_part_list(scene, part_list)


# Core Settings Class
class NMSSettings(PropertyGroup):
    # Build Array of base part types. (Vanilla Parts - Mods - Presets)
    enum_items = []
    for pack, _ in PART_BUILDER.available_packs:
        enum_items.append((pack, pack, "View {0}...".format(pack)))
    enum_items.append(("PRESETS", "Presets", "View Presets..."))

    # Blender Properties.
    enum_switch : EnumProperty(
        name="enum_switch",
        description="Toggle to display between parts and presets.",
        items=enum_items,
        options={"ENUM_FLAG"},
        default=None,
        update=part_switch,
    )

    material_switch : EnumProperty(
        name="material_switch",
        description="Decide what type of material to apply",
        items=[
            ("CONCRETE", "Concrete", "Concrete"),
            ("RUST", "Rust", "Rust"),
            ("STONE", "Stone", "Stone"),
            ("WOOD", "Wood", "Wood"),
        ],
        options={"ENUM_FLAG"},
        default={"CONCRETE"},
    )

    preset_name : StringProperty(
        name="preset_name", description="The of a preset.", default="", maxlen=1024
    )

    string_base : StringProperty(
        name="Base Name",
        description="The name of the base set in game.",
        default="",
        maxlen=1024,
    )

    string_address : StringProperty(
        name="Galactic Address",
        description="The galactic address.",
        default="",
        maxlen=1024,
    )

    string_usn : StringProperty(
        name="USN", description="The username attribute.", default="", maxlen=1024
    )

    string_uid : StringProperty(
        name="UID", description="A user ID.", default="", maxlen=1024
    )

    string_lid : StringProperty(
        name="LID", description="Not sure what this is.", default="", maxlen=1024
    )

    string_ptk : StringProperty(
        name="PTK", description="Not sure what this is.", default="", maxlen=1024
    )

    string_ts : StringProperty(
        name="TS",
        description="Timestamp - not sure what this is.",
        default="",
        maxlen=1024,
    )

    string_last_ts : StringProperty(
        name="LastUpdatedTimestamp",
        description="Timestamp - last updated timestamp.",
        default="",
        maxlen=1024,
    )

    float_pos_x : FloatProperty(
        name="X", description="The X position of the base in planet space.", default=0.0
    )

    float_pos_y : FloatProperty(
        name="Y", description="The Y position of the base in planet space.", default=0.0
    )

    float_pos_z : FloatProperty(
        name="Z", description="The Z position of the base in planet space.", default=0.0
    )

    float_ori_x : FloatProperty(
        name="X",
        description="The X orientation vector of the base in planet space.",
        default=0.0,
    )

    float_ori_y : FloatProperty(
        name="Y",
        description="The Y orientation vector of the base in planet space.",
        default=0.0,
    )

    float_ori_z : FloatProperty(
        name="Z",
        description="The Z orientation vector of the base in planet space.",
        default=0.0,
    )

    # Unconverted stamps
    LastEditedById : StringProperty(
        name="LastEditedByID",
        description="LastEditedByID.",
        default="",
        maxlen=1024,
    )
    LastEditedByUsername_value : StringProperty(
        name="LastEditedByUsername",
        description="LastEditedByUsername.",
        default="",
        maxlen=1024,
    )
    original_base_version : IntProperty(
        name="OriginalBaseVersion",
        description="OriginalBaseVersion.",
        default=3
    )

    room_vis_switch : IntProperty(name="room_vis_switch", default=0)

    def generate_from_data(self, nms_data):
        # Start new file
        self.new_file()
        # Start bringing the data in.
        if "GalacticAddress" in nms_data:
            self.string_address = str(nms_data["GalacticAddress"])
        if "Position" in nms_data:
            self.float_pos_x = nms_data["Position"][0]
            self.float_pos_y = nms_data["Position"][1]
            self.float_pos_z = nms_data["Position"][2]
        if "Forward" in nms_data:
            self.float_ori_x = nms_data["Forward"][0]
            self.float_ori_y = nms_data["Forward"][1]
            self.float_ori_z = nms_data["Forward"][2]
        if "Name" in nms_data:
            self.string_base = str(nms_data["Name"])
        if "LastUpdateTimestamp" in nms_data:
            self.string_last_ts = str(nms_data["LastUpdateTimestamp"])
        if "Owner" in nms_data:
            Owner_details = nms_data["Owner"]
            self.string_uid = str(Owner_details["UID"])
            self.string_ts = str(Owner_details["TS"])
            self.string_lid = str(Owner_details["LID"])
            self.string_usn = str(Owner_details["USN"])
            self.string_ptk = str(Owner_details["PTK"])
        # Unconverted stamps
        if "LastEditedById" in nms_data:
            self.LastEditedById = str(nms_data["LastEditedById"])
        if "LastEditedByUsername" in nms_data:
            self.LastEditedByUsername_value = str(nms_data["LastEditedByUsername"])
        if "OriginalBaseVersion" in nms_data:
            self.original_base_version = nms_data["OriginalBaseVersion"]
        
        _profile = cProfile.Profile(subcalls=False)
        _profile.enable()



        # Build Objects
        if "Objects" in nms_data:
            PART_BUILDER.build_parts_from_dict(nms_data)

        if "Presets" in nms_data:
            PRESET_BUILDER.build_presets_from_dict(nms_data)

        # Optimise any duplicate power controls.
        power.optimise_control_points()

        _profile.disable()
        _profile.print_stats(sort="cumtime")

    def generate_data(self, capture_presets=False):
        """Export the data in the blender scene to NMS compatible data.
        
        This will slot the data into the clip-board so you can easy copy
        and paste data back and forth between the tool.
        """
        # Try making the address an int, if not it should be a string.
        try:
            galactive_address = int(self.string_address)
        except BaseException:
            galactive_address = self.string_address

        # Try making the timestamp an int, if not it should be a string.
        try:
            ts = int(self.string_ts)
        except:
            ts = self.string_ts

        try:
            last_ts = int(self.string_last_ts)
        except:
            last_ts = self.string_last_ts

        data = {
            "BaseVersion": 4,
            "OriginalBaseVersion":self.original_base_version,
            "GalacticAddress": galactive_address,
            "Position": [
                self.float_pos_x,
                self.float_pos_y,
                self.float_pos_z
            ],
            "Forward": [
                self.float_ori_x,
                self.float_ori_y,
                self.float_ori_z
            ],
            "UserData": 0,
            "LastUpdateTimestamp":last_ts,
            "RID": "",
            "Owner": {
                "UID": self.string_uid,
                "LID": self.string_lid,
                "USN": self.string_usn,
                "PTK": self.string_ptk,
                "TS": ts,
            },
            "Name": self.string_base,
            "BaseType": {"PersistentBaseTypes": "HomePlanetBase"},
            "LastEditedById": self.LastEditedById,
            "LastEditedByUsername": self.LastEditedByUsername_value
        }
        # Capture Individual Objects
        data["Objects"] = PART_BUILDER.get_all_part_data(
            capture_presets=capture_presets
        )
        # Capture Presets.
        if capture_presets:
            data["Presets"] = PRESET_BUILDER.get_all_preset_data()

        return data

    # Import and Export Methods ---
    def import_nms_data(self):
        """Import and build a base based on the contents of user clipboard.

        The clipboard should contain a copy of the base data found in the
        No Man's Sky Save Editor.
        """
        # Read clipboard data.
        clipboard_data = bpy.context.window_manager.clipboard
        try:
            nms_import_data = json.loads(clipboard_data)
        except:
            raise RuntimeError(
                "Could not import base data, are you sure you copied "
                "the data to the clipboard?"
            )
        # Start a new file
        self.generate_from_data(nms_import_data)

    def export_nms_data(self):
        """Generate data and place it into the user's clipboard.
        
        This generates a flat set of individual base parts for NMS to read.
        All preset information is lost in this process.
        """
        data = self.generate_data()
        bpy.context.window_manager.clipboard = json.dumps(data, indent=4)

    # Save and Load Methods ---
    def save_nms_data(self, file_path):
        """Generate data and place it into a json file.
        
        This preserves any presets built in scene.

        Args:
            file_path (str): The path to the json file.
        """
        data = self.generate_data(capture_presets=True)
        # Add .json if it's not specified.
        if not file_path.endswith(".json"):
            file_path += ".json"
        # Save to file path
        with open(file_path, "w") as stream:
            json.dump(data, stream, indent=4)

    def load_nms_data(self, file_path):
        # First load
        with open(file_path, "r") as stream:
            try:
                save_data = json.load(stream)
            except BaseException:
                message = (
                    "Could not load base data, are you sure you "
                    "chose the correct file?"
                )
                raise RuntimeError(message)
        # Build from Data
        self.generate_from_data(save_data)

    def new_file(self):
        """Reset's the entire Blender scene to default.
        
        Note:
            * Removes all base information in the Blender properties.
            * Resets the build part order in the part builder.
            * Removes all items with ObjectID, PresetID and NMS_LIGHT properties.
            * Resets the room visibility switch to default.
        """
        self.string_address = ""
        self.string_base = ""
        self.string_lid = ""
        self.string_ts = ""
        self.string_uid = ""
        self.string_usn = ""
        self.string_ptk = ""
        self.float_pos_x = 0
        self.float_pos_y = 0
        self.float_pos_z = 0
        self.float_ori_x = 0
        self.float_ori_y = 0
        self.float_ori_z = 0
        self.string_last_ts = ""
        self.LastEditedById = ""
        self.original_base_version = 3
        self.LastEditedByUsername_value = ""

        # Restore part builder ordering
        PART_BUILDER.part_order = 0
        # Remove all no mans sky items from scene.
        # Deselect all
        bpy.ops.object.select_all(action="DESELECT")
        # Select NMS Items
        for ob in bpy.data.objects:
            if "ObjectID" in ob:
                ob.hide_select = False
                ob.select_set(True)
            if "PresetID" in ob:
                ob.hide_select = False
                ob.select_set(True)
            if "NMS_LIGHT" in ob:
                ob.hide_viewport = False
                ob.hide_select = False
                ob.select_set(True)
            if "base_builder_item" in ob:
                ob.hide_viewport = False
                ob.hide_select = False
                ob.select_set(True)
        # Remove
        bpy.ops.object.delete()
        # Reset room vis
        self.room_vis_switch = 0

    def toggle_room_visibility(self):
        """Cycle through room visibilities.
        
        Note:
            Visibility types are...
                0: Normal
                1: Ghosted
                2: Invisible
                3: Lit
        """
        # Increment Room Vis
        if self.room_vis_switch < 3:
            self.room_vis_switch += 1
        else:
            self.room_vis_switch = 0

        # Select NMS Items
        invisible_objects = GHOSTED_ITEMS["GHOSTED"]

        # Set Shading.
        if self.room_vis_switch in [0, 1, 2]:
            bpy.context.space_data.shading.type = "SOLID"
            bpy.context.scene.render.engine = "BLENDER_EEVEE"
            # bpy.context.scene.game_settings.material_mode = 'MULTITEXTURE'
        elif self.room_vis_switch in [3]:
            bpy.context.space_data.shading.type = "MATERIAL"
            bpy.context.scene.render.engine = "BLENDER_EEVEE"
            # bpy.context.scene.game_settings.material_mode = 'GLSL'

        # Set Hide
        hidden = True
        if self.room_vis_switch in [0, 1, 3]:
            hidden = False

        # Transparency.
        show_transparent = False
        if self.room_vis_switch in [1]:
            show_transparent = True

        # Hide Select.
        hide_select = False
        if self.room_vis_switch in [1]:
            hide_select = True
        
        # Toggle lights.
        use_lights = self.room_vis_switch in [3]
        bpy.context.space_data.shading.use_scene_lights = use_lights

        # Iterate materials for transparecny.
        # NOTE: Seems in 2.8 you can't set per object alpha toggling anymore :/
        for material in bpy.data.materials:
            material.diffuse_color[3] = 0.07 if show_transparent else 1.0
        
        # Iterate object for selection.
        for ob in bpy.data.objects:
            if "ObjectID" in ob:
                if ob["ObjectID"] in invisible_objects:
                    is_preset = False
                    if "is_preset" in ob:
                        is_preset = ob["is_preset"]
                    # Normal
                    ob.hide_viewport = hidden
                    # ob.show_transparent = show_transparent
                    if not is_preset:
                        ob.hide_select = hide_select
                    ob.select_set(False)

    def duplicate(self):
        """Snaps one object to another based on selection."""
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            ShowMessageBox(
                message="Make sure you have an item selected.", title="Duplicate"
            )
            return

        # Get Selected item.
        target = utils.get_current_selection()
        # Part
        if "ObjectID" in target:
            object_id = target["ObjectID"]
            userdata = target["UserData"]
            # Build Item.
            new_item = PART_BUILDER.build_item(object_id, userdata=userdata)
            # Snap.
            SNAPPER.snap_objects(new_item, target)
        if "PresetID" in target:
            preset_id = target["PresetID"]
            # Build Item.
            new_item = PRESET_BUILDER.build_preset(preset_id)
            # Snap.
            SNAPPER.snap_objects(new_item, target)

    def duplicate_along_curve(self, distance_percentage):
        """Snaps one object to another based on selection."""
        selected_objects = bpy.context.selected_objects

        if len(selected_objects) != 2:
            message = (
                "Make sure you have two items selected. Select the item to"
                " duplicate, then the curve you want to snap to."
            )
            ShowMessageBox(message=message, title="Duplicate Along Curve")
            return {"FINISHED"}

        # Validate gap_distance.
        range_message = "Please choose a value between 0 and 1."
        if distance_percentage <= 0.0:
            ShowMessageBox(message=range_message, title="Duplicate Along Curve")
            return {"FINISHED"}

        if distance_percentage >= 1.0:
            ShowMessageBox(message=range_message, title="Duplicate Along Curve")
            return {"FINISHED"}

        # Figure out selection.
        if "ObjectID" in selected_objects[0] or "PresetID" in selected_objects[0]:
            curve_object = selected_objects[1]
            dup_object = selected_objects[0]
        else:
            curve_object = selected_objects[0]
            dup_object = selected_objects[1]
        # Perform duplication along curve.
        curve.duplicate_along_curve(
            PART_BUILDER, PRESET_BUILDER, dup_object, curve_object, distance_percentage
        )

    def apply_colour(self, colour_index=0, material=None):
        """Snaps one object to another based on selection."""
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            ShowMessageBox(
                message="Make sure you have an item selected.",
                title="Apply Colour"
            )
            return {"FINISHED"}

        # Apply Colour Material.
        for obj in selected_objects:
            _material.assign_material(obj, colour_index, material)

        # Refresh the viewport.
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    def snap(
            self,
            next_source=False,
            prev_source=False,
            next_target=False,
            prev_target=False):
        """Snaps one object to another based on selection."""
        selected_objects = bpy.context.selected_objects

        if len(selected_objects) != 2:
            message = (
                "Make sure you have two items selected. Select the item you"
                " want to snap to, then the item you want to snap."
            )
            ShowMessageBox(message=message, title="Snap")
            return {"FINISHED"}

        # Perform Snap
        source_object = bpy.context.view_layer.objects.active
        target_object = [obj for obj in selected_objects if obj != source_object][0]
        SNAPPER.snap_objects(
            source_object,
            target_object,
            next_source=next_source,
            prev_source=prev_source,
            next_target=next_target,
            prev_target=prev_target,
        )


# UI ---
# File Buttons Panel ---
class NMS_PT_file_buttons_panel(Panel):
    bl_idname = "NMS_PT_file_buttons_panel"
    bl_label = "No Man's Sky Base Builder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        first_column = layout.column(align=True)
        button_row = first_column.row(align=True)
        button_row.operator("nms.new_file")
        save_load_row = first_column.row(align=True)
        save_load_row.operator("nms.save_data", icon="FILE_TICK")
        save_load_row.operator("nms.load_data", icon="FILE_FOLDER")
        nms_row = first_column.row(align=True)
        nms_row.operator("nms.import_nms_data", icon="PASTEDOWN")
        nms_row.operator("nms.export_nms_data", icon="COPYDOWN")


# Base Property Panel ---
class NMS_PT_base_prop_panel(Panel):
    bl_idname = "NMS_PT_base_prop_panel"
    bl_label = "Base Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nms_tool = scene.nms_base_tool
        properties_box = layout.box()
        properties_column = properties_box.column(align=True)
        properties_column.prop(nms_tool, "string_base")
        properties_column.prop(nms_tool, "string_address")
        # Hide these keys as they are too technical for user. 
        # (Also have no idea what they are for...)
        # properties_column.prop(nms_tool, "string_last_ts")
        # properties_column.prop(nms_tool, "original_base_version")
        # properties_column.prop(nms_tool, "LastEditedByUsername_value")
        # properties_column.prop(nms_tool, "LastEditedById")


# Snap Panel ---
class NMS_PT_snap_panel(Panel):
    bl_idname = "NMS_PT_snap_panel"
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nms_tool = scene.nms_base_tool

        snap_box = layout.box()
        snap_column = snap_box.column()
        snap_column.label(text="Visibility")
        # Room Vis Button.
        label = "Exterior Room Visibility: Normal"
        if nms_tool.room_vis_switch == 1:
            label = "Exterior Room Visibility: Ghosted"
        elif nms_tool.room_vis_switch == 2:
            label = "Exterior Room Visibility: Invisible"
        elif nms_tool.room_vis_switch == 3:
            label = "Exterior Room Visibility: Lit"

        snap_column.operator(
            "nms.toggle_room_visibility", icon="CUBE", text=label
        )

        snap_column.label(text="Duplicate")
        snap_column.operator("nms.duplicate", icon="DUPLICATE")
        dup_along_curve = snap_column.operator(
            "nms.duplicate_along_curve", icon="CURVE_DATA"
        )
        # dup_along_curve.distance_percentage = 0.1
        snap_column.label(text="Snap")
        snap_op = snap_column.operator("nms.snap", icon="SNAP_ON")

        target_row = snap_column.row()
        target_row.label(text="Target")
        snap_target_prev = target_row.operator("nms.snap", icon="TRIA_LEFT", text="Prev")
        snap_target_next = target_row.operator("nms.snap", icon="TRIA_RIGHT", text="Next")

        source_row = snap_column.row()
        source_row.label(text="Source")
        snap_source_prev = source_row.operator("nms.snap", icon="TRIA_LEFT", text="Prev")
        snap_source_next = source_row.operator("nms.snap", icon="TRIA_RIGHT", text="Next")

        # Set Snap Operator assignments.
        # Default
        snap_op.prev_source = False
        snap_op.next_source = False
        snap_op.prev_target = False
        snap_op.next_target = False
        # Previous Target.
        snap_target_prev.prev_source = False
        snap_target_prev.next_source = False
        snap_target_prev.prev_target = True
        snap_target_prev.next_target = False
        # Next Target.
        snap_target_next.prev_source = False
        snap_target_next.next_source = False
        snap_target_next.prev_target = False
        snap_target_next.next_target = True
        # Previous Source.
        snap_source_prev.prev_source = True
        snap_source_prev.next_source = False
        snap_source_prev.prev_target = False
        snap_source_prev.next_target = False
        # Next Source.
        snap_source_next.prev_source = False
        snap_source_next.next_source = True
        snap_source_next.prev_target = False
        snap_source_next.next_target = False

# Colour Panel ---
class NMS_PT_colour_panel(Panel):
    bl_idname = "NMS_PT_colour_panel"
    bl_label = "Colour"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nms_tool = scene.nms_base_tool
        pcoll = preview_collections["main"]
        enum_row = layout.row(align=True)
        enum_row.prop(nms_tool, "material_switch", expand=True)
        colour_row_1 = layout.row(align=True)
        colour_row_1.scale_y = 1.3
        colour_row_1.scale_x = 1.3
        for idx in range(16):
            colour_icon = pcoll["{0}_colour".format(idx)]
            colour_op = colour_row_1.operator(
                "nms.apply_colour", text="", icon_value=colour_icon.icon_id
            )
            colour_op.colour_index = idx

# Colour Panel ---
class NMS_PT_logic_panel(Panel):
    bl_idname = "NMS_PT_logic_panel"
    bl_label = "Power and Logic"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nms_tool = scene.nms_base_tool

        layout = self.layout
        box = layout.box()
        col = box.column()
        col.label(text="Electrics")
        row = col.row()
        row.operator("nms.point", icon="EMPTY_DATA")
        row.operator("nms.connect", icon="PARTICLES")
        divide_row = col.row()
        divide_row.operator("nms.divide", icon="LINCURVE")
        divide_row.operator("nms.split", icon="MOD_PHYSICS")

        col.label(text="Logic")
        logic_row = col.row(align=True)
        logic_row.operator("nms.logic_button")
        logic_row.operator("nms.logic_wall_switch")
        logic_row.operator("nms.logic_prox_switch")
        logic_row.operator("nms.logic_inv_switch")
        logic_row.operator("nms.logic_auto_switch")
        logic_row.operator("nms.logic_floor_switch")

# Build Panel ---
class NMS_PT_build_panel(Panel):
    bl_idname = "NMS_PT_build_panel"
    bl_label = "Build"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "No Mans Sky"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nms_tool = scene.nms_base_tool
        layout.prop(nms_tool, "enum_switch", expand=True)
        layout.operator("nms.save_as_preset", icon="SCENE_DATA")
        layout.template_list(
            "NMS_UL_actions_list",
            "compact",
            context.scene,
            "col",
            context.scene,
            "col_idx"
        )

    
class NMS_UL_actions_list(bpy.types.UIList):
    previous_layout = None

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            # Add a category item if the title is specified.
            if item.title:
                layout.label(text=item.title)

            # Draw Parts
            if item.item_type == "parts" and item.description:
                all_parts = [x for x in item.description.split(",") if x]
                part_row = layout.column_flow(columns=3)
                for part in all_parts:
                    operator = part_row.operator(
                        "object.list_build_operator",
                        text=PART_BUILDER.get_nice_name(part),
                    )
                    operator.part_id = part

            # Draw Presets
            if item.item_type == "presets":
                if item.description in PRESET_BUILDER.get_presets():
                    # Create Sub layuts
                    build_area = layout.split(factor=0.7)
                    operator = build_area.operator(
                        "object.list_build_operator", text=item.description
                    )
                    edit_area = build_area.split(factor=0.6)
                    edit_operator = edit_area.operator(
                        "object.list_edit_operator", text="Edit"
                    )
                    delete_operator = edit_area.operator(
                        "object.list_delete_operator", text="X"
                    )
                    operator.part_id = item.description
                    edit_operator.part_id = item.description
                    delete_operator.part_id = item.description


class PartCollection(bpy.types.PropertyGroup):
    title : bpy.props.StringProperty()
    description : bpy.props.StringProperty()
    item_type : bpy.props.StringProperty()

def create_sublists(input_list, n=3):
    """Create a list of sub-lists with n elements."""
    total_list = [input_list[x : x + n] for x in range(0, len(input_list), n)]
    # Fill in any blanks.
    last_list = total_list[-1]
    while len(last_list) < n:
        last_list.append("")
    return total_list

def generate_ui_list_data(item_type="parts", pack=None):
    """Generate a list of Blender UI friendly data of categories and parts.
    
    When we retrieve presets we just want an item name.

    For parts I am doing a trick where I am grouping sets of 3 parts in order
    to make a grid in each UIList entry.

    Args:
        item_type (str): The type of items we want to retrieve
            options - "presets", "parts".
    
    Return:
        list: tuple (str, str): Label and Description of items for the UIList.
    """
    ui_list_data = []
    # Presets
    if "presets" in item_type:
        ui_list_data.append(("Presets", ""))
        for preset in PRESET_BUILDER.get_presets():
            ui_list_data.append(("", preset))
    else:
        # Packs/Parts
        for category in PART_BUILDER.get_categories(pack=pack):
            ui_list_data.append((category, ""))
            category_parts = PART_BUILDER.get_parts_from_category(
                category,
                pack=pack
            )
            new_parts = create_sublists(category_parts)
            for part in new_parts:
                joined_list = ",".join(part)
                ui_list_data.append(("", joined_list))
    return ui_list_data


def refresh_ui_part_list(scene, item_type="parts", pack=None):
    """Refresh the UI List.
    
    Args:
        item_type: The type of items we want to retrieve.
            options - "presets", "parts".
    """
    # Clear the scene col.
    try:
        scene.col.clear()
    except:
        pass

    # Get part data based on
    ui_list_data = generate_ui_list_data(item_type=item_type, pack=pack)
    # Create items with labels and descriptions.
    for i, (label, description) in enumerate(ui_list_data, 1):
        item = scene.col.add()
        item.title = label.title().replace("_", " ")
        item.description = description
        item.item_type = item_type
        item.name = " ".join((str(i), label, description))


# Operators ---
# File Operators ---
class NewFile(bpy.types.Operator):
    bl_idname = "nms.new_file"
    bl_label = "New"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.new_file()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SaveData(bpy.types.Operator):
    bl_idname = "nms.save_data"
    bl_label = "Save"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.save_nms_data(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class LoadData(bpy.types.Operator):
    bl_idname = "nms.load_data"
    bl_label = "Load"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.load_nms_data(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class ImportData(bpy.types.Operator):
    bl_idname = "nms.import_nms_data"
    bl_label = "Import NMS"

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.import_nms_data()
        return {"FINISHED"}


class ExportData(bpy.types.Operator):
    bl_idname = "nms.export_nms_data"
    bl_label = "Export NMS"

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.export_nms_data()
        return {"FINISHED"}


# Tool Operators ---
class ToggleRoom(bpy.types.Operator):
    bl_idname = "nms.toggle_room_visibility"
    bl_label = "Toggle Room Visibility: Normal"

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.toggle_room_visibility()
        return {"FINISHED"}


class SaveAsPreset(bpy.types.Operator):
    bl_idname = "nms.save_as_preset"
    bl_label = "Save As Preset"
    preset_name: bpy.props.StringProperty(name="Preset Name")

    def execute(self, context):
        # Save Preset.
        PRESET_BUILDER.save_preset_data(self.preset_name)
        # Refresh Preset List.
        scene = context.scene
        nms_tool = scene.nms_base_tool
        if nms_tool.enum_switch == {"PRESETS"}:
            refresh_ui_part_list(scene, "presets")
        # Reset string variable.
        self.preset_name = ""
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)




# List Operators ---
class ListBuildOperator(bpy.types.Operator):
    """Build the specified item."""

    bl_idname = "object.list_build_operator"
    bl_label = "Simple Object Operator"
    part_id: StringProperty()

    def execute(self, context):
        # Get Selection
        selection = utils.get_current_selection()
        if self.part_id in PRESET_BUILDER.get_presets():
            new_item = PRESET_BUILDER.build_preset(self.part_id)
        else:
            # Build item
            new_item = PART_BUILDER.build_item(self.part_id)

        if selection:
            SNAPPER.snap_objects(new_item, selection)
        return {"FINISHED"}


class ListEditOperator(bpy.types.Operator):
    """Edit the specified preset."""

    bl_idname = "object.list_edit_operator"
    bl_label = "Edit Preset"
    part_id: StringProperty()

    def execute(self, context):
        nms_tool = context.scene.nms_base_tool
        if self.part_id in PRESET_BUILDER.get_presets():
            nms_tool.new_file()
            PRESET_BUILDER.generate_preset(self.part_id)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class ListDeleteOperator(bpy.types.Operator):
    """Delete the specified preset."""

    bl_idname = "object.list_delete_operator"
    bl_label = "Delete"
    part_id: StringProperty()

    def execute(self, context):
        scene = context.scene
        nms_tool = context.scene.nms_base_tool
        if self.part_id in PRESET_BUILDER.get_presets():
            PRESET_BUILDER.delete_preset(self.part_id)
            if nms_tool.enum_switch == {"PRESETS"}:
                refresh_ui_part_list(scene, "presets")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

# Tool Operators ---
class Duplicate(bpy.types.Operator):
    bl_idname = "nms.duplicate"
    bl_label = "Duplicate"
    

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.duplicate()
        return {"FINISHED"}

class DuplicateAlongCurve(bpy.types.Operator):
    bl_idname = "nms.duplicate_along_curve"
    bl_label = "Duplicate Along Curve"
    distance_percentage: bpy.props.FloatProperty(
        name="Distance Percentage Between Item."
    )

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        nms_tool.duplicate_along_curve(
            distance_percentage=self.distance_percentage
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
        
class ApplyColour(bpy.types.Operator):
    bl_idname = "nms.apply_colour"
    bl_label = "Apply Colour"
    colour_index: IntProperty(default=0)

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        material = nms_tool.material_switch
        nms_tool.apply_colour(
            colour_index=self.colour_index, material=material
        )
        return {"FINISHED"}


class Snap(bpy.types.Operator):
    bl_idname = "nms.snap"
    bl_label = "Snap"

    next_source : BoolProperty()
    prev_source : BoolProperty()
    next_target : BoolProperty()
    prev_target : BoolProperty()

    def execute(self, context):
        scene = context.scene
        nms_tool = scene.nms_base_tool
        kwargs = {
            "next_source": self.next_source,
            "prev_source": self.prev_source,
            "next_target": self.next_target,
            "prev_target": self.prev_target
        }
        nms_tool.snap(**kwargs)
        return {"FINISHED"}

# Logic Operators ---
class Point(bpy.types.Operator):
    bl_idname = "nms.point"
    bl_label = "New Point"

    def execute(self, context):
        point = power.create_point("ARBITRARY_POINT")
        utils.select(point)
        return {"FINISHED"}

class Connect(bpy.types.Operator):
    bl_idname = "nms.connect"
    bl_label = "Connect"

    def execute(self, context):
        # Validate selection.
        selected_objects = bpy.context.selected_objects
        if len(selected_objects) != 2:
            message = (
                "Make sure you have two electric points selected."
            )
            ShowMessageBox(message=message, title="Connect")
            return {"FINISHED"}

        # Build and perform connection .
        start = selected_objects[0]
        end = selected_objects[1]
        # Validate points.
        start, end = power.generate_control_points(start, end)
        if not start and not end:
            message = (
                "These two items are not compatible to connect."
            )
            ShowMessageBox(message=message, title="Connect")
            return {"FINISHED"}

        start_name = start.name
        end_name = end.name
        # Re-obtain objects
        start = utils.get_item_by_name(start_name)
        end = utils.get_item_by_name(end_name)
        # Create new power line.
        line_object = "U_POWERLINE"
        if "power_line" in start:
            line_object = start["power_line"].split(".")[0]
        power_line = PART_BUILDER.build_item(line_object, skip_power_controls=True)
        # Create controls.
        power.create_power_controls(
            power_line,
            start=start,
            end=end
        )
        return {"FINISHED"}

class Divide(bpy.types.Operator):
    bl_idname = "nms.divide"
    bl_label = "Divide"

    def execute(self, context):
        # Get Selected item.
        target = utils.get_current_selection()
        if target["ObjectID"] not in ["U_POWERLINE", "U_PIPELINE", "U_PORTALLINE"]:
            ShowMessageBox(
                message="Make sure you have a powerline item selected.",
                title="Divide"
            )
            return {"FINISHED"}
        # Perform split.
        power.divide(target)
        return {"FINISHED"}


class Split(bpy.types.Operator):
    bl_idname = "nms.split"
    bl_label = "Split"

    def execute(self, context):
        # Get Selected item.
        target = utils.get_current_selection()
        if target["ObjectID"] not in ["U_POWERLINE", "U_PIPELINE", "U_PORTALLINE"]:
            ShowMessageBox(
                message="Make sure you have a powerline item selected.",
                title="Split"
            )
            return {"FINISHED"}
        # Perform split.
        power.split(target, target["ObjectID"])
        return {"FINISHED"}


class LogicButton(bpy.types.Operator):
    bl_idname = "nms.logic_button"
    bl_label = "BTN"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        # Build button.
        button = PART_BUILDER.build_item("U_SWITCHBUTTON")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

class LogicWallSwitch(bpy.types.Operator):
    bl_idname = "nms.logic_wall_switch"
    bl_label = "SWITCH"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        button = PART_BUILDER.build_item("U_SWITCHWALL")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

class LogicProxSwitch(bpy.types.Operator):
    bl_idname = "nms.logic_prox_switch"
    bl_label = "PROX"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        button = PART_BUILDER.build_item("U_SWITCHPROX")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

class LogicInvSwitch(bpy.types.Operator):
    bl_idname = "nms.logic_inv_switch"
    bl_label = "INV"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        button = PART_BUILDER.build_item("U_TRANSISTOR1")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

class LogicAutoSwitch(bpy.types.Operator):
    bl_idname = "nms.logic_auto_switch"
    bl_label = "AUTO"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        button = PART_BUILDER.build_item("U_TRANSISTOR2")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

class LogicFloorSwitch(bpy.types.Operator):
    bl_idname = "nms.logic_floor_switch"
    bl_label = "FLOOR"

    def execute(self, context):
        # Get Selected item.
        selection = utils.get_current_selection()
        button = PART_BUILDER.build_item("U_SWITCHPRESS")
        # Snap to selection.
        if selection:
            SNAPPER.snap_objects(button, selection)
            utils.zero_scale(button)
        # Select new item.
        utils.select(button)
        return {"FINISHED"}

# We can store multiple preview collections here,
# however in this example we only store "main"
preview_collections = {}

# Plugin Registration ---

classes = (
    NMSSettings, 
    
    Snap,
    Point,
    Connect,
    Divide,
    Split,

    LogicButton,
    LogicWallSwitch,
    LogicProxSwitch,
    LogicInvSwitch,
    LogicAutoSwitch,
    LogicFloorSwitch,

    ApplyColour,
    Duplicate,
    DuplicateAlongCurve,
    
    SaveAsPreset,
    ToggleRoom,
    
    NewFile, 
    SaveData,
    LoadData,

    ExportData,
    ImportData,
    
    PartCollection,

    ListDeleteOperator,
    ListEditOperator,
    ListBuildOperator,
    NMS_UL_actions_list,

    NMS_PT_file_buttons_panel,
    NMS_PT_base_prop_panel,
    NMS_PT_snap_panel,
    NMS_PT_colour_panel,
    NMS_PT_logic_panel,
    NMS_PT_build_panel
)

def register():
    # Load Icons.
    pcoll = bpy.utils.previews.new()
    # path to the folder where the icon is
    # the path is calculated relative to this py file inside the addon folder
    my_icons_dir = os.path.join(os.path.dirname(__file__), "images")

    # load a preview thumbnail of a file and store in the previews collection
    # Load Colours
    for idx in range(16):
        pcoll.load(
            "{0}_colour".format(idx),
            os.path.join(my_icons_dir, "{0}.jpg".format(idx)),
            "IMAGE",
        )

    preview_collections["main"] = pcoll

    # Register Plugin
    for _class in classes:
        bpy.utils.register_class(_class)
    bpy.types.Scene.nms_base_tool = PointerProperty(type=NMSSettings)
    bpy.types.Scene.col = bpy.props.CollectionProperty(type=PartCollection)
    bpy.types.Scene.col_idx = bpy.props.IntProperty(default=0)

    refresh_ui_part_list()

def unregister():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

    for _class in reversed(classes):
        bpy.utils.unregister_class(_class)
    del bpy.types.Scene.nms_base_tool


if __name__ == "__main__":
    register()
