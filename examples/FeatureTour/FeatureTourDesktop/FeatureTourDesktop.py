# FileName: FeatureTourDesktop.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import sys

from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FeatureTourDesktop(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("LiberRPA Feature Tour Desktop")
        self.setFixedSize(560, 380)

        self.requestIdInput = QLineEdit()
        self.requestIdInput.setObjectName("requestIdInput")
        self.requestIdInput.setAccessibleName("Request ID")

        self.recordsClerkInput = QLineEdit()
        self.recordsClerkInput.setObjectName("recordsClerkInput")
        self.recordsClerkInput.setAccessibleName("Records Clerk")

        self.ministryInput = QComboBox()
        self.ministryInput.setObjectName("ministryInput")
        self.ministryInput.setAccessibleName("Ministry")
        self.ministryInput.addItems([
            "Ministry of Truth",
            "Ministry of Peace",
            "Ministry of Love",
            "Ministry of Plenty",
        ])

        self.subjectInput = QLineEdit()
        self.subjectInput.setObjectName("subjectInput")
        self.subjectInput.setAccessibleName("Subject")

        self.priorityInput = QComboBox()
        self.priorityInput.setObjectName("priorityInput")
        self.priorityInput.setAccessibleName("Priority")
        self.priorityInput.addItems([
            "Standard",
            "Urgent",
        ])

        self.approvedInput = QCheckBox("Approved for Rectification")
        self.approvedInput.setObjectName("approvedInput")
        self.approvedInput.setAccessibleName("Approved for Rectification")
        self.approvedInput.setChecked(False)

        self.submitButton = QPushButton("Submit")
        self.submitButton.setObjectName("submitButton")
        self.submitButton.setAccessibleName("Submit")
        self.submitButton.clicked.connect(self._submit)

        self.resetButton = QPushButton("Reset")
        self.resetButton.setObjectName("resetButton")
        self.resetButton.setAccessibleName("Reset")
        self.resetButton.clicked.connect(self._reset)

        self.statusText = QLabel("Ready")
        self.statusText.setObjectName("statusText")

        formLayout = QFormLayout()
        formLayout.addRow("Request ID:", self.requestIdInput)
        formLayout.addRow("Records Clerk:", self.recordsClerkInput)
        formLayout.addRow("Ministry:", self.ministryInput)
        formLayout.addRow("Subject:", self.subjectInput)
        formLayout.addRow("Priority:", self.priorityInput)
        formLayout.addRow("", self.approvedInput)

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.submitButton)
        buttonLayout.addWidget(self.resetButton)

        statusLayout = QHBoxLayout()
        statusLayout.addWidget(QLabel("Status:"))
        statusLayout.addWidget(self.statusText)
        statusLayout.addStretch()

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(QLabel("Ministry of Truth"))
        mainLayout.addWidget(QLabel("Records Rectification Desk"))
        mainLayout.addSpacing(14)
        mainLayout.addLayout(formLayout)
        mainLayout.addSpacing(12)
        mainLayout.addLayout(buttonLayout)
        mainLayout.addSpacing(18)
        mainLayout.addLayout(statusLayout)
        mainLayout.addStretch()

        self.setLayout(mainLayout)

    def _submit(self) -> None:
        strRequestId = self.requestIdInput.text().strip()
        strRecordsClerk = self.recordsClerkInput.text().strip()
        strSubject = self.subjectInput.text().strip()

        if not strRequestId or not strRecordsClerk or not strSubject:
            self.statusText.setText("Validation failed")
            return

        strMinistry = self.ministryInput.currentText()
        strPriority = self.priorityInput.currentText()
        strApproval = "Approved" if self.approvedInput.isChecked() else "Review Required"

        self.statusText.setText(
            f"Submitted - {strRequestId} / {strRecordsClerk} / {strMinistry} / {strPriority} / {strApproval}"
        )

    def _reset(self) -> None:
        self.requestIdInput.clear()
        self.recordsClerkInput.clear()
        self.ministryInput.setCurrentIndex(0)
        self.subjectInput.clear()
        self.priorityInput.setCurrentIndex(0)
        self.approvedInput.setChecked(False)
        self.statusText.setText("Ready")


def main() -> None:
    appObj = QApplication(sys.argv)

    windowObj = FeatureTourDesktop()
    windowObj.show()

    sys.exit(appObj.exec_())


if __name__ == "__main__":
    main()
