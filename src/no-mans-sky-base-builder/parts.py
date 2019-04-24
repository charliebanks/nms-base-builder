import logging
import math
import os
from copy import deepcopy

import bpy
import mathutils

from . import material, utils

LOGGER = logging.getLogger(__name__)


class PartBuilder(object):

    FILE_PATH = os.path.dirname(os.path.realpath(__file__))
    MODEL_PATH = os.path.join(FILE_PATH, "models")
    LIGHTS_JSON = os.path.join(FILE_PATH, "lights.json")
    NICE_JSON = os.path.join(FILE_PATH, "nice_names.json")

    def __init__(self):
        """Initialise.

        Create a dictionary reference of part ID's and their OBJ path.
        """
        # Load in light information.
        self.lights_dictionary = utils.load_dictionary(self.LIGHTS_JSON)
        # Load in nice name information.
        self.nice_name_dictionary = utils.load_dictionary(self.NICE_JSON)

        # Construct part information.
        self.part_cache = {}
        self.part_reference = {}
        for category in self.get_categories():
            parts = self.get_objs_from_category(category)
            for part in parts:
                # Get Unique ID.
                unique_id = os.path.basename(part)
                # Construct full path.
                part_path = os.path.join(self.MODEL_PATH, category, part)
                # Place part information into reference.
                self.part_reference[unique_id] = {
                    "category": category,
                    "full_path": part_path
                }

    def get_parts_from_category(self, category):
        """Get all the parts from a specific category."""
        parts = []
        for item, value in self.part_reference.items():
            part_category = value["category"]
            if part_category == category:
                parts.append(item)
        return sorted(parts)

    def clear_cache(self):
        """Clear the part cache."""
        self.part_cache.clear()

    def get_all_nms_objects(self, capture_presets=False):
        """Wrapper to retrieve all blender objects that are made for NMS.

        If capture_presets is True, we get a list of all top level parts and
        preset objects.

        If it's False, we get all top level and preset level NMS items. We
        also excluse all top level preset items. 
        
        Args:
            capture_presets (bool): Decide whether or not we want to be aware
                of presets. If not it will get all individual pieces.
        """
        if capture_presets:
            # Get all preset and top level parts.
            presets = [part for part in bpy.data.objects if "presetID" in part]
            flat_parts = [part for part in bpy.data.objects if part["belongs_to_preset"] is False]
            return presets + flat_parts
        else:
            # Get all individual NMS parts.
            return [part for part in bpy.data.objects if "objectID" in part]

    def get_categories(self):
        """Get the list of categories."""
        return os.listdir(self.MODEL_PATH)

    def get_objs_from_category(self, category):
        """Get a list of parts belonging to a category.
        
        Args:
            category (str): The name of the category.
        """
        category_path = os.path.join(self.MODEL_PATH, category)
        # Validate category path.
        if not os.path.exists(category_path):
            raise RuntimeError(category + " does not exist.")

        all_objs = [
            part for part in os.listdir(category_path) if part.endswith(".obj")
        ]
        file_names = sorted(all_objs)
        return file_names

    def get_obj_path(self, part):
        """Get the path to the OBJ file from a part."""
        part_dictionary = self.part_reference.get(part, {})
        return part_dictionary.get("full_path", None)

    def get_nice_name(self, part):
        """Get a nice version of the part id."""
        part = os.path.basename(part)
        nice_name = part.title().replace("_", " ")
        return self.nice_name_dictionary.get(part, nice_name)

    def retrieve_part(self, part_name):
        """Retrieve the object that represents the part.
        
        There are 3 outcomes.
        - If the object already exists in the scene cache, we can just
            duplciate it.
        - If it doesn't exist in the cache, find the obj path.
        - If the obj path doesn't exist, just createa  cube.
        """
        # Duplicate.
        if part_name in self.part_cache:
            item_object = self.part_cache[part_name]
            # If it's in the cache, but deleted by user, we can import again.
            all_item_names = [item.name for item in bpy.data.objects]
            if item_object.name in all_item_names:
                return utils.duplicate_hierarchy(item)

        # Obj.
        obj_path = self.get_obj_path(part_name) or ""
        # If it exists, import the obj.
        if os.path.isfile(obj_path):
            bpy.ops.import_scene.obj(filepath=obj_path, split_mode="OFF")
            item = bpy.context.selected_objects[0]
        else:
            # If not then create a blender cube.
            item = bpy.ops.mesh.primitive_cube_add()
            item = bpy.context.object

        # Build Light
        item.name = part_name
        item["objectID"] = part_name
        # Create Light.
        self.build_light(item)
        return item

    def get_part_data(self, object, is_preset=False):
        """Given a blender object, generate useful NMS data from it.
        
        Args:
            object (bpy.ob): Blender scene object.
            is_prest (bool): Toggle to ignore data not required for presets.
        Returns:
            dict: Dictionary of information.
        """
        # Get Matrix Data
        ob_world_matrix = object.matrix_world
        # Bring the matrix from Blender Z-Up soace into standard Y-up space.
        mat_rot = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        obj_wm_offset = mat_rot * ob_world_matrix
        # Retrieve Position, Up and At vectors.
        pos = obj_wm_offset.decompose()[0]
        up = utils.get_direction_vector(obj_wm_offset, direction_matrix="up")
        at = utils.get_direction_vector(obj_wm_offset, direction_matrix="at")

        # Build dictionary.
        data = {
            "ObjectID": "^{0}".format(object["objectID"]),
            "Position": [pos[0], pos[1], pos[2]],
            "Up": [up[0], up[1], up[2]],
            "At": [at[0], at[1], at[2]]
        }

        # Add Particular information.
        if not is_preset:
            timestamp = object["Timestamp"]
            user_data = object["UserData"]
            data["Timestamp"] = int(timestamp)
            data["UserData"] = int(user_data)

        return data

    def build_item(
        self,
        part,
        timestamp=1539023700,
        userdata=0,
        position=[0, 0, 0],
        up_vec=[0, 1, 0],
        at_vec=[0, 0, 1]):
        """Build a part given a set of paremeters.
        
        This is they main function of the program for building.

        Args:
            part (str): The part ID.
            timestamp (int): The timestamp of build (this should go away and compute automatically).
            user_data(int): This determines the colour of a part, default is 0 for now.
            position (vector): The location of the part.
            up_vec(vector): The up vector for the part orientation.
            at_vec(vector): The aim vector for the part orientation.
        """
        # Get Current Selection
        current_selection = utils.get_current_selection()

        # Get the obj path.
        item = self.retrieve_part(part)

        # Lock Scale
        item.lock_scale[0] = True
        item.lock_scale[1] = True
        item.lock_scale[2] = True
        # Lock Everything if it's the BASE_FLAG. Things can break if user
        # moves this around.
        if part == "BASE_FLAG":
            item.lock_location[0] = True
            item.lock_location[1] = True
            item.lock_location[2] = True
            item.lock_rotation[0] = True
            item.lock_rotation[1] = True
            item.lock_rotation[2] = True
        
        # Add custom attributes.
        item["objectID"] = part
        item["Timestamp"] = timestamp
        item["belongs_to_preset"] = False
        # Apply Colour
        material.assign_material(item, userdata)

        # Move
        utils.move_to(item, position=position, up=up_vec, at=at_vec)
        
        # Select the new object.
        item.select = True
        return item

    def build_parts_from_json(self, json_path):
        # Validate preset existence.
        if not os.path.isfile(json_path):
            return

        # Load Data.
        data = utils.load_dictionary(json_path)

        if data:
            return self.build_parts_from_dict(data)

    def build_parts_from_dict(self, data):
        """Given the preset name, generate the items in scene.
        
        Args:
            preset_name (str): The name of the preset.
            edit_mode (bool): Toggle to build
        """
       
        # Validate Objects information.
        if "Objects" not in data:
            return

        # Start creating parts.
        parts = []
        for part_data in data["Objects"]:
            part = part_data["ObjectID"].replace("^", "")
            timestamp = part_data["Timestamp"]
            user_data = part_data["UserData"]
            part_position = part_data["Position"]
            up_vec = part_data["Up"]
            at_vec = part_data["At"]
            # Build the item.
            item = self.build_item(
                part,
                timestamp,
                user_data,
                part_position,
                up_vec,
                at_vec
            )
            parts.append(item)

        return parts

    # Lights ---
    def build_light(self, item):
        """If the part is is found to have light information, add them."""

        # Validete NMS object.
        if "objectID" not in item:
            return

        # Get object id from item.
        object_id = item["objectID"]
        # Find light data
        if object_id not in self.lights_dictionary:
            return

        # Build Lights
        light_information = self.lights_dictionary[object_id]
        for idx, light_values in enumerate(light_information.values()):
            # Get Light Properties.
            light_type = light_values["type"]
            light_location = light_values["location"]

            # Create light.
            light = bpy.ops.object.lamp_add(
                type=light_type.upper(),
                location=light_location
            )
            light = bpy.context.object
            light["NMS_LIGHT"] = True
            light.name = "{0}_light{1}".format(item.name, idx)
            data_copy = deepcopy(light_values)

            # Remove invalid blender properties.
            data_copy.pop("type")
            data_copy.pop("location")

            # Apply all other properties to blender object.
            for key, value in data_copy.items():
                if isinstance(value, list):
                    value = mathutils.Vector(tuple(value))
                setattr(light.data, key, value)

            # Parent to object.
            utils.parent(item, light)

            # Disable Selection.
            light.hide = True
            light.hide_select = True