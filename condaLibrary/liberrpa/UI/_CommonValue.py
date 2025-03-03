# FileName: _CommonValue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"



try:
    from liberrpa.FlowControl.ProjectFlowInit import dictFlowFile

    if dictFlowFile["highlightUi"]:
        global boolHighlightUi
        boolHighlightUi = True
    else:
        boolHighlightUi = False
except Exception as e:
    boolHighlightUi = False
