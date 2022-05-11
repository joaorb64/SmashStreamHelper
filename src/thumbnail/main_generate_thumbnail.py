# This script can be used to generate thumbnails using ./out/program_state.json and ./thumbnail_base
# Run as python ./src/generate_thumbnail in order to test it

from numbers import Rational
import random
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from cgitb import text
from textwrap import fill
from pathlib import Path
import json
from click import style
import requests
import shutil
import string
from copy import deepcopy
import datetime
import os

from src.TSHGameAssetManager import TSHGameAssetManager

display_phase = True
use_team_names = False
use_sponsors = True
all_eyesight = False


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

    return(x_separator, y_separator)


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
    return((round(new_x), round(new_y)))


def resize_image_to_max_size(image: QPixmap, max_size, eyesight_coordinates=None, fill_x=True, fill_y=True, zoom=1):
    current_size = image.size()
    x_ratio = max_size[0]/current_size.width()
    y_ratio = max_size[1]/current_size.height()

    if max_size[0] < 0 or max_size[1] < 0:
        raise ValueError(
            msg=f"Size cannot be negative, given max size is {max_size}")

    resized_eyesight = None
    if (x_ratio < y_ratio and fill_x and fill_y) or (fill_y and not fill_x) or ((not fill_x) and (not fill_y) and (x_ratio > y_ratio)):
        new_x = y_ratio*current_size.width()*zoom
        new_y = max_size[1]*zoom
        if eyesight_coordinates:
            resized_eyesight = (
                round(eyesight_coordinates[0]*y_ratio*zoom), round(eyesight_coordinates[1]*y_ratio*zoom))
    else:
        new_x = max_size[0]*zoom
        new_y = x_ratio*current_size.height()*zoom
        if eyesight_coordinates:
            resized_eyesight = (
                round(eyesight_coordinates[0]*x_ratio*zoom), round(eyesight_coordinates[1]*x_ratio*zoom))

    new_size = (round(new_x), round(new_y))
    image = image.scaled(
        new_size[0], new_size[1], transformMode=Qt.TransformationMode.SmoothTransformation)

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
        if max_size[1] > new_y:
            top = round(-(max_size[1] - new_y)/2)
            bottom = round((max_size[1] + new_y)/2)

    image = image.copy(
        int(left),
        int(top),
        int(right-left),
        int(bottom-top)
    )

    return(image)


def create_composite_image(image, size, coordinates):
    background = QPixmap(size)
    background.fill(QColor(0, 0, 0, 0))
    painter = QPainter(background)
    painter.drawPixmap(int(coordinates[0]), int(coordinates[1]), image)
    painter.end()
    return(background)


