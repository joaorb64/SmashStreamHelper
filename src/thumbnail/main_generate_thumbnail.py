# This script can be used to generate thumbnails using ./out/program_state.json and ./thumbnail_base
# Run as python ./src/generate_thumbnail in order to test it

import itertools
from math import cos, radians, sin
import random
import traceback
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from pathlib import Path
import json
import shutil
import datetime
import os
import re
from loguru import logger

from src.TSHGameAssetManager import TSHGameAssetManager
from src.Helpers.TSHLocaleHelper import TSHLocaleHelper
from src.Helpers.TSHDictHelper import *
from src.Helpers.TSHAltTextHelper import generate_youtube
from src.Helpers.TSHDirHelper import TSHResolve

is_preview = False

display_phase = True
use_team_names = False
use_sponsors = True
all_eyesight = False
no_separator = 0
flip_direction = False
smooth_scale = True
no_separator_angle = 45
no_separator_distance = 30
proportional_scaling = True

separator_color_code = "#888888"

crop_borders = []  # left, right, top, bottom
scale_fill_x = 0
scale_fill_y = 0

proportional_zoom = 1


def color_code_to_tuple(color_code):
    raw_color_code = color_code.lstrip("#")
    red = int(raw_color_code[0:2], base=16)
    green = int(raw_color_code[2:4], base=16)
    blue = int(raw_color_code[4:6], base=16)
    color = (red, green, blue)
    return color


def generate_separator_images(thumbnail, color_code="#888888", width=3):
    x_size, y_size = round(thumbnail.width()/2), int(thumbnail.height())
    x_separator = QPixmap(x_size, y_size)
    x_separator.fill(QColor(0, 0, 0, 0))
    y_separator = x_separator.copy(x_separator.rect())

    actual_width_y = round(width*ratio[0])
    actual_width_x = round(width*ratio[1])

    painter = QPainter(x_separator)

    painter.setPen(
        QPen(QColor(color_code), actual_width_x))

    painter.drawLine(0, int(y_size/2), x_size, int(y_size/2))

    painter.end()

    painter = QPainter(y_separator)

    painter.setPen(
        QPen(QColor(color_code), actual_width_y))

    painter.drawLine(int(x_size/2), 0, int(x_size/2), y_size)

    painter.end()

    return (x_separator, y_separator)


def find(element, json):
    keys = element.split('.')
    rv = json
    for key in keys:
        rv = rv[key]
    return rv


def calculate_new_dimensions(current_size, max_size):
    # Use -1 if you do not want to constrain in that dimension
    x_ratio = max_size[0]/current_size.width()
    y_ratio = max_size[1]/current_size.height()

    if max_size[0] < 0 and max_size[1] < 0:
        raise ValueError(
            msg=f"Size cannot be negative, given max size is {max_size}")

    if (x_ratio*current_size.height() > max_size[1]) or x_ratio < 0:
        new_x = y_ratio*current_size.width()
        new_y = max_size[1]
    else:
        new_x = max_size[0]
        new_y = x_ratio*current_size.height()
    return ((round(new_x), round(new_y)))


