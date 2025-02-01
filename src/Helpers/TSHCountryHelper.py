import re
import unicodedata
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import requests
import os
import traceback

from .TSHDirHelper import TSHResolve
from .TSHDictHelper import deep_get
from ..TournamentDataProvider import TournamentDataProvider
from .TSHLocaleHelper import TSHLocaleHelper
import json
from loguru import logger


class TSHCountryHelperSignals(QObject):
    countriesUpdated = Signal()


class TSHCountryHelper(QObject):
    instance: "TSHCountryHelper" = None

    countries_json = {}
    countries = {}
    cities = {}
    countryModel = None
    signals = TSHCountryHelperSignals()

    def __init__(self) -> None:
        super().__init__()
        self.UpdateCountriesFile()

    def UpdateCountriesFile(self):
        class DownloaderThread(QThread):
            def run(self):
                try:
                    url = 'https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/refs/heads/master/json/countries%2Bstates%2Bcities.json'
                    r = requests.get(url, allow_redirects=True)
                    tmp_file = TSHResolve(
                        './assets/countries+states+cities.json.tmp')

                    with open(tmp_file, 'wb') as f:
                        f.write(r.content)

                    try:
                        # Test if downloaded JSON is valid
                        json.load(open(tmp_file))

                        # Remove old file, overwrite with new one
                        os.remove('./assets/countries+states+cities.json')
                        os.rename(tmp_file,
                                  './assets/countries+states+cities.json')

                        logger.info("Countries file updated")
                        TSHCountryHelper.LoadCountries()
                    except:
                        logger.error("Countries files download failed")
                except Exception as e:
                    logger.error(
                        "Could not update countries+states+cities.json: "+str(e))
        downloaderThread = DownloaderThread(self)
        downloaderThread.start()

    def remove_accents_lower(input_str):
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

    def GetBasicCountryInfo(country_code):
        if not country_code in TSHCountryHelper.countries:
            return {}

        return {
            "name": TSHCountryHelper.countries[country_code]["name"],
            "display_name": TSHCountryHelper.countries[country_code]["display_name"],
            "en_name": TSHCountryHelper.countries[country_code]["en_name"],
            "code": TSHCountryHelper.countries[country_code]["code"],
            "latitude": TSHCountryHelper.countries[country_code]["latitude"],
            "longitude": TSHCountryHelper.countries[country_code]["longitude"],
            "asset": f'./assets/country_flag/{country_code.lower()}.png'
        }

    def LoadCountries():
        try:
            f = open("./assets/countries+states+cities.json",
                     'r', encoding='utf-8')
            countries_json = json.loads(f.read())
            TSHCountryHelper.countries_json = countries_json

            # Setup countries - states
            for c in countries_json:
                # Load display name
                display_name = c["name"]

                locale = TSHLocaleHelper.programLocale
                if locale.replace("_", "-") in c["translations"]:
                    display_name = c["translations"][locale.replace(
                        "_", "-")]
                elif re.split("-|_", locale)[0] in c["translations"]:
                    display_name = c["translations"][re.split(
                        "-|_", locale)[0]]

                # Load display name
                export_name = c["name"]

                locale = TSHLocaleHelper.exportLocale
                if locale.replace("_", "-") in c["translations"]:
                    export_name = c["translations"][locale.replace(
                        "_", "-")]
                elif re.split("-|_", locale)[0] in c["translations"]:
                    export_name = c["translations"][re.split(
                        "-|_", locale)[0]]

                ccode = c.get("iso2") if not c.get("iso2").isdigit() else "".join([
                    word[0] for word in re.split(r'\s+|-', c.get("name"))])

                TSHCountryHelper.countries[c["iso2"]] = {
                    "name": export_name,
                    "display_name": display_name,
                    "en_name": c.get("name"),
                    "code": ccode,
                    "latitude": c.get("latitude"),
                    "longitude": c.get("longitude"),
                    "states": {}
                }

                for s in c.get("states", []):
                    if s.get("state_code") is None:
                        continue

                    scode = s.get("state_code") if not s.get("state_code").isdigit() else "".join([
                        word[0] for word in re.split(r'\s+|-', s.get("name").strip()) if len(word) > 0])

                    TSHCountryHelper.countries[c["iso2"]]["states"][s["state_code"]] = {
                        "name": s.get("name"),
                        "code": scode,
                        "original_code": s.get("state_code"),
                        "latitude": s.get("latitude"),
                        "longitude": s.get("longitude"),
                    }

            # Setup model
            TSHCountryHelper.countryModel = QStandardItemModel()

            noCountry = QStandardItem()
            noCountry.setData({}, Qt.ItemDataRole.UserRole)
            TSHCountryHelper.countryModel.appendRow(noCountry)

            for i, country_code in enumerate(TSHCountryHelper.countries.keys()):
                item = QStandardItem()
                item.setIcon(
                    QIcon(f'./assets/country_flag/{country_code.lower()}.png'))
                countryData = TSHCountryHelper.GetBasicCountryInfo(
                    country_code)
                item.setData(countryData, Qt.ItemDataRole.UserRole)
                item.setData(
                    f'{TSHCountryHelper.countries[country_code]["display_name"]} / {TSHCountryHelper.countries[country_code]["en_name"]} ({country_code})', Qt.ItemDataRole.EditRole)
                TSHCountryHelper.countryModel.appendRow(item)

            # Setup cities - states for reverse search
            for country in countries_json:
                for state in country.get("states"):
                    for c in state["cities"]:
                        if country["iso2"] not in TSHCountryHelper.cities:
                            TSHCountryHelper.cities[country["iso2"]] = {}
                        city_name = TSHCountryHelper.remove_accents_lower(
                            c["name"])
                        if city_name not in TSHCountryHelper.cities[country["iso2"]]:
                            TSHCountryHelper.cities[country["iso2"]
                                                    ][city_name] = state["state_code"]

            TSHCountryHelper.signals.countriesUpdated.emit()

            AdditionalFlags = os.listdir("./user_data/additional_flag")

            AdditionalFlagsFiltered = []
            for flag in AdditionalFlags:
                filename = os.path.basename(flag)
                ext = filename.split(".")[-1]
                #  Remove flags with less than 3 characters
                if len(filename.removesuffix("."+ext)) >= 3:
                    AdditionalFlagsFiltered.append(flag)
            AdditionalFlags = AdditionalFlagsFiltered

            if AdditionalFlags:
                separator = QStandardItem()
                separator.setData("    " + QApplication.translate("app",
                                  "TSH_legacy_00277").upper() + "    ", Qt.ItemDataRole.EditRole)
                separator.setEnabled(False)
                separator.setSelectable(False)
                TSHCountryHelper.countryModel.appendRow(separator)

            for flag in AdditionalFlags:
                item = QStandardItem()
                item.setIcon(QIcon(f"./user_data/additional_flag/{flag}"))
                item.setData({
                    "name": flag[:-4],
                    "display_name": flag[:-4],
                    "en_name": flag[:-4],
                    "code": flag[:-4],
                    "asset": f'./user_data/additional_flag/{flag}'
                }, Qt.ItemDataRole.UserRole)
                item.setData(flag[:-4], Qt.ItemDataRole.EditRole)
                TSHCountryHelper.countryModel.appendRow(item)
        except:
            TSHCountryHelper.countries_json = {}
            logger.error(traceback.format_exc())

    def FindState(countryCode, city):
        # State explicit?
        # Normalize parts of city string
        split = city.replace(" - ", ",").split(",")

        logger.debug(f"Finding State from city string [{city}]")

        for part in split[::-1]:
            part = part.strip()

            state = next(
                (st for st in TSHCountryHelper.countries.get(countryCode, {}).get("states", {}).values(
                ) if TSHCountryHelper.remove_accents_lower(st["code"]) == TSHCountryHelper.remove_accents_lower(part)),
                None
            )
            if state is None:
                state = next(
                    (st for st in TSHCountryHelper.countries.get(countryCode, {}).get("states", {}).values(
                    ) if TSHCountryHelper.remove_accents_lower(st["name"]) == TSHCountryHelper.remove_accents_lower(part)),
                    None
                )
            if state is not None:
                logger.debug(
                    f"State was explicit: [{city}] -> [{part}] = {state}")
                return state["original_code"]

        # No, so get by City
        for part in split[::-1]:
            part = part.strip()

            state = TSHCountryHelper.cities.get(countryCode, {}).get(
                TSHCountryHelper.remove_accents_lower(part), None)

            if state is not None:
                logger.debug(f"Got state from city name: [{city}] -> [{part}] = {state}")
                return state

        return None


TSHCountryHelper.instance = TSHCountryHelper()