def paste_image_matrix(thumbnail, path_matrix, max_size, paste_coordinates, eyesight_matrix, player_index=0, flip_p1=False, flip_p2=False, fill_x=True, fill_y=True, zoom=1):
    separator_h_image, separator_v_image = generate_separator_images(
        thumbnail, separator_color_code, separator_width)
    num_line = len(path_matrix)

    if (player_index == 1 and flip_p2) or (player_index == 0 and flip_p1):
        paste_coordinates = (
            round(thumbnail.width()-paste_coordinates[0]-max_size[0]), paste_coordinates[1])
        thumbnail = thumbnail.transformed(QTransform().scale(-1, 1))

    for line_index in range(0, len(path_matrix)):
        line = path_matrix[line_index]
        eyesight_line = eyesight_matrix[line_index]
        num_col = len(line)
        for col_index in range(0, len(line)):
            individual_max_size = (
                round(max_size[0]/num_col), round(max_size[1]/num_line))
            image_path = line[col_index]
            eyesight_coordinates = eyesight_line[col_index]
            print(f"Processing asset: {image_path}")
            individual_paste_x = round(
                paste_coordinates[0] + col_index*individual_max_size[0])
            individual_paste_y = round(
                paste_coordinates[1] + line_index*individual_max_size[1])
            individual_paste_coordinates = (
                individual_paste_x, individual_paste_y)
            character_image = QPixmap("./"+image_path, 'RGBA')
            character_image = resize_image_to_max_size(
                character_image, individual_max_size, eyesight_coordinates, fill_x, fill_y, zoom)
            composite_image = create_composite_image(
                character_image, thumbnail.size(), individual_paste_coordinates)
            painter = QPainter(thumbnail)
            painter.drawPixmap(0, 0, composite_image)
            painter.end()

            # crop
            left = round(0)
            top = round(0)
            right = round(separator_v_image.width())
            bottom = round(individual_max_size[1])
            separator_v_image = separator_v_image.copy(
                left, top, right-left, bottom-top)
            separator_v_offset = max_size[0]/num_col
            for i in range(1, num_col):
                separator_paste_x = round(
                    paste_coordinates[0]-(separator_v_image.width()/2)+i*separator_v_offset)
                separator_paste_y = individual_paste_y
                separator_paste_coordinates = (
                    separator_paste_x, separator_paste_y)
                composite_image = create_composite_image(
                    separator_v_image, thumbnail.size(), separator_paste_coordinates)
                painter = QPainter(thumbnail)
                painter.drawPixmap(0, 0, composite_image)
                painter.end()

        # crop
        left = round(0)
        top = round(0)
        right = round(max_size[0])
        bottom = round(separator_h_image.height())
        separator_h_image = separator_h_image.copy(
            left, top, right-left, bottom-top)
        separator_h_offset = max_size[1]/num_line
        for i in range(1, num_line):
            separator_paste_x = paste_coordinates[0]
            separator_paste_y = round(
                paste_coordinates[1]-(separator_h_image.height()/2)+i*separator_h_offset)
            separator_paste_coordinates = (
                separator_paste_x, separator_paste_y)
            composite_image = create_composite_image(
                separator_h_image, thumbnail.size(), separator_paste_coordinates)
            painter = QPainter(thumbnail)
            painter.drawPixmap(0, 0, composite_image)
            painter.end()

    if (player_index == 1 and flip_p2) or (player_index == 0 and flip_p1):
        thumbnail = thumbnail.transformed(QTransform().scale(-1, 1))

    return(thumbnail)


def paste_characters(thumbnail, data, all_eyesight, used_assets, flip_p1=False, flip_p2=False, fill_x=True, fill_y=True, zoom=1):
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

    for i in [0, 1]:
        team_index = i+1
        path_matrix = []
        eyesight_matrix = []
        current_team = find(f"score.team.{team_index}.player", data)
        for player_key in current_team.keys():
            character_list = []
            eyesight_list = []
            characters = find(f"{player_key}.character", current_team)
            for character_key in characters.keys():
                try:
                    image_path = find(
                        f"{character_key}.assets.{used_assets}.asset", characters)
                    eyesight_coordinates = None

                    character_path = find(
                        f"{character_key}.assets.{used_assets}", characters)

                    if character_path.get("eyesight"):
                        eyesight_coordinates = (
                            character_path.get("eyesight")["x"], character_path.get("eyesight")["y"])

                    print(eyesight_coordinates)
                    if image_path:
                        character_list.append(image_path)
                        eyesight_list.append(eyesight_coordinates)
                except KeyError:
                    None
            if character_list:
                # For team 1, characters must come from the center
                # so we have to reverse the array
                if i == 0:
                    character_list.reverse()
                    eyesight_list.reverse()
                path_matrix.append(character_list)
                eyesight_matrix.append(eyesight_list)

        paste_x = origin_x_coordinates[i]
        paste_y = origin_y_coordinates[i]
        paste_coordinates = (paste_x, paste_y)
        thumbnail = paste_image_matrix(
            thumbnail, path_matrix, max_size, paste_coordinates, eyesight_matrix, i, flip_p1, flip_p2, fill_x, fill_y, zoom)

    return(thumbnail)