def resize_image_to_max_size(image: QPixmap, max_size, eyesight_coordinates=None, fill_x=True, fill_y=True, zoom=1):
    current_size = image.size()
    x_ratio = max_size[0]/current_size.width()
    y_ratio = max_size[1]/current_size.height()

    if max_size[0] < 0 or max_size[1] < 0:
        raise ValueError(
            msg=f"Size cannot be negative, given max size is {max_size}")

    resized_eyesight = None
    effective_zoom = zoom
    zoom_step = 0.01
    zoom_flag = False
    while not zoom_flag:
        if (x_ratio < y_ratio):
            new_x = y_ratio*current_size.width()*effective_zoom
            new_y = max_size[1]*effective_zoom
            if eyesight_coordinates:
                resized_eyesight = (
                    round(eyesight_coordinates[0]*y_ratio*effective_zoom), round(eyesight_coordinates[1]*y_ratio*effective_zoom))
        else:
            new_x = max_size[0]*effective_zoom
            new_y = x_ratio*current_size.height()*effective_zoom
            if eyesight_coordinates:
                resized_eyesight = (
                    round(eyesight_coordinates[0]*x_ratio*effective_zoom), round(eyesight_coordinates[1]*x_ratio*effective_zoom))
        if not (new_x < max_size[0] and ("left" in crop_borders) and ("right" in crop_borders)):
            if not (new_y < max_size[1] and ("top" in crop_borders) and ("bottom" in crop_borders)):
                zoom_flag = True
        if not zoom_flag:
            effective_zoom += zoom_step

    new_size = (round(new_x), round(new_y))
    new_image = image.scaled(
        new_size[0],
        new_size[1],
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    # crop
    if not resized_eyesight:
        left = round(-(max_size[0] - new_x)/2)
        top = round(-(max_size[1] - new_y)/2)
        right = round((max_size[0] + new_x)/2)
        bottom = round((max_size[1] + new_y)/2)
    else:
        left = round(resized_eyesight[0]-(max_size[0]/2))
        top = round(resized_eyesight[1]-(max_size[1]/2))
        right = round(resized_eyesight[0]+(max_size[0]/2))
        bottom = round(resized_eyesight[1]+(max_size[1]/2))
        if left < 0:
            left = 0
            right = max_size[0]
        if top < 0:
            top = 0
            bottom = max_size[1]
        if right > new_x:
            right = new_x
            left = new_x - max_size[0]
        if bottom > new_y:
            bottom = new_y
            top = new_y - max_size[1]
    if max_size[0] > new_x:
        left = round(-(max_size[0] - new_x)/2)
        right = round((max_size[0] + new_x)/2)
        if ("left" in crop_borders):
            left = 0
            right = max_size[0]
        if ("right" in crop_borders):
            right = max_size[0]
            left = new_x - max_size[0]
    if max_size[1] > new_y:
        top = round(-(max_size[1] - new_y)/2)
        bottom = round((max_size[1] + new_y)/2)
        if ("top" in crop_borders):
            top = 0
            bottom = max_size[1]
        if ("bottom" in crop_borders):
            bottom = max_size[1]
            top = new_y - max_size[1]

    new_image = create_composite_image(
        new_image, QSize(max_size[0], max_size[1]), (-left, -top))

    return (new_image)


def create_composite_image(image, size, coordinates):
    background = QPixmap(size)
    background.fill(QColor(0, 0, 0, 0))
    painter = QPainter(background)
    painter.drawPixmap(int(coordinates[0]), int(coordinates[1]), image)
    painter.end()
    return (background)


def generate_multicharacter_positions(character_number, center=[0.5, 0.5], radius=0.3, angle=45):
    positions = []

    # For 1 character, just center it
    if character_number == 1:
        radius = 0

    angle_rad = radians(angle+45)

    if character_number == 2:
        angle_rad = radians(angle)

    pendulum = 1

    for i in range(character_number):
        if i > 1:
            if i % 2 == 0:
                pendulum *= -1
            else:
                pendulum *= -1
                pendulum += 1
            i = pendulum

        angle = angle_rad + radians(360/character_number) * i
        pos = [
            center[0] + cos(angle) * radius,
            center[1] + sin(angle) * radius
        ]
        positions.append(pos)

    return positions


def paste_image_matrix(thumbnail, path_matrix, max_size, paste_coordinates, eyesight_matrix, rescaling_matrix, player_index=0, flip_p1=False, flip_p2=False, fill_x=True, fill_y=True, customZoom=1, horizontalAlign=50, verticalAlign=50, uncropped_edges=[]):
    num_line = len(path_matrix)

    global proportional_zoom, no_separator, no_separator_angle, no_separator_distance, is_preview, ratio, separator_color_code, separator_width, smooth_scale
    image_ratio = (max(ratio[0], ratio[1]), max(ratio[0], ratio[1]))

    separatorsPix = QPixmap(thumbnail.width(), thumbnail.height())
    separatorsPix.fill(QColor(0, 0, 0, 0))

    debugPix = QPixmap(thumbnail.width(), thumbnail.height())
    debugPix.fill(QColor(0, 0, 0, 0))

    # if (player_index == 1 and flip_p2) or (player_index == 0 and flip_p1):
    #     paste_coordinates = (
    #         round(thumbnail.width()-paste_coordinates[0]-max_size[0]), paste_coordinates[1])
    # thumbnail = thumbnail.transformed(QTransform().scale(-1, 1))

    for line_index in range(0, len(path_matrix)):
        line = path_matrix[line_index]

        eyesight_line = []

        if eyesight_matrix and len(eyesight_matrix) >= line_index:
            eyesight_line = eyesight_matrix[line_index]

        num_col = len(line)

        for col_index in range(0, len(line))[::-1]:
            if path_matrix[line_index][col_index] == None:
                continue

            chars_in_col = 0
            chars_in_line = 0

            curr_col_index = 0
            curr_line_index = 0

            if flip_direction:
                for l in range(0, len(path_matrix)):
                    if l == line_index:
                        curr_line_index = chars_in_line
                    if path_matrix[l][col_index] != None:
                        chars_in_line += 1
                chars_in_col = len(line)
                curr_col_index = col_index
            else:
                for c in range(0, len(line)):
                    if c == col_index:
                        curr_col_index = chars_in_col
                    if line[c] != None:
                        chars_in_col += 1
                chars_in_line = len(path_matrix)
                curr_line_index = line_index

            individual_max_size = (
                round(max_size[0]/chars_in_col), round(max_size[1]/chars_in_line))
            image_path = line[col_index]

            individual_paste_x = round(
                paste_coordinates[0] + curr_col_index*individual_max_size[0])
            individual_paste_y = round(
                paste_coordinates[1] + curr_line_index*individual_max_size[1])

            if no_separator != 0:
                individual_max_size = (
                    max_size[0], round(max_size[1]/num_line))
                individual_paste_x = paste_coordinates[0]

            logger.info(f"Processing asset: {image_path}")

            pix = QPixmap(image_path, "RGBA")
            tmpWidth = int(pix.width() * image_ratio[0])
            tmpHeight = int(pix.height() * image_ratio[1])
            # pix = pix.scaled(int(pix.width() * image_ratio[0]), int(pix.height() * image_ratio[1]), transformMode=Qt.TransformationMode.SmoothTransformation)
            painter = QPainter(thumbnail)

            eyesight_coordinates = (tmpWidth/2, tmpHeight/2)

            if len(eyesight_line) >= col_index:
                if eyesight_line[col_index] != None:
                    eyesight_coordinates = (
                        eyesight_line[col_index][0] * image_ratio[0],
                        eyesight_line[col_index][1] * image_ratio[1]
                    )

            uncropped_edge = []

            if len(uncropped_edges) >= line_index:
                if len(uncropped_edges[line_index]) >= col_index:
                    uncropped_edge = uncropped_edges[line_index][col_index]

            # For cropped assets, zoom to fill
            # Calculate max zoom
            zoom_x = max_size[0] / tmpWidth
            zoom_y = max_size[1] / tmpHeight

            min_zoom = 1

            # print(rescaling_matrix)

            global proportional_scaling

            if proportional_scaling:
                rescaling_factor = rescaling_matrix[line_index][col_index]
            else:
                rescaling_factor = 1

            # print(uncropped_edge)

            if not uncropped_edge:
                if zoom_x > zoom_y:
                    min_zoom = zoom_x * proportional_zoom * rescaling_factor
                else:
                    min_zoom = zoom_y * proportional_zoom * rescaling_factor
            else:
                if 'u' in uncropped_edge and 'd' in uncropped_edge and 'l' in uncropped_edge and 'r' in uncropped_edge:
                    min_zoom = customZoom * proportional_zoom * rescaling_factor
                elif not 'l' in uncropped_edge and not 'r' in uncropped_edge:
                    min_zoom = zoom_x * proportional_zoom * rescaling_factor
                elif not 'u' in uncropped_edge and not 'd' in uncropped_edge:
                    min_zoom = zoom_y * proportional_zoom * rescaling_factor
                else:
                    min_zoom = customZoom * proportional_zoom * rescaling_factor

            global scale_fill_x, scale_fill_y
            # print("scale_fill", scale_fill_x, scale_fill_y)
            if scale_fill_x and not scale_fill_y:
                min_zoom = zoom_x  * proportional_zoom * rescaling_factor
            elif scale_fill_y and not scale_fill_x:
                min_zoom = zoom_y  * proportional_zoom * rescaling_factor
            elif scale_fill_x and scale_fill_y:
                min_zoom = max(zoom_x, zoom_y) * rescaling_factor

            zoom = max(min_zoom, customZoom * min_zoom)
            if (not 'l' in uncropped_edge and not 'r' in uncropped_edge) or (not 'u' in uncropped_edge and not 'd' in uncropped_edge):
                minZoomWidth = min_zoom*tmpWidth
                minZoomHeight = min_zoom*tmpHeight
                if (not 'l' in uncropped_edge and not 'r' in uncropped_edge) and minZoomWidth != max_size[0]:
                    correction_ratio = max_size[0] / minZoomWidth
                    minZoomWidth = minZoomWidth * correction_ratio
                    minZoomHeight = minZoomHeight * correction_ratio
                    if (not (not 'u' in uncropped_edge and not 'd' in uncropped_edge)) or ((not 'u' in uncropped_edge and not 'd' in uncropped_edge) and minZoomHeight >= max_size[1]):
                        zoom = zoom * correction_ratio
                if (not 'u' in uncropped_edge and not 'd' in uncropped_edge) and minZoomHeight != max_size[1]:
                    correction_ratio = max_size[1] / minZoomHeight
                    minZoomWidth = minZoomWidth * correction_ratio
                    minZoomHeight = minZoomHeight * correction_ratio
                    if (not (not 'l' in uncropped_edge and not 'r' in uncropped_edge)) or ((not 'l' in uncropped_edge and not 'r' in uncropped_edge) and minZoomWidth >= max_size[0]):
                        zoom = zoom * correction_ratio
            # print("zoom", zoom)

            xx = 0
            yy = 0

            customCenter = [horizontalAlign/100.0, verticalAlign/100.0]

            if no_separator != 0:
                customCenter = generate_multicharacter_positions(
                    num_col,
                    center=customCenter,
                    radius=no_separator_distance/100,
                    angle=no_separator_angle
                )[col_index]

            if player_index == 1:
                customCenter[0] = 1 - customCenter[0]

            if (player_index == 1 and flip_p2) or (player_index == 0 and flip_p1):
                customCenter[0] = 1 - customCenter[0]

            if not customCenter:
                customCenter = [0.5, 0.5]

            xx = -eyesight_coordinates[0] * zoom + \
                individual_max_size[0] * customCenter[0]
            yy = -eyesight_coordinates[1] * zoom + \
                individual_max_size[1] * customCenter[1]

            original_xx = xx
            original_yy = yy

            # Max move X
            maxMoveX = individual_max_size[0] - tmpWidth * zoom

            if not 'l' in uncropped_edge:
                if xx > 0:
                    xx = 0

            if not 'r' in uncropped_edge:
                if xx < maxMoveX:
                    xx = maxMoveX

            # Max move Y
            maxMoveY = individual_max_size[1] - tmpHeight * zoom

            if not 'u' in uncropped_edge:
                if yy > 0:
                    yy = 0

            if not 'd' in uncropped_edge:
                if yy < maxMoveY:
                    yy = maxMoveY

            flip = False

            if (player_index == 1 and flip_p2) or (player_index == 0 and flip_p1):
                flip = True

            area = QPixmap(int(individual_max_size[0]), int(
                individual_max_size[1]))
            area.fill(QColor(0, 0, 0, 0))

            areaPaint = QPainter(area)

            transformMode = Qt.TransformationMode.SmoothTransformation

            if not smooth_scale:
                transformMode = Qt.TransformationMode.FastTransformation

            areaPaint.drawPixmap(
                int(xx), int(yy),
                pix
                .scaled(
                    int(zoom*tmpWidth),
                    int(zoom*tmpHeight),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    transformMode
                )
            )

            areaPaint.end()

            if flip:
                area = area.transformed(QTransform().scale(-1, 1))

            painter.drawPixmap(
                int(individual_paste_x),
                int(individual_paste_y),
                area
            )
            painter.end()

            if is_preview:
                global font_1
                draw_text(
                    debugPix,
                    QApplication.translate("Form", "TSH_legacy_00115_{0}").format(
                        "{0:.2f}".format(zoom)) + '%'+"\n",
                    font_1, 24, (0, 0, 0),
                    (round(paste_coordinates[0] + col_index *
                     round(max_size[0]/num_col)), individual_paste_y+2),
                    (round(max_size[0]/num_col), 24),
                    True,
                    (200, 200, 200),
                    (4, 2)
                )

                draw_text(
                    debugPix,
                    QApplication.translate("Form", "TSH_legacy_00116_{0}_{1}").format(
                        int(original_xx - xx), int(original_yy - yy)),
                    font_1, 24, (0, 0, 0),
                    (round(paste_coordinates[0] + col_index *
                     round(max_size[0]/num_col)), individual_paste_y+22),
                    (round(max_size[0]/num_col), 24),
                    True,
                    (200, 200, 200),
                    (4, 2)
                )

            if no_separator == 0:
                separator_right = False
                separator_down = False

                separatorHeight = round(separator_width*ratio[0])
                separatorWidth = round(separator_width*ratio[1])

                if flip_direction:
                    separator_right = curr_col_index < len(line)-1

                    for l in range(line_index+1, len(path_matrix)):
                        if path_matrix[l][col_index] != None:
                            separator_down = True
                            break
                else:
                    separator_down = curr_line_index < len(path_matrix)-1

                    for c in range(col_index+1, len(line)):
                        if line[c] != None:
                            separator_right = True
                            break

                if separator_right and separator_width > 0:
                    painter = QPainter(separatorsPix)
                    painter.setPen(
                        QPen(QColor(separator_color_code), separatorWidth))
                    painter.drawLine(
                        individual_paste_x + individual_max_size[0],
                        individual_paste_y,
                        individual_paste_x + individual_max_size[0],
                        individual_paste_y + individual_max_size[1],
                    )
                    painter.end()

                if separator_down and separator_width > 0:
                    painter = QPainter(separatorsPix)
                    painter.setPen(
                        QPen(QColor(separator_color_code), separatorHeight))
                    painter.drawLine(
                        individual_paste_x,
                        individual_paste_y + individual_max_size[1],
                        individual_paste_x + individual_max_size[0],
                        individual_paste_y + individual_max_size[1],
                    )
                    painter.end()

        painter = QPainter(thumbnail)
        painter.drawPixmap(0, 0, separatorsPix)
        if is_preview:
            painter.drawPixmap(0, 0, debugPix)
        painter.end()

    return (thumbnail)


def paste_characters(thumbnail, data, all_eyesight, used_assets, flip_p1=False, flip_p2=False, fill_x=True, fill_y=True, zoom=1, horizontalAlign=50, verticalAlign=50, scoreboardNumber=1):
    max_x_size = round(
        template_data["character_images"]["dimensions"]["x"]*ratio[0]/2)
    max_y_size = round(
        template_data["character_images"]["dimensions"]["y"]*ratio[1])
    max_size = (max_x_size, max_y_size)
    origin_x_coordinates = [round(template_data["character_images"]["position"]["x"]*ratio[0]), round(
        template_data["character_images"]["position"]["x"]*ratio[0])+max_x_size]
    origin_y_coordinates = [
        round(template_data["character_images"]["position"]["y"]*ratio[1]),
        round(template_data["character_images"]["position"]["y"]*ratio[1])
    ]

    path_matrices = []
    eyesight_matrices = []
    uncropped_edge_matrices = []
    average_size = None
    rescaling_matrices = []

    for i in [0, 1]:
        team_index = i+1

        path_matrix = []
        eyesight_matrix = []
        uncropped_edge_matrix = []
        rescaling_matrix = []

        try:
            current_team = find(
                f"score.{scoreboardNumber}.team.{team_index}.player", data)
        except Exception as e:
            logger.error(traceback.format_exc())
            return

        for player_key in current_team.keys():
            character_list = []
            eyesight_list = []
            uncropped_edge_list = []
            rescaling_list = []
            characters = find(f"{player_key}.character", current_team)
            for character_key in characters.keys():
                try:
                    image_path = find(
                        f"{character_key}.assets.{used_assets}.asset", characters)
                    eyesight_coordinates = None

                    character_path = find(
                        f"{character_key}.assets.{used_assets}", characters)

                    # Eyesight
                    if character_path.get("eyesight"):
                        eyesight_coordinates = (
                            character_path.get("eyesight")["x"], character_path.get("eyesight")["y"])

                    # Uncropped edges
                    uncropped_edges = None

                    if character_path.get("uncropped_edge") is not None:
                        uncropped_edges = character_path.get("uncropped_edge")
                    else:
                        uncropped_edges = []

                    # Average size
                    if character_path.get("average_size") is not None:
                        average_size = character_path.get("average_size")

                    # Rescale
                    rescale_factor = 1

                    if character_path.get("rescaling_factor") is not None:
                        rescale_factor = character_path.get("rescaling_factor")

                    if image_path:
                        character_list.append(image_path)
                        eyesight_list.append(eyesight_coordinates)
                        uncropped_edge_list.append(uncropped_edges)
                        rescaling_list.append(rescale_factor)
                except KeyError:
                    None
            if character_list:
                # For team 1, characters must come from the center
                # so we have to reverse the array
                # but only when drawing separators
                global no_separator
                if i == 0 and not no_separator and not flip_direction:
                    character_list.reverse()
                    eyesight_list.reverse()
                    uncropped_edge_list.reverse()
                    rescaling_list.reverse()

                if no_separator:
                    path_matrix.extend(character_list)
                    eyesight_matrix.extend(eyesight_list)
                    uncropped_edge_matrix.extend(uncropped_edge_list)
                    rescaling_matrix.extend(rescaling_list)
                else:
                    path_matrix.append(character_list)
                    eyesight_matrix.append(eyesight_list)
                    uncropped_edge_matrix.append(uncropped_edge_list)
                    rescaling_matrix.append(rescaling_list)

        if no_separator:
            path_matrix = [path_matrix]
            eyesight_matrix = [eyesight_matrix]
            uncropped_edge_matrix = [uncropped_edge_matrix]
            rescaling_matrix = [rescaling_matrix]

        # Transpose character lists
        if not no_separator and flip_direction:
            path_matrix = list(
                map(list, itertools.zip_longest(*path_matrix, fillvalue=None)))
            eyesight_matrix = list(
                map(list, itertools.zip_longest(*eyesight_matrix, fillvalue=None)))
            uncropped_edge_matrix = list(
                map(list, itertools.zip_longest(*uncropped_edge_matrix, fillvalue=None)))
            rescaling_matrix = list(
                map(list, itertools.zip_longest(*rescaling_matrix, fillvalue=None)))

        path_matrices.append(path_matrix)
        eyesight_matrices.append(eyesight_matrix)
        uncropped_edge_matrices.append(uncropped_edge_matrix)
        rescaling_matrices.append(rescaling_matrix)

    # Calculate proportional scaling
    global proportional_zoom
    proportional_zoom = 1

    if average_size is not None:
        proportional_zoom = 0
        proportional_zoom = max(
            proportional_zoom, max_size[0] / ratio[0] / average_size.get("x") * 1.2)
        proportional_zoom = max(
            proportional_zoom, max_size[1] / ratio[1] / average_size.get("y") * 1.2)
    else:
        # Keeping this as a fallback, but should never enter this block of code
        # print("No proportional size. Calculating.")
        max_width = 0
        max_height = 0

        for path_matrix in path_matrices:
            for player_pathes in path_matrix:
                for path in player_pathes:
                    pix = QPixmap(path)
                    pix = pix.scaled(
                        int(pix.width() * ratio[0]),
                        int(pix.height() * ratio[1]),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    max_width = max(max_width, pix.width())
                    max_height = max(max_height, pix.height())

        if max_width != 0 and max_height != 0:
            proportional_zoom = max(
                proportional_zoom, max_size[0] / max_width * 1.2)
            proportional_zoom = max(
                proportional_zoom, max_size[1] / max_height * 1.2)

    for i in [0, 1]:
        team_index = i+1

        path_matrix = path_matrices[i]
        eyesight_matrix = eyesight_matrices[i]
        uncropped_edge_matrix = uncropped_edge_matrices[i]
        rescale_matrix = rescaling_matrices[i]

        paste_x = origin_x_coordinates[i]
        paste_y = origin_y_coordinates[i]
        paste_coordinates = (paste_x, paste_y)

        thumbnail = paste_image_matrix(
            thumbnail, path_matrix, max_size, paste_coordinates, eyesight_matrix, rescale_matrix, i, flip_p1, flip_p2,
            fill_x, fill_y, zoom, horizontalAlign=horizontalAlign, verticalAlign=verticalAlign, uncropped_edges=uncropped_edge_matrix)

    return (thumbnail)


def draw_text(thumbnail, text, font_data, max_font_size, color, pos, container_size, outline, outline_color, padding=(32, 16), skew=(0, 0)):
    pix = QPixmap(int(container_size[0]), int(container_size[1]))
    pix.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    font = QFont()
    family = font_data["name"]
    font.setFamily(family)
    font.setPixelSize(int(max_font_size))
    type = font_data["fontPath"]
    if "bold" in type.lower():
        font.setBold(True)
    if "italic" in type.lower():
        font.setItalic(True)

    fontMetrics = QFontMetricsF(font)

    while (fontMetrics.height()+2*padding[1] > int(container_size[1])):
        max_font_size -= 1
        if max_font_size <= 0:
            raise ValueError("Text too small, size cannot be negative")
        font.setPixelSize(int(max_font_size))
        fontMetrics = QFontMetricsF(font)

    stretch = 100

    while (fontMetrics.width(text)+2*padding[0] > int(container_size[0])):
        if stretch <= template_data["lower_text_stretch_limit"]:
            max_font_size -= 1
            if max_font_size <= 0:
                raise ValueError("Text too small, size cannot be negative")
            font.setPixelSize(int(max_font_size))
        else:
            stretch -= 1
            font.setStretch(stretch)
        fontMetrics = QFontMetricsF(font)

    text_x = round((padding[0]))
    text_y = round((padding[1]))
    text_coordinates = (text_x, text_y)
    # print(text_coordinates)

    if outline:
        stroke_width = round(8*ratio[1])
    else:
        stroke_width = 0

    path = QPainterPath()

    painter.setFont(font)

    pen = QPen()

    if isinstance(color, tuple):
        color = [color] * len(text)

    pos_x = int(text_coordinates[0]) + (container_size[0] -
                                        padding[0]*2) / 2 - fontMetrics.width(text)/2

    for i, char in enumerate(text):
        path.clear()

        pen.setWidth(stroke_width)
        pen.setColor(QColor(
            outline_color[0],
            outline_color[1],
            outline_color[2]
        ))
        painter.setPen(pen)

        painter.setBrush(QColor(
            color[i][0],
            color[i][1],
            color[i][2]
        ))

        path.addText(
            pos_x,
            int(text_coordinates[1]) + fontMetrics.height()/4 +
            (container_size[1]-padding[1]*2)/2,
            font,
            char
        )

        painter.drawPath(path)

        pen.setWidth(0)
        pen.setColor(QColor(0, 0, 0, 0))
        painter.setPen(pen)
        painter.drawPath(path)

        pos_x += fontMetrics.width(char)

    painter.end()

    pix = pix.transformed(QTransform().shear(radians(skew[0]), radians(
        skew[1])), Qt.TransformationMode.SmoothTransformation)

    # Paste pixmap in the thumbnail
    painter = QPainter(thumbnail)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawPixmap(pos[0], pos[1], pix)
    painter.end()


def paste_player_text(thumbnail, data, use_team_names=False, use_sponsors=True, scoreboardNumber=1):
    text_player_max_dimensions = (round(template_data["character_images"]["dimensions"]["x"]*ratio[0]/2.0), round(
        template_data["player_text"]["dimensions"]["y"]*ratio[1]))
    text_player_coordinates = [
        (round((template_data["character_images"]["position"]["x"])*ratio[0]), round(
            (template_data["player_text"]["height_center"]-(template_data["player_text"]["dimensions"]["y"]/2.0))*ratio[1])),
        (round((template_data["character_images"]["position"]["x"]+(2*template_data["character_images"]["dimensions"]["x"]/4.0))*ratio[0]),
         round((template_data["player_text"]["height_center"]-(template_data["player_text"]["dimensions"]["y"]/2.0))*ratio[1]))
    ]

    font_path = font_1
    # get_text_size_for_height(thumbnail, font_path, pixel_height)
    text_size = template_data["initial_font_size"]*ratio[1]
    player_text_color = text_color[0]

    for i in [0, 1]:
        team_index = i+1
        player_list = []
        color_mask = []
        final_color_mask = []

        if use_team_names and find(f"score.{scoreboardNumber}.team.{team_index}.teamName", data):
            player_name = find(
                f"score.{scoreboardNumber}.team.{team_index}.teamName", data)
            final_color_mask = player_text_color["font_color"]
        else:
            current_team = find(
                f"score.{scoreboardNumber}.team.{team_index}.player", data)
            for key in current_team.keys():
                current_data = ""
                individual_color_mask = []

                team = current_team[key].get("team", "")
                if team and use_sponsors:
                    current_data += team+" "
                    individual_color_mask += [sponsor_color[i]] * len(team+" ")

                current_data += current_team[key].get("name", "")
                individual_color_mask += [player_text_color["font_color"]
                                          ] * len(current_team[key].get("name", ""))

                if current_data:
                    current_data = current_data.strip()

                if (not use_sponsors) or (not current_data):
                    current_data = current_team[key].get("name", "")
                    individual_color_mask += [
                        player_text_color["font_color"]] * len(current_data)
                    if current_data:
                        current_data = current_data.strip()
                if current_data:
                    player_list.append(current_data)
                    color_mask.append(individual_color_mask)

            player_name = " / ".join(player_list)

            final_color_mask = color_mask[0]

            if len(color_mask) > 0:
                for mask in color_mask[1:]:
                    final_color_mask += [player_text_color["font_color"]] * 3
                    final_color_mask += mask

        if use_team_names or len(player_list) > 1:
            player_type = "team"
        else:
            player_type = "player"

        # print(f"Processing {player_type}: {player_name}")

        draw_text(
            thumbnail,
            player_name,
            font_path,
            text_size,
            final_color_mask,
            text_player_coordinates[i],
            text_player_max_dimensions,
            player_text_color["has_outline"],
            player_text_color["outline_color"],
            (
                round(template_data["player_text"]["x_offset"]*ratio[0]),
                round(template_data["player_text"]["y_padding"]*ratio[1])
            ),
            (
                template_data["player_text"].get("skew", {}).get("x", 0),
                template_data["player_text"].get("skew", {}).get("y", 0)
            )
        )


def paste_round_text(thumbnail, data, display_phase=True, scoreboardNumber=1):
    if display_phase:
        if template_data["info_text"]["horizontal"]:
            round_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0]), round((template_data["info_text"]["height_center"]-(
                template_data["info_text"]["dimensions"]["y"]/2.0))*ratio[1]))
            phase_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0])+round((template_data["info_text"]["dimensions"]["x"]/2.0)*ratio[0]), round(
                (template_data["info_text"]["height_center"]-(template_data["info_text"]["dimensions"]["y"]/2.0))*ratio[1]))

            text_max_dimensions = (round((template_data["info_text"]["dimensions"]["x"]/2.0)*ratio[0]), round(
                template_data["info_text"]["dimensions"]["y"]*ratio[1]))
        else:
            y_0 = template_data["info_text"]["height_center"] - \
                (template_data["info_text"]["dimensions"]["y"]/2.0)
            y_1 = template_data["info_text"]["height_center"]
            phase_text_pos = (
                round(template_data["info_text"]["x_position"]*ratio[0]), round(y_0*ratio[1]))
            round_text_pos = (
                round(template_data["info_text"]["x_position"]*ratio[0]), round(y_1*ratio[1]))

            text_max_dimensions = (round((template_data["info_text"]["dimensions"]["x"])*ratio[0]), round(
                (template_data["info_text"]["dimensions"]["y"]/2.0)*ratio[1]))

        text_size = template_data["initial_font_size"]*ratio[1]
        y_padding = round(template_data["info_text"]["y_padding"]*ratio[1])
        if not template_data["info_text"]["horizontal"]:
            y_padding = round(y_padding/2.0)

        draw_text(
            thumbnail,
            find(f"score.{scoreboardNumber}.phase", data),
            font_2,
            text_size,
            text_color[1]["font_color"],
            phase_text_pos,
            text_max_dimensions,
            text_color[1]["has_outline"],
            text_color[1]["outline_color"],
            (
                round(template_data["info_text"]["x_offset"]*ratio[0]/2.0),
                y_padding
            ),
            (
                template_data["info_text"].get("skew", {}).get("x", 0),
                template_data["info_text"].get("skew", {}).get("y", 0)
            )
        )

        draw_text(
            thumbnail,
            find(f"score.{scoreboardNumber}.match", data),
            font_2,
            text_size,
            text_color[1]["font_color"],
            round_text_pos,
            text_max_dimensions,
            text_color[1]["has_outline"],
            text_color[1]["outline_color"],
            (
                round(template_data["info_text"]["x_offset"]*ratio[0]/2.0),
                y_padding
            ),
            (
                template_data["info_text"].get("skew", {}).get("x", 0),
                template_data["info_text"].get("skew", {}).get("y", 0)
            )
        )
    else:
        round_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0]), round((template_data["info_text"]["height_center"]-(
            template_data["info_text"]["dimensions"]["y"]/2.0))*ratio[1]))
        text_max_dimensions = (round((template_data["info_text"]["dimensions"]["x"])*ratio[0]), round(
            template_data["info_text"]["dimensions"]["y"]*ratio[1]))

        text_size = template_data["initial_font_size"]*ratio[1]

        draw_text(
            thumbnail,
            find(f"score.{scoreboardNumber}.match", data),
            font_2,
            text_size,
            text_color[1]["font_color"],
            round_text_pos,
            text_max_dimensions,
            text_color[1]["has_outline"],
            text_color[1]["outline_color"],
            (round(template_data["info_text"]["x_offset"]*ratio[0]),
             round(template_data["info_text"]["y_padding"]*ratio[1]))
        )


