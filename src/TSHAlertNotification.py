import unicodedata
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import requests
import os
import traceback
import json
import time
from loguru import logger


class TSHAlertNotificationSignals(QObject):
    alerts = Signal(object)


class TSHAlertNotification(QObject):
    instance: "TSHAlertNotification" = None

    def __init__(self) -> None:
        super().__init__()
        self.signals = TSHAlertNotificationSignals()
        self.signals.alerts.connect(self.ShowAlerts)

    def UiMounted(self):
        class AlertThread(QThread):
            def run(self):
                alerts = None

                try:
                    response = requests.get(
                        "https://raw.githubusercontent.com/joaorb64/TournamentStreamHelper/main/assets/alerts.json")
                    alerts = json.loads(response.text)
                except Exception as e:
                    logger.error(traceback.format_exc())

                try:
                    alerts_red = json.load(
                        open('./user_data/alerts_red.json', encoding='utf-8'))
                except Exception as e:
                    logger.error(traceback.format_exc())

                filtered = {}

                if alerts is not None and alerts_red is not None:
                    for alertId, alert in alerts.items():
                        if alertId not in alerts_red:
                            if alert.get("dateStart", None):
                                if time.time() > alert.get("dateStart"):
                                    continue
                            if alert.get("dateEnd", None):
                                if time.time() > alert.get("dateEnd"):
                                    continue

                            filtered[alertId] = alert

                self.parent().signals.alerts.emit(filtered)

        thread = AlertThread(self)
        thread.start()

    def ShowAlerts(self, alerts):
        i = 1

        for alertId, alert in alerts.items():
            message = QDialog()
            message.setWindowModality(
                Qt.WindowModality.ApplicationModal)
            vbox = QVBoxLayout()
            message.setLayout(vbox)
            message.setWindowTitle(
                QApplication.translate("app", "TSH_legacy_00237_{0}_{1}").format(i, len(alerts.keys())))
            message.layout().addWidget(QLabel(alert.get("alert")))

            hbox = QHBoxLayout()
            vbox.addLayout(hbox)

            btOk = QPushButton("OK")
            hbox.addWidget(btOk)
            btRemindLater = QPushButton(QApplication.translate("app", "TSH_legacy_00238"))
            hbox.addWidget(btRemindLater)

            message.setMinimumWidth(500)
            message.setMinimumHeight(200)

            btOk.clicked.connect(
                lambda: self.MarkNotificationRed(alertId))
            btOk.clicked.connect(
                lambda: message.close())
            btRemindLater.clicked.connect(
                lambda: message.close())

            message.exec()

            i += 1

    def MarkNotificationRed(self, id):
        alerts_red = None

        try:
            alerts_red = json.load(
                open('./user_data/alerts_red.json', encoding='utf-8'))
        except Exception as e:
            logger.error(traceback.format_exc())

        if alerts_red is not None:
            alerts_red.append(id)
            with open("./user_data/alerts_red.json", 'w') as outfile:
                json.dump(alerts_red, outfile)


if not os.path.exists("./user_data/alerts_red.json"):
    with open("./user_data/alerts_red.json", 'w') as outfile:
        outfile.write("[]")

TSHAlertNotification.instance = TSHAlertNotification()