def draw_text(thumbnail, text, font_data, max_font_size, color, pos, container_size, outline, outline_color, padding=(32, 16)):
    painter = QPainter(thumbnail)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    font = QFont()
    family = font_data["name"]
    font.setFamily(family)
    font.setPixelSize(int(max_font_size))
    type = font_data["type"]
    if "bold" in type.lower():
        font.setBold(True)
    if "italic" in type.lower():
        font.setItalic(True)

    fontMetrics = QFontMetricsF(font)

    while(fontMetrics.height()+2*padding[1] > int(container_size[1])):
        max_font_size -= 1
        if max_font_size <= 0:
            raise ValueError("Text too small, size cannot be negative")
        font.setPixelSize(int(max_font_size))
        fontMetrics = QFontMetricsF(font)

    stretch = 100

    while(fontMetrics.width(text)+2*padding[0] > int(container_size[0])):
        if stretch <= template_data["lower_text_stretch_limit"]:
            max_font_size -= 1
            if max_font_size <= 0:
                raise ValueError("Text too small, size cannot be negative")
            font.setPixelSize(int(max_font_size))
        else:
            stretch -= 1
            font.setStretch(stretch)
        fontMetrics = QFontMetricsF(font)

    text_x = round((pos[0]+padding[0]))
    text_y = round((pos[1]+padding[1]))
    text_coordinates = (text_x, text_y)
    print(text_coordinates)

    if outline:
        stroke_width = round(8*ratio[1])
    else:
        stroke_width = 0

    path = QPainterPath()

    painter.setFont(font)

    pen = QPen()
    pen.setWidth(stroke_width)
    pen.setColor(QColor(
        outline_color[0],
        outline_color[1],
        outline_color[2]
    ))
    painter.setPen(pen)

    painter.setBrush(QColor(
        color[0],
        color[1],
        color[2]
    ))

    path.addText(
        int(text_coordinates[0]) +
        (container_size[0] - padding[0]*2) /
        2 - fontMetrics.width(text)/2,
        int(text_coordinates[1]) + fontMetrics.height()/4 +
        (container_size[1]-padding[1]*2)/2,
        font,
        text
    )

    painter.drawPath(path)

    pen.setWidth(0)
    pen.setColor(QColor(0, 0, 0, 0))
    painter.setPen(pen)
    painter.drawPath(path)

    painter.end()


def paste_player_text(thumbnail, data, use_team_names=False, use_sponsors=True):
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
        if use_team_names:
            player_name = find(f"score.team.{team_index}.teamName", data)
        else:
            current_team = find(f"score.team.{team_index}.player", data)
            for key in current_team.keys():
                current_data = current_team[key].get("mergedName")
                if current_data:
                    current_data = current_data.rstrip("[L]").strip()
                if (not use_sponsors) or (not current_data):
                    current_data = current_team[key].get("name")
                    if current_data:
                        current_data = current_data.strip()
                if current_data:
                    player_list.append(current_data)
            player_name = " / ".join(player_list)

        if use_team_names or len(player_list) > 1:
            player_type = "team"
        else:
            player_type = "player"

        print(f"Processing {player_type}: {player_name}")

        draw_text(
            thumbnail,
            player_name,
            font_path,
            text_size,
            player_text_color["font_color"],
            text_player_coordinates[i],
            text_player_max_dimensions,
            player_text_color["has_outline"],
            player_text_color["outline_color"],
            (round(template_data["player_text"]["x_offset"]*ratio[0]),
             round(template_data["player_text"]["y_padding"]*ratio[1]))
        )