def paste_main_icon(thumbnail, icon_path):
    max_x_size = round(
        template_data["icons_position"]["main"]["dimensions"]["x"]*ratio[0])
    max_y_size = round(
        template_data["icons_position"]["main"]["dimensions"]["y"]*ratio[1])
    max_size = (max_x_size, max_y_size)

    icon_image = QPixmap(icon_path, 'RGBA')
    if icon_image.isNull():
        return thumbnail
    icon_size = calculate_new_dimensions(icon_image.size(), max_size)
    icon_image = icon_image.transformed(
        QTransform().scale(
            icon_size[0]/icon_image.width(), icon_size[1]/icon_image.height()),
        Qt.TransformationMode.SmoothTransformation)

    x_offset = template_data["base_ratio"]["x"] / 2.0
    if template_data["icons_position"]["bind_to_character_images"]:
        x_offset = template_data["character_images"]["dimensions"]["x"] / \
            2.0 + template_data["character_images"]["position"]["x"]

    y_offset = template_data["icons_position"]["y_offset"]
    if template_data["icons_position"]["bind_to_character_images"]:
        y_offset = y_offset + \
            template_data["character_images"]["position"]["y"]
    if template_data["icons_position"]["align"].lower() == "bottom":
        y_offset = template_data["base_ratio"]["y"] - \
            template_data["icons_position"]["y_offset"] - \
            icon_image.height()/ratio[1]
        # print(y_offset)
        if template_data["icons_position"]["bind_to_character_images"]:
            y_offset = template_data["character_images"]["position"]["y"] + template_data["character_images"]["dimensions"]["y"] - \
                template_data["icons_position"]["y_offset"] - \
                icon_image.height()/ratio[1]

    icon_x = round(x_offset*ratio[0] - icon_size[0]/2)
    icon_y = y_offset*ratio[1]
    icon_coordinates = (icon_x, icon_y)
    composite_image = create_composite_image(
        icon_image, thumbnail.size(), icon_coordinates)

    painter = QPainter(thumbnail)
    painter.drawPixmap(0, 0, composite_image)
    painter.end()
    return (thumbnail)


