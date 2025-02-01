import sys
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from .SettingsWidget import SettingsWidget
from ..TSHHotkeys import TSHHotkeys


class TSHSettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def UiMounted(self):
        self.setWindowTitle(QApplication.translate("Settings", "TSH_legacy_00129"))

        # Create a list widget for the selection
        self.selection_list = QListWidget()
        self.selection_list.currentRowChanged.connect(
            self.on_selection_changed)

        # Create a stacked widget for the settings widgets
        self.settings_stack = QStackedWidget()

        # Create a scroll area for the settings stack
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.settings_stack)

        # Create a splitter for the selection and settings
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.selection_list)
        splitter.addWidget(scroll_area)

        # Set the layout for the dialog
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Add general settings
        generalSettings = []

        generalSettings.append((
            QApplication.translate(
                "settings.general", "TSH_legacy_00301"),
            "profanity_filter",
            "checkbox",
            True
        ))

        generalSettings.append((
            QApplication.translate(
                "settings.control_score_from_stage_strike", "TSH_legacy_00297"),
            "control_score_from_stage_strike",
            "checkbox",
            True
        ))

        generalSettings.append((
            QApplication.translate(
                "settings.disable_autoupdate", "TSH_legacy_00298"),
            "disable_autoupdate",
            "checkbox",
            False
        ))

        generalSettings.append((
            QApplication.translate(
                "settings.disable_export", "TSH_legacy_00299"),
            "disable_export",
            "checkbox",
            False
        ))
        
        generalSettings.append((
            QApplication.translate(
                "settings.disable_overwrite", "TSH_legacy_00300"),
            "disable_overwrite",
            "checkbox",
            False
        ))

        self.add_setting_widget(QApplication.translate(
            "settings", "TSH_legacy_00287"), SettingsWidget("general", generalSettings))

        # Add hotkey settings
        hotkeySettings = []

        hotkeySettings.append((
            QApplication.translate("settings.hotkeys", "TSH_legacy_00317"),
            "hotkeys_enabled",
            "checkbox",
            True
        ))

        key_names = {
            "load_set": QApplication.translate("settings.hotkeys", "TSH_legacy_00310"),
            "team1_score_up": QApplication.translate("settings.hotkeys", "TSH_legacy_00311"),
            "team1_score_down": QApplication.translate("settings.hotkeys", "TSH_legacy_00312"),
            "team2_score_up": QApplication.translate("settings.hotkeys", "TSH_legacy_00313"),
            "team2_score_down": QApplication.translate("settings.hotkeys", "TSH_legacy_00314"),
            "reset_scores": QApplication.translate("settings.hotkeys", "TSH_legacy_00315"),
            "swap_teams": QApplication.translate("settings.hotkeys", "TSH_legacy_00316"),
        }

        for i, (setting, value) in enumerate(TSHHotkeys.instance.keys.items()):
            hotkeySettings.append((
                key_names[setting],
                setting,
                "hotkey",
                value,
                TSHHotkeys.instance.ReloadHotkeys
            ))

        self.add_setting_widget(QApplication.translate(
            "settings", "TSH_legacy_00288"), SettingsWidget("hotkeys", hotkeySettings))
            
        # Add Bluesky settings
        bskySettings = []
        bskySettings.append((
            QApplication.translate(
                "settings.bsky", "TSH_legacy_00291"),
            "host",
            "textbox",
            "https://bsky.social"
        ))
        bskySettings.append((
            QApplication.translate(
                "settings.bsky", "TSH_legacy_00292"),
            "username",
            "textbox",
            ""
        ))
        bskySettings.append((
            QApplication.translate(
                "settings.bsky", "TSH_legacy_00293"),
            "app_password",
            "password",
            "",
            None,
            QApplication.translate(
                "settings.bsky", "TSH_legacy_00294") + "\n" +
                QApplication.translate(
                "settings.bsky", "TSH_legacy_00295") + "\n\n" +
                QApplication.translate(
                "settings.bsky", "TSH_legacy_00296").upper()
        ))
        
        self.add_setting_widget(QApplication.translate(
            "settings", "TSH_legacy_00289"), SettingsWidget("bsky_account", bskySettings))

        self.resize(1000, 500)
        QApplication.processEvents()
        splitter.setSizes([200, self.width()-200])

    def on_selection_changed(self, index):
        # Get the selected item and its associated widget
        item = self.selection_list.item(index)
        widget = item.data(Qt.UserRole)

        # Set the current widget in the stack
        self.settings_stack.setCurrentWidget(widget)

    def add_setting_widget(self, name, widget):
        # Create a list widget item for the selection
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, widget)
        self.selection_list.addItem(item)

        # Add the setting widget to the stack
        self.settings_stack.addWidget(widget)