def paste_round_text(thumbnail, data, display_phase=True):
    if display_phase:
        if template_data["info_text"]["horizontal"]:
            phase_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0]), round((template_data["info_text"]["height_center"]-(
                template_data["info_text"]["dimensions"]["y"]/2.0))*ratio[1]))
            round_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0])+round((template_data["info_text"]["dimensions"]["x"]/2.0)*ratio[0]), round(
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
            find(f"score.phase", data),
            font_2,
            text_size,
            text_color[1]["font_color"],
            phase_text_pos,
            text_max_dimensions,
            text_color[1]["has_outline"],
            text_color[1]["outline_color"],
            (round(template_data["info_text"]
             ["x_offset"]*ratio[0]/2.0), y_padding)
        )

        draw_text(
            thumbnail,
            find(f"score.match", data),
            font_2,
            text_size,
            text_color[1]["font_color"],
            round_text_pos,
            text_max_dimensions,
            text_color[1]["has_outline"],
            text_color[1]["outline_color"],
            (round(template_data["info_text"]
             ["x_offset"]*ratio[0]/2.0), y_padding)
        )
    else:
        round_text_pos = (round(template_data["info_text"]["x_position"]*ratio[0]), round((template_data["info_text"]["height_center"]-(
            template_data["info_text"]["dimensions"]["y"]/2.0))*ratio[1]))
        text_max_dimensions = (round((template_data["info_text"]["dimensions"]["x"])*ratio[0]), round(
            template_data["info_text"]["dimensions"]["y"]*ratio[1]))

        text_size = template_data["initial_font_size"]*ratio[1]

        draw_text(
            thumbnail,
            find(f"score.match", data),
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
    if icon_path:
        max_x_size = round(
            template_data["icons_position"]["main"]["dimensions"]["x"]*ratio[0])
        max_y_size = round(
            template_data["icons_position"]["main"]["dimensions"]["y"]*ratio[1])
        max_size = (max_x_size, max_y_size)

        icon_image = QPixmap(icon_path, 'RGBA')
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
            print(y_offset)
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
    return(thumbnail)


def paste_side_icon(thumbnail, icon_path_list):
    if len(icon_path_list) > 2:
        raise(ValueError(msg="Error: icon_path_list has 3 or more elements"))

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
                print(y_offset)
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
    return(thumbnail)


def createFalseData(gameAssetManager: TSHGameAssetManager = None, used_assets: str = None):
    # Array [{"name", "asset"}]
    chars = []

    if gameAssetManager and len(gameAssetManager.instance.characters.keys()) > 0:

        for i in range(4):
            key = list(gameAssetManager.instance.characters.keys())[
                random.randint(0, len(gameAssetManager.instance.characters)-1)]

            character = gameAssetManager.instance.characters[key]

            data = gameAssetManager.instance.GetCharacterAssets(
                character.get("codename"), 0)

            asset = data.get(used_assets)

            if not asset:
                asset = data.get("full")
            if not asset:
                asset = data.get("portrait")

            chars.append({
                "name": key,
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
                "name": QApplication.translate("app","Player {0}").format(i+1),
                "team": QApplication.translate("app","Sponsor {0}").format(i+1),
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

    print(chars)

    data = {
        "game": {
            "codename": "test",
            "name": "Test",
            "smashgg_id": 0
        },
        "score": {
            "best_of": 0,
            "match": QApplication.translate("app","Winners Finals"),
            "phase": QApplication.translate("app","Pool {0}").format("A"),
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
                    "teamName": QApplication.translate("app","Team {0}").format("A")
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
                    "teamName": QApplication.translate("app","Team {0}").format("B")
                }
            }
        }
    }
    return data


def generate(settingsManager, isPreview=False, gameAssetManager=None):
    # can't import SettingsManager (ImportError: attempted relative import beyond top-level package) so.. parameter ?
    settings = settingsManager.Get("thumbnail")

    data_path = "./out/program_state.json"
    out_path = "./out/thumbnails" if not isPreview else "./tmp/thumbnail"
    tmp_path = "./tmp"

    # IMG PATH
    foreground_path = settings["foreground_path"]
    if not os.path.isfile(foreground_path):
        raise Exception(f"Foreground {foreground_path} doesn't exist !")
    background_path = settings["background_path"]
    if not os.path.isfile(background_path):
        raise Exception(f"Background {background_path} doesn't exist !")
    main_icon_path = settings["main_icon_path"]
    if main_icon_path and not os.path.isfile(main_icon_path):
        raise Exception(f"Main Icon {main_icon_path} doesn't exist !")
    side_icon_list = settings["side_icon_list"]
    # not blocking so empty
    if side_icon_list[0] and not os.path.isfile(side_icon_list[0]):
        print(f"Top Left Icon {side_icon_list[0]} doesn't exist !")
        side_icon_list[0] = ''
    if side_icon_list[1] and not os.path.isfile(side_icon_list[1]):
        print(f"Top Right Icon {side_icon_list[1]} doesn't exist !")
        side_icon_list[1] = ''
    # BOOLEAN
    display_phase = settings["display_phase"]
    use_team_names = settings["use_team_names"]
    use_sponsors = settings["use_sponsors"]
    flip_p1 = settings["flip_p1"]
    flip_p2 = settings["flip_p2"]

    font_list = ["./assets/font/OpenSans/OpenSans-Bold.ttf",
                 "./assets/font/OpenSans/OpenSans-Semibold.ttf"]
    if settings["font_list"][0]:
        font_list[0] = settings["font_list"][0]
    if settings["font_list"][1]:
        font_list[1] = settings["font_list"][1]

    global text_color
    text_color = [
        {
            "font_color": color_code_to_tuple(settings["font_color"][0]),
            "has_outline": settings["font_outline_enabled"][0],
            "outline_color": color_code_to_tuple(settings["font_outline_color"][0])
        },
        {
            "font_color": color_code_to_tuple(settings["font_color"][1]),
            "has_outline": settings["font_outline_enabled"][1],
            "outline_color": color_code_to_tuple(settings["font_outline_color"][1])
        }
    ]

    zoom = 1

    try:
        with open(data_path, 'rt', encoding='utf-8') as f:
            data = json.loads(f.read())
        # if data missing
        if not data.get("game").get("codename"):
            raise Exception(QApplication.translate("thumb_app", "Please select a game first"))
        # - if more than one player (team of 2,3 etc), not necessary because test is made on paste_player_text
        for i in [1, 2]:
            if 'name' not in data.get("score").get("team").get(str(i)).get("player").get("1"):
                raise Exception(QApplication.translate("thumb_app", "Player {0} tag missing").format(i))

        game_codename = data.get("game").get("codename")
        used_assets = settings[f"asset/{game_codename}"]
        asset_data_path = f"./user_data/games/{game_codename}/{used_assets}/config.json"
        zoom = settings.get(f"zoom/{game_codename}", 100)/100
    except Exception as e:
        if isPreview:
            game_codename = data.get("game").get("codename")
            data = createFalseData(
                gameAssetManager, settings.get(f"asset/{game_codename}"))
            used_assets = "full"
            asset_data_path = f"./assets/mock_data/mock_asset/config.json"
            zoom = settings.get(f"zoom/{game_codename}", 100)/100
        else:
            raise e

    with open(asset_data_path, 'rt', encoding='utf-8') as f:
        all_eyesight = json.loads(f.read()).get("eyesights")

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
    separator_color_code = settings["separator"]["color"]
    separator_width = settings["separator"]["width"]

    Path(out_path).mkdir(parents=True, exist_ok=True)

    foreground = QPixmap(foreground_path, "RGBA")
    background = QPixmap(background_path, "RGBA")
    global template_data
    with open(settings["thumbnail_type"], 'rt') as template_data_file:
        template_data = template_data_file.read()
        template_data = json.loads(template_data)

    if isPreview:
        background = background.scaled(
            int(background.width()/2),
            int(background.height()/2),
            transformMode=Qt.TransformationMode.SmoothTransformation
        )

    global ratio
    ratio = (background.width()/template_data["base_ratio"]["x"],
             background.height()/template_data["base_ratio"]["y"])

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

    thumbnail = paste_characters(
        thumbnail, data, all_eyesight, used_assets, flip_p1, flip_p2, fill_x=True, fill_y=True, zoom=zoom)
    composite_image = create_composite_image(
        foreground, thumbnail.size(), (0, 0))

    painter = QPainter(thumbnail)
    painter.drawPixmap(0, 0, composite_image)
    painter.end()

    paste_player_text(thumbnail, data, use_team_names, use_sponsors)
    paste_round_text(thumbnail, data, display_phase)
    thumbnail = paste_main_icon(thumbnail, main_icon_path)
    thumbnail = paste_side_icon(thumbnail, side_icon_list)

    # TODO get char name
    if not isPreview:
        tag_player1 = find("score.team.1.player.1.name", data)
        tag_player2 = find("score.team.2.player.1.name", data)
        thumbnail_filename = f"{tag_player1}-vs-{tag_player2}-{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')}"
        thumbnail.save(f"{out_path}/{thumbnail_filename}.png")
        thumbnail.save(f"{out_path}/{thumbnail_filename}.jpg")
        if os.path.isdir(tmp_path):
            shutil.rmtree(tmp_path)
        print(
            f"Thumbnail successfully saved as {out_path}/{thumbnail_filename}.png and {out_path}/{thumbnail_filename}.jpg")
        return f"{out_path}/{thumbnail_filename}.png"
    else:
        thumbnail_filename = f"template"
        thumbnail.save(f"{out_path}/{thumbnail_filename}.png")
        print(
            f"Thumbnail successfully saved as {out_path}/{thumbnail_filename}.png")
        return f"{out_path}/{thumbnail_filename}.png"