def paste_side_icon(thumbnail, icon_path_list):
    if len(icon_path_list) > 2:
        raise (ValueError(msg="Error: icon_path_list has 3 or more elements"))

    max_x_size = round(
        template_data["icons_position"]["side"]["dimensions"]["x"]*ratio[0])
    max_y_size = round(
        template_data["icons_position"]["side"]["dimensions"]["y"]*ratio[0])
    max_size = (max_x_size, max_y_size)

    for index in range(0, len(icon_path_list)):
        icon_path = icon_path_list[index]
        if icon_path:
            icon_image = QPixmap(icon_path, 'RGBA')
            icon_size = calculate_new_dimensions(icon_image.size(), max_size)
            icon_image = icon_image.transformed(
                QTransform().scale(
                    icon_size[0]/icon_image.width(), icon_size[1]/icon_image.height()),
                Qt.TransformationMode.SmoothTransformation)

            y_offset = template_data["icons_position"]["y_offset"]
            if template_data["icons_position"]["bind_to_character_images"]:
                y_offset = y_offset + \
                    template_data["character_images"]["position"]["y"]
            if template_data["icons_position"]["align"].lower() == "bottom":
                y_offset = template_data["base_ratio"]["y"] - \
                    template_data["icons_position"]["y_offset"] - \
                    icon_image.height()/ratio[1]
                # print(y_offset)
                if template_data["icons_position"]["bind_to_character_images"]:
                    y_offset = template_data["character_images"]["position"]["y"] + template_data["character_images"]["dimensions"]["y"] - \
                        template_data["icons_position"]["y_offset"] - \
                        icon_image.height()/ratio[1]

            x_offset = index*template_data["base_ratio"]["x"]
            if template_data["icons_position"]["bind_to_character_images"]:
                x_offset = template_data["character_images"]["position"]["x"] + \
                    index*template_data["character_images"]["dimensions"]["x"]
            x_offset = x_offset - \
                round(template_data["icons_position"]
                      ["side"]["x_offset"]) * ((index*2)-1)
            icon_x = x_offset*ratio[0] - index*icon_size[0]
            icon_y = y_offset*ratio[1]

            icon_coordinates = (round(icon_x), round(icon_y))
            composite_image = create_composite_image(
                icon_image, thumbnail.size(), icon_coordinates)

            painter = QPainter(thumbnail)
            painter.drawPixmap(0, 0, composite_image)
            painter.end()
    return (thumbnail)


