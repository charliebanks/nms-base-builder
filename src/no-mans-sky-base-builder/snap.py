"""Module level utilities for snapping objects together.

Author: Charlie Banks <@charliebanks>

"""

import json
import math
import os
from copy import copy

import mathutils

from . import utils


class Snapper(object):
    # File Paths.
    FILE_PATH = os.path.dirname(os.path.realpath(__file__))
    SNAP_MATRIX_JSON = os.path.join(FILE_PATH, "resources", "snapping_info.json")
    SNAP_PAIR_JSON = os.path.join(FILE_PATH, "resources", "snapping_pairs.json")

    def __init__(self):
        """Initialise."""
        self.snap_matrix_dictionary = utils.load_dictionary(self.SNAP_MATRIX_JSON)
        self.snap_pair_dictionary = utils.load_dictionary(self.SNAP_PAIR_JSON)
        self.snap_cache = {}

    def get_snap_matrices_from_group(self, group):
        """Retrieve all snap points belonging to the snap group.
        
        Args:
            group (str): The top level descriptor for the snap group.
        """
        if group in self.snap_matrix_dictionary:
            if "snap_points" in self.snap_matrix_dictionary[group]:
                return self.snap_matrix_dictionary[group]["snap_points"]

    def get_snap_group_from_part(self, part_id):
        """Search through the grouping dictionary and return the snap group.
        
        Args:
            part_id (str): The ID of the building part.
        """
        for group, value in self.snap_matrix_dictionary.items():
            parts = value["parts"]
            if part_id in parts:
                return group


    def get_snap_pair_options(self, target_item_id, source_item_id):
        """Get the snapping start and end keys corresponding to the
        target and source IDs.

        Args:
            target_item_id (str): 
            source_item_id (str): 
        """
        # Get Groups.
        target_group = self.get_snap_group_from_part(target_item_id)
        source_group = self.get_snap_group_from_part(source_item_id)

        # If no target and no source then we don't do anything.
        if not target_group and not source_group:
            return None

        # Get Pairing.
        if target_group in self.snap_pair_dictionary:
            snapping_dictionary = self.snap_pair_dictionary[target_group]
            if source_group in snapping_dictionary:
                return snapping_dictionary[source_group]

    def get_closest_snap_points(
            self,
            source,
            target,
            source_filter=None,
            target_filter=None):
        """Get the closest snap points of two objects.
        
        Args:
            source (bpy.ob): The source item we are moving.
            target (bpy.ob): The object we are snapping on to.
            source_filter (str): A filter for the snap points being used.
            target_filter (str): A filter for the snap points being used.
        """
        source_snap_group = self.get_snap_group_from_part(source["SnapID"])
        target_snap_group = self.get_snap_group_from_part(target["SnapID"])
        source_matrices = self.get_snap_matrices_from_group(source_snap_group)
        target_matrices = self.get_snap_matrices_from_group(target_snap_group)
        
        lowest_source_key = None
        lowest_target_key = None
        lowest_distance = 9999999
        for source_key, source_info in source_matrices.items():
            # Check source filter.
            if source_filter and source_filter not in source_key:
                continue

            for target_key, target_info in target_matrices.items():
                # Check target filter.
                if target_filter and target_filter not in target_key:
                    continue
                
                # Find the distance and check if its lower then the one
                # stored.
                local_source_matrix = mathutils.Matrix(source_info["matrix"])
                local_target_matrix = mathutils.Matrix(target_info["matrix"])

                source_snap_matrix = source.matrix_world @ local_source_matrix
                target_snap_matrix = target.matrix_world @ local_target_matrix

                distance = self.get_distance_between(
                    source_snap_matrix, target_snap_matrix
                )
                if distance < lowest_distance:
                    lowest_distance = distance
                    lowest_source_key = source_key
                    lowest_target_key = target_key

        return lowest_source_key, lowest_target_key

    def get_matrix_from_key(self, item, key):
        """Get the matrix for a given item and the snap key."""
        # Get relavant snap information from item.
        snap_group = self.get_snap_group_from_part(item["SnapID"])
        snap_matrices = self.get_snap_matrices_from_group(snap_group)
        # Validate key entry.
        if key not in snap_matrices:
            return None

        # Return matrix.
        return snap_matrices[key]["matrix"]

    @staticmethod
    def get_distance_between(matrix1, matrix2):
        """Get the distance between two matrices.
        
        Args:
            matrix1: First matrix input.
            matrix2: Second matrix input.

        Returns:
            float: The distance between the two.
        """
        translate1 = matrix1.decompose()[0]
        translate2 = matrix2.decompose()[0]
        return math.sqrt(
            (translate2.x - translate1.x)**2 + (translate2.y - translate1.y)**2  + (translate2.z - translate1.z)**2
        )

    @staticmethod
    def offset_constraint(source, target):
        """Constrain the position using a location copy constraint.
        
        Args:
            source (bpy.ob): The source item we are moving.
            target (bpy.ob): The object we are snapping on to.
        """
        constraint = source.constraints.new(type='COPY_LOCATION')
        constraint.target = target
        constraint.use_offset = True


    def snap_objects(
            self,
            source,
            target,
            next_source=False,
            prev_source=False,
            next_target=False,
            prev_target=False):
        """Given a source and a target, snap one to the other.
        
        Args:
            source (bpy.ob): The source item we are moving.
            target (bpy.ob): The object we are snapping on to.
            next_source (bool): Use the next source snap point to the current.
            prev_source (bool) Use the previous source snap point to 
                the current.
            next_target (bool) Use the next target snap point to the current.
            prev_target (bool) Use the previous target snap point to
                the current.
        """
        # For preset targets, just snap them together.
        if "PresetID" in target:
            source.matrix_world = copy(target.matrix_world)
            utils.select([source])
            return

        # Get Current Selection Object Type.
        source_key = None
        target_key = None

        source_object_id = None
        target_object_id = None
        # Check of object IDs
        if "SnapID" not in source:
            return False

        if "SnapID" not in target:
            return False

        # If anything, move the item to the target.
        source.matrix_world = copy(target.matrix_world)
        # Ensure selection is set.
        utils.select([source])
        # Get Pairing options.
        snap_pairing_options = self.get_snap_pair_options(
            target["SnapID"],
            source["SnapID"]
        )
        # If no snap details are avaialbe then don't bother.
        if not snap_pairing_options:
            return False

        target_pairing_options = [
            part.strip() for part in snap_pairing_options[0].split(",")
        ]
        source_pairing_options = [
            part.strip() for part in snap_pairing_options[1].split(",")
        ]

        # Get the per item reference.
        target_item_snap_reference = self.snap_cache.get(target.name, {})
        # Get the target item type.
        target_id = target["SnapID"]
        # Find corresponding dict in snap reference.
        target_snap_group = self.get_snap_group_from_part(target_id)
        target_local_matrix_datas = self.get_snap_matrices_from_group(
            target_snap_group
        )
        if target_local_matrix_datas:
            # Get the default target.
            default_target_key = target_pairing_options[0]
            target_key = target_item_snap_reference.get(
                "target",
                default_target_key
            )

            # If the previous key is not in the available options
            # revert to default.
            if target_key not in target_pairing_options:
                target_key = default_target_key

            if next_target:
                target_key = utils.get_adjacent_dict_key(
                    target_pairing_options,
                    target_key,
                    step="next"
                )

            if prev_target:
                target_key = utils.get_adjacent_dict_key(
                    target_pairing_options,
                    target_key,
                    step="prev"
                )

        # Get the per item reference.
        source_item_snap_reference = self.snap_cache.get(
            source.name,
            {}
        )
        # Get the source type.
        source_id = source["SnapID"]
        # Find corresponding dict.
        source_snap_group = self.get_snap_group_from_part(source_id)
        source_local_matrix_datas = self.get_snap_matrices_from_group(
            source_snap_group
        )
        if source_local_matrix_datas:
            default_source_key = source_pairing_options[0]

            # If the source and target are the same, the source key can be
            # the opposite of target.
            if source_id == target_id:
                default_source_key = target_local_matrix_datas[target_key].get(
                    "opposite", default_source_key
                )

            # Get the source key from the item reference, or use the default.
            if (source_id == target_id) and (prev_target or next_target):
                source_key = target_local_matrix_datas[target_key].get(
                    "opposite", default_source_key
                )
            else:
                source_key = source_item_snap_reference.get(
                    "source",
                    default_source_key
                )

            # If the previous key is not in the available options
            # revert to default.
            if source_key not in source_pairing_options:
                source_key = default_source_key

            if next_source:
                source_key = utils.get_adjacent_dict_key(
                    source_pairing_options,
                    source_key,
                    step="next"
                )

            if prev_source:
                source_key = utils.get_adjacent_dict_key(
                    source_pairing_options,
                    source_key,
                    step="prev"
                )
        
        if source_key and target_key:
            # Snap-point to snap-point matrix maths.
            # As I've defined X to be always outward facing, we snap the rotated
            # matrix to the point.
            # s = source, t = target, o = local snap matrix.
            # [(s.so)^-1 * (t.to)] * [(s.so) * 180 rot-matrix * (s.so)^-1]

            # First Create a Flipped Y Matrix based on local offset.
            start_matrix = copy(source.matrix_world)
            start_matrix_inv = copy(source.matrix_world)
            start_matrix_inv.invert()
            offset_matrix = mathutils.Matrix(
                source_local_matrix_datas[source_key]["matrix"]
            )

            # Target Matrix
            target_matrix = copy(target.matrix_world)
            target_offset_matrix = mathutils.Matrix(
                target_local_matrix_datas[target_key]["matrix"]
            )

            # Calculate the location of the target matrix.
            target_snap_matrix = target_matrix @ target_offset_matrix

            # Calculate snap position.
            snap_matrix = start_matrix @ offset_matrix
            snap_matrix_inv = copy(snap_matrix)
            snap_matrix_inv.invert()

            # Rotate by 180 around Y at the origin.
            origin_matrix = snap_matrix_inv @ snap_matrix
            rotation_matrix = mathutils.Matrix.Rotation(
                math.radians(180.0),
                4,
                "Y"
            )
            origin_flipped_matrix = rotation_matrix @ origin_matrix
            flipped_snap_matrix = snap_matrix @ origin_flipped_matrix

            flipped_local_offset = start_matrix_inv @ flipped_snap_matrix

            # Diff between the two.
            flipped_local_offset.invert()
            target_location = target_snap_matrix @ flipped_local_offset

            source.matrix_world = target_location

            # Find the opposite source key and set it.
            next_target_key = target_key

            # If we are working with the same objects.
            next_target_key = source_local_matrix_datas[source_key].get(
                "opposite",
                None
            )

            # Update source item refernece.
            source_item_snap_reference["source"] = source_key
            source_item_snap_reference["target"] = next_target_key

            # Update target item reference.
            target_item_snap_reference["target"] = target_key

            # Update per item reference.
            self.snap_cache[source.name] = source_item_snap_reference
            self.snap_cache[target.name] = target_item_snap_reference

            # Before we do any snapping, we should first see if it needs
            # to be live attachment.
            # If the source is a power control, and the target is not, bind it.
            # if source["SnapID"] == "POWER_CONTROL" and target["SnapID"] != "POWER_CONTROL":
                # self.offset_constraint(source, target)

            # Ensure selection is set.
            utils.select([target, source])

            
            return True