def createFalseData(gameAssetManager: TSHGameAssetManager = None, used_assets: str = None):
    # Array [{"name", "asset"}]
    chars = []

    if gameAssetManager and len(gameAssetManager.instance.characters.keys()) > 0:

        for i in range(4):
            asset = None
            if not asset:
                key = list(gameAssetManager.instance.characters.keys())[
                    random.randint(0, len(gameAssetManager.instance.characters)-1)]

                character = gameAssetManager.instance.characters[key]
                skin = random.randint(
                    0, len(gameAssetManager.instance.characters[key]))

                data = gameAssetManager.instance.GetCharacterAssets(
                    character.get("codename"), skin)

                asset = data.get(used_assets)

                if not asset:
                    asset = data.get("full")
                if not asset:
                    asset = data.get("portrait")
                if not asset:
                    asset = data.get("base_files/icon")

            name = key
            if character.get("locale"):
                locale = TSHLocaleHelper.programLocale
                if locale.replace("-", "_") in character["locale"]:
                    name = character["locale"][locale.replace("-", "_")]
                elif re.split("-|_", locale)[0] in character["locale"]:
                    name = character["locale"][re.split("-|_", locale)[0]]

            chars.append({
                "name": name,
                "team": gameAssetManager.instance.selectedGame.get("codename").upper(),
                "asset": {
                    "assets": {
                        "full": asset
                    },
                    "codename": character["codename"],
                    "name": key,
                    "skin": "0"
                }
            })
    else:
        for i in range(4):
            chars.append({
                "name": QApplication.translate("app", "TSH_legacy_00213_{0}").format(i+1),
                "team": QApplication.translate("app", "TSH_legacy_00266_{0}").format(i+1),
                "asset": {
                    "assets": {
                        "full": {
                            "asset": f"./assets/mock_data/mock_asset/full_character_{i}.png",
                            "eyesight": {
                                "x": 540,
                                "y": 126
                            }
                        }
                    },
                    "codename": "character",
                    "name": "Character",
                    "skin": "0"
                },
            })

    # print(chars)

    data = {
        "game": {
            "codename": "test",
            "name": "Test",
            "smashgg_id": 0
        },
        "score": {
            "1": {
                "best_of": 0,
                "match": TSHLocaleHelper.matchNames.get("winners_final"),
                "phase": TSHLocaleHelper.phaseNames.get("group").format("A"),
                "team": {
                    "1": {
                        "losers": False,
                        "player": {
                            "1": {
                                "character": {
                                    "1": chars[0]["asset"],
                                    "2": chars[1]["asset"]
                                },
                                "country": {},
                                "mergedName": f"{chars[0]['team']} | {chars[0]['name']}",
                                "name": chars[0]["name"],
                                "state": {},
                                "team": chars[0]["team"]
                            }
                        },
                        "score": 0,
                        "teamName": QApplication.translate("app", "TSH_legacy_00267_{0}").format("A")
                    },
                    "2": {
                        "losers": False,
                        "player": {
                            "1": {
                                "character": {
                                    "1": chars[2]["asset"]
                                },
                                "country": {},
                                "mergedName": f"{chars[2]['team']} | {chars[2]['name']}",
                                "name": chars[2]["name"],
                                "state": {},
                                "team": chars[2]["team"]
                            },
                            "2": {
                                "character": {
                                    "1": chars[3]["asset"]
                                },
                                "country": {},
                                "mergedName": f"{chars[3]['team']} | {chars[3]['name']}",
                                "name": chars[3]["name"],
                                "state": {},
                                "team": chars[3]["team"]
                            }
                        },
                        "score": 0,
                        "teamName": QApplication.translate("app", "TSH_legacy_00267_{0}").format("B")
                    }
                }
            }
        }
    }
    return data


def remove_special_chars(input_str: str):
    invalid = '<>:"/\\|?* '
    for char in invalid:
        input_str = input_str.replace(char, "")
    return input_str


def generate(settingsManager, isPreview=False, gameAssetManager=None, scoreboardNumber=1):
    # can't import SettingsManager (ImportError: attempted relative import beyond top-level package) so.. parameter ?
    settings = settingsManager.Get("thumbnail_config")

    global template_data
    try:
        with open(settings.get("thumbnail_type"), 'rt') as template_data_file:
            template_data = template_data_file.read()
            template_data = json.loads(template_data)
    except:
        if isPreview:
            return
        raise Exception(f"Thumbnail type could not be loaded")

    global is_preview
    is_preview = isPreview

    data_path = "./out/program_state.json"
    out_path = "./out/thumbnails" if not isPreview else TSHResolve("tmp/thumbnail")
    tmp_path = TSHResolve("tmp")

    # IMG PATH
    foreground_path = settings.get("foreground_path")
    if not foreground_path:
        foreground_path = template_data["default_foreground"]
    background_path = settings.get("background_path")
    if not background_path:
        background_path = template_data["default_background"]
    if not os.path.isfile(background_path):
        raise Exception(f"Background {background_path} doesn't exist !")
    main_icon_path = settings.get("main_icon_path", "")
    side_icon_list = [
        deep_get(settings, f"side_icon_list.L", ""),
        deep_get(settings, f"side_icon_list.R", "")
    ]
    # not blocking so empty
    if side_icon_list[0] and not os.path.isfile(side_icon_list[0]):
        logger.info(f"Top Left Icon {side_icon_list[0]} doesn't exist !")
        side_icon_list[0] = ''
    if side_icon_list[1] and not os.path.isfile(side_icon_list[1]):
        logger.info(f"Top Right Icon {side_icon_list[1]} doesn't exist !")
        side_icon_list[1] = ''
    # BOOLEAN
    display_phase = deep_get(settings, f"display_phase")
    use_team_names = deep_get(settings, "use_team_names")
    use_sponsors = deep_get(settings, "use_sponsors")

    font_list = [
        {
            "name": "Roboto Condensed",
            "type": "Bold",
            "fontPath": "./assets/font/RobotoCondensed.ttf"
        },
        {
            "name": "Roboto Condensed",
            "type": "Bold",
            "fontPath": "./assets/font/RobotoCondensed.ttf"
        }
    ]
    if deep_get(settings, f"player_font"):
        font_list[0] = deep_get(settings, f"player_font")
    if deep_get(settings, f"phase_font"):
        font_list[1] = deep_get(settings, f"phase_font")

    global text_color
    text_color = [
        {
            "font_color": color_code_to_tuple(settings.get("player_font_color", "#FFFFFF")),
            "has_outline": deep_get(settings, f"player_outline", True),
            "outline_color": color_code_to_tuple(deep_get(settings, f"player_outline_color", "#FFFFFF"))
        },
        {
            "font_color": color_code_to_tuple(settings.get("phase_font_color", "#FFFFFF")),
            "has_outline": deep_get(settings, f"phase_outline", True),
            "outline_color": color_code_to_tuple(deep_get(settings, f"phase_outline_color", "#FFFFFF"))
        }
    ]

    global sponsor_color
    sponsor_color = [
        color_code_to_tuple(settings.get("sponsor_font_color_1", "#FFFFFF")),
        color_code_to_tuple(settings.get("sponsor_font_color_2", "#FFFFFF"))
    ]

    zoom = 1

    global smooth_scale

    try:
        with open(data_path, 'rt', encoding='utf-8') as f:
            data = json.loads(f.read())
        # if data missing
        if not data.get("game").get("codename"):
            raise Exception(QApplication.translate(
                "thumb_app", "TSH_legacy_00321"))
        # - if more than one player (team of 2,3 etc), not necessary because test is made on paste_player_text
        for i in [1, 2]:
            if 'name' not in data.get("score").get(str(scoreboardNumber)).get("team").get(str(i)).get("player").get("1"):
                raise Exception(QApplication.translate(
                    "thumb_app", "TSH_legacy_00322_{0}").format(i))
        game_codename = data.get("game").get("codename")
        used_assets = deep_get(settings, f"game.{game_codename}.asset_pack")
        asset_data_path = f"./user_data/games/{game_codename}/{used_assets}/config.json"
        zoom = deep_get(settings, f"game.{game_codename}.zoom", 100)/100
        flip_p1 = deep_get(settings, f"game.{game_codename}.flip_p1")
        flip_p2 = deep_get(settings, f"game.{game_codename}.flip_p2")
        smooth_scale = deep_get(settings, f"game.{game_codename}.smooth_scale")
    except Exception as e:
        if isPreview:
            game_codename = data.get("game").get("codename")
            data = createFalseData(gameAssetManager, deep_get(
                settings, f"game.{game_codename}.asset_pack"))
            used_assets = "full"
            asset_data_path = f"./assets/mock_data/mock_asset/config.json"
            zoom = deep_get(settings, f"game.{game_codename}.zoom", 100)/100
            flip_p1 = deep_get(settings, f"game.{game_codename}.flip_p1")
            flip_p2 = deep_get(settings, f"game.{game_codename}.flip_p2")
            smooth_scale = deep_get(
                settings, f"game.{game_codename}.smooth_scale")
        else:
            raise e

    try:
        with open(asset_data_path, 'rt', encoding='utf-8') as f:
            all_eyesight = json.loads(f.read()).get("eyesights", {})
    except:
        all_eyesight = {}

    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    # for i in range(0, len(font_list)):
    #     if font_list[i]["fontPath"].startswith("http"):
    #         tmp_font_dir = f"{tmp_path}/fonts"
    #         filename, extension = os.path.splitext(font_list[i]["fontPath"])
    #         filename = f"font_{i}{extension}"
    #         Path(tmp_font_dir).mkdir(parents=True, exist_ok=True)
    #         local_font_path = f"{tmp_font_dir}/{filename}"
    #         with open(local_font_path, 'wb') as f:
    #             font_response = requests.get(font_list[i]["fontPath"])
    #             f.write(font_response.content)
    #             font_list[i]["fontPath"] = local_font_path

    global font_1
    global font_2
    font_1 = font_list[0]
    font_2 = font_list[1]

    global separator_color_code
    global separator_width
    separator_color_code = deep_get(settings, f"separator.color", "#FFFFFF")
    separator_width = deep_get(settings, f"separator.width", 5)

    Path(out_path).mkdir(parents=True, exist_ok=True)

    foreground = QPixmap(foreground_path, "RGBA")
    background = QPixmap(background_path, "RGBA")

    if isPreview:
        background = background.scaled(
            int(background.width()/2),
            int(background.height()/2),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

    global ratio
    ratio = (background.width()/template_data["base_ratio"]["x"],
             background.height()/template_data["base_ratio"]["y"])

    global scale_fill_x, scale_fill_y
    scale_fill_x = deep_get(settings, f"game.{game_codename}.scaleFillX", 0)
    scale_fill_y = deep_get(settings, f"game.{game_codename}.scaleFillY", 0)

    global no_separator
    no_separator = deep_get(
        settings, f"game.{game_codename}.hideSeparators", 0)

    global no_separator_angle
    no_separator_angle = deep_get(
        settings, f"game.{game_codename}.noSeparatorAngle", 45)

    global no_separator_distance
    no_separator_distance = deep_get(
        settings, f"game.{game_codename}.noSeparatorDistance", 30)

    global proportional_scaling
    proportional_scaling = deep_get(
        settings, f"game.{game_codename}.proportionalScaling", True)

    global flip_direction
    flip_direction = deep_get(
        settings, f"game.{game_codename}.flipSeparators", 0)

    foreground = foreground.scaled(
        background.width(),
        background.height(),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    thumbnail = QPixmap(background.width(), background.height())
    thumbnail.fill(QColor(0, 0, 0, 0))

    composite_image = create_composite_image(
        background, thumbnail.size(), (0, 0))

    painter = QPainter(thumbnail)
    painter.drawPixmap(0, 0, composite_image)
    painter.drawPixmap(0, 0, background)
    painter.end()

    horizontalAlign = deep_get(
        settings, f"game.{game_codename}.align.horizontal", 50)
    verticalAlign = deep_get(
        settings, f"game.{game_codename}.align.vertical", 40)

    thumbnail = paste_characters(
        thumbnail, data, all_eyesight, used_assets, flip_p1, flip_p2, fill_x=True, fill_y=True, zoom=zoom, horizontalAlign=horizontalAlign, verticalAlign=verticalAlign, scoreboardNumber=scoreboardNumber)
    if thumbnail is None:
        return
    composite_image = create_composite_image(
        foreground, thumbnail.size(), (0, 0))

    painter = QPainter(thumbnail)
    painter.drawPixmap(0, 0, composite_image)
    painter.end()

    paste_player_text(thumbnail, data, use_team_names,
                      use_sponsors, scoreboardNumber=scoreboardNumber)
    paste_round_text(thumbnail, data, display_phase,
                     scoreboardNumber=scoreboardNumber)
    thumbnail = paste_main_icon(thumbnail, main_icon_path)
    thumbnail = paste_side_icon(thumbnail, side_icon_list)

    # TODO get char name
    if not isPreview:
        tag_player1 = find(
            f"score.{scoreboardNumber}.team.1.player.1.name", data)
        tag_player2 = find(
            f"score.{scoreboardNumber}.team.2.player.1.name", data)
        thumbnail_filename = f"{remove_special_chars(tag_player1)}-vs-{remove_special_chars(tag_player2)}-{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')}"
        thumbnail.save(f"{out_path}/{thumbnail_filename}.png")
        thumbnail.save(f"{out_path}/{thumbnail_filename}.jpg")
        if os.path.isdir(tmp_path):
            shutil.rmtree(tmp_path)
        logger.info(
            f"Thumbnail successfully saved as {out_path}/{thumbnail_filename}.png and {out_path}/{thumbnail_filename}.jpg")
        yt_title, yt_description = generate_youtube(
            scoreboardNumber, display_phase)
        with open(f"{out_path}/{thumbnail_filename}_title.txt", "wt", encoding="utf-8") as txt_file:
            txt_file.write(yt_title)
        with open(f"{out_path}/{thumbnail_filename}_desc.txt", "wt", encoding="utf-8") as txt_file:
            txt_file.write(yt_description)
        logger.info(
            f"YouTube data successfully saved as {out_path}/{thumbnail_filename}_title.txt and {out_path}/{thumbnail_filename}_desc.txt")
        return f"{out_path}/{thumbnail_filename}.png"
    else:
        thumbnail_filename = f"template"
        thumbnail.save(f"{out_path}/{thumbnail_filename}.png")
        logger.info(
            f"Thumbnail successfully saved as {out_path}/{thumbnail_filename}.png")
        return f"{out_path}/{thumbnail_filename}.png"
