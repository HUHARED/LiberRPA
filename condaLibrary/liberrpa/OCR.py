# FileName: OCR.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


""" The module bases on EasyOCR, calculate by CPU in local machine, so the handle time will increase significantly with image's size. """
from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import DictTextBlock
from liberrpa.Common._BasicConfig import get_liberrpa_folder_path
from liberrpa.Common._TypedValue import DictTextBlock


import os


"""
If it throw the error:
OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll already initialized.
OMP: Hint This means that multiple copies of the OpenMP runtime have been linked into the program. That is dangerous, since it can degrade performance or cause incorrect results. The best thing to do is to ensure that only a single OpenMP runtime is linked into the process, e.g. by avoiding static linking of the OpenMP runtime in any library. As an unsafe, unsupported, undocumented workaround 
you can set the environment variable KMP_DUPLICATE_LIB_OK=TRUE to allow the program to continue to execute, but that may cause crashes or silently produce incorrect results. For more information, please see http://www.intel.com/software/products/support/. 
set this:

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
"""

dictReader = {}  # dict[str, easyocr.Reader]


@Log.trace()
def _initialize() -> None:
    global dictReader
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    from pathlib import Path
    import json5
    import easyocr

    strLiberRPA = get_liberrpa_folder_path()
    strConfigPath = os.path.join(strLiberRPA, R"envs\ocr\ocr.jsonc")
    strConfig = Path(strConfigPath).read_text()
    dictOcrConfig: dict[str, list[str]] = json5.loads(strConfig)  # type: ignore - type is right.

    for strModelName in dictOcrConfig.keys():
        dictReader[strModelName] = easyocr.Reader(
            lang_list=dictOcrConfig[strModelName],
            gpu=False,
            model_storage_directory=os.path.join(strLiberRPA, R"envs\ocr\model"),
            user_network_directory=os.path.join(strLiberRPA, R"envs\ocr\model\CustomModel"),
            detect_network="craft",
            recog_network=strModelName,
            download_enabled=False,
            detector=True,
            recognizer=True,
            verbose=False,
            quantize=True,
            cudnn_benchmark=False,
        )
        Log.debug(f"Create {strModelName} model.")


@Log.trace()
def get_text_with_position(
    image: str,
    modelName: str = "english_default",
    min_size: int = 10,
    low_text: float = 0.4,
    mag_ratio: int = 1,
    add_margin: float = 0.2,
    decoder: str = "greedy",
    beamWidth: int = 5,
    contrast_ths: float = 0.1,
    adjust_contrast: float = 0.5,
    filter_ths: float = 0.003,
    text_threshold: float = 0.7,
    link_threshold: float = 0.4,
    canvas_size: int = 2560,
    slope_ths: float = 0.1,
    ycenter_ths: float = 0.5,
    height_ths: float = 0.5,
    width_ths: float = 0.5,
    y_ths: float = 0.5,
    x_ths: float = 1,
    threshold: float = 0.2,
    bbox_min_score: float = 0.2,
    bbox_min_size: int = 3,
    max_candidates: int = 0,
) -> list[DictTextBlock]:
    """
    Perform OCR on an image and returns text blocks with their positions.
    Note that it bases on EasyOCR, calculate by CPU in local machine, so the handle time will increase significantly with image's size.
    The first run will take some time to initialize.

    min_size, low_text, mag_ratio,add_margin are most useful generally.
    If you don't know the arguments' meaning, refer to [EasyOCR api](https://www.jaided.ai/easyocr/documentation/)

    The default model "english_default" is actually "english_g2" of EasyOCR. You can add your custom model into the path 'LiberRPA/envs/ocr', put the .pth file in 'model', the .yaml and .py file in '/model/CustomModel', then add the information into 'ocr.jsonc'. Restart LiberRPA Local Server, it will load the model automatically.

    Parameters:
        image: Path to the image file.
        modelName: The model used for OCR.
        min_size: Minimum text size (in pixel) to detect. Increase it may help to detect more text.
        low_text: Text low-bound score. Increase it may help to detect more text.
        mag_ratio: Image magnification ratio. Increase it may help to detect more text.
        add_margin: Additional margin to add around text during detection. Increase it may help to detect more characters at the beginning and end of the text block.
        decoder: Options are 'greedy', 'beamsearch' and 'wordbeamsearch'.
        beamWidth: How many beam to keep when decoder = 'beamsearch' or 'wordbeamsearch'
        contrast_ths: Text box with contrast lower than this value will be passed into model 2 times. First is with original image and second with contrast adjusted to 'adjust_contrast' value. The one with more confident level will be returned as a result.
        adjust_contrast: Target contrast level for low contrast text box
        filter_ths: Filter threshold.
        text_threshold: Text confidence threshold.
        link_threshold: Link confidence threshold.
        canvas_size: Maximum image size. Image bigger than this value will be resized down.
        slope_ths: Maximum slope (delta y/delta x) to considered merging. Low value means tiled boxes will not be merged.
        ycenter_ths: Maximum shift in y direction. Boxes with different level should not be merged.
        height_ths: Maximum different in box height. Boxes with very different text size should not be merged.
        width_ths: Maximum horizontal distance to merge boxes.
        y_ths: Maximum verticall distance to merge text boxes. (May not work due to paragraph=False in this function)
        x_ths: Maximum horizontal distance to merge text boxes.(May not work due to paragraph=False in this function)
        threshold: General threshold for detection.
        bbox_min_score: Minimum score for bounding boxes.
        bbox_min_size: Minimum size for bounding boxes.
        max_candidates: Maximum number of candidate detections.

    Returns:
        list[DictTextBlock]: A list of dictionaries containing the detected text and their positions: {'text': <class 'str'>,
    'top_left_x': <class 'int'>,
    'top_left_y': <class 'int'>,
    'top_right_x': <class 'int'>,
    'top_right_y': <class 'int'>,
    'bottom_left_x': <class 'int'>,
    'bottom_left_y': <class 'int'>,
    'bottom_right_x': <class 'int'>,
    'bottom_right_y': <class 'int'>}
    """

    global dictReader

    if len(dictReader.keys()) == 0:
        _initialize()

    listResult: list[tuple[list[list[int]], str, float]] = dictReader[modelName].readtext(
        image=image,
        decoder=decoder,
        beamWidth=beamWidth,
        batch_size=1,
        workers=0,
        allowlist=None,
        blocklist=None,
        detail=1,
        rotation_info=None,
        paragraph=False,
        min_size=min_size,
        contrast_ths=contrast_ths,
        adjust_contrast=adjust_contrast,
        filter_ths=filter_ths,
        text_threshold=text_threshold,
        low_text=low_text,
        link_threshold=link_threshold,
        canvas_size=canvas_size,
        mag_ratio=mag_ratio,
        slope_ths=slope_ths,
        ycenter_ths=ycenter_ths,
        height_ths=height_ths,
        width_ths=width_ths,
        y_ths=y_ths,
        x_ths=x_ths,
        add_margin=add_margin,
        threshold=threshold,
        bbox_min_score=bbox_min_score,
        bbox_min_size=bbox_min_size,
        max_candidates=max_candidates,
        output_format="standard",
    )  # type: ignore
    print(listResult)

    listReturn: list[DictTextBlock] = []
    if len(listResult) != 0:
        for tupleTemp in listResult:
            dictTemp: DictTextBlock = {
                "text": tupleTemp[1],
                "top_left_x": int(tupleTemp[0][0][0]),
                "top_left_y": int(tupleTemp[0][0][1]),
                "top_right_x": int(tupleTemp[0][1][0]),
                "top_right_y": int(tupleTemp[0][1][1]),
                "bottom_left_x": int(tupleTemp[0][2][0]),
                "bottom_left_y": int(tupleTemp[0][2][1]),
                "bottom_right_x": int(tupleTemp[0][3][0]),
                "bottom_right_y": int(tupleTemp[0][3][1]),
            }
            listReturn.append(dictTemp)

    return listReturn


@Log.trace()
def get_text(
    image: str,
    modelName: str = "english_default",
    min_size: int = 10,
    low_text: float = 0.4,
    mag_ratio: int = 1,
    add_margin: float = 0.2,
    decoder: str = "greedy",
    beamWidth: int = 5,
    contrast_ths: float = 0.1,
    adjust_contrast: float = 0.5,
    filter_ths: float = 0.003,
    text_threshold: float = 0.7,
    link_threshold: float = 0.4,
    canvas_size: int = 2560,
    slope_ths: float = 0.1,
    ycenter_ths: float = 0.5,
    height_ths: float = 0.5,
    width_ths: float = 0.5,
    y_ths: float = 0.5,
    x_ths: float = 1,
    threshold: float = 0.2,
    bbox_min_score: float = 0.2,
    bbox_min_size: int = 3,
    max_candidates: int = 0,
) -> str:
    """
    Perform OCR on an image and returns the extracted text as a single string.
    Note that it bases on EasyOCR, calculate by CPU in local machine, so the handle time will increase significantly with image's size.
    The first run will take some time to initialize.

    min_size, low_text, mag_ratio,add_margin are most useful generally.
    If you don't know the arguments' meaning, refer to [EasyOCR api](https://www.jaided.ai/easyocr/documentation/)

    Parameters:
        image: Path to the image file.
        modelName: The model used for OCR.
        min_size: Minimum text size (in pixel) to detect. Increase it may help to detect more text.
        low_text: Text low-bound score. Increase it may help to detect more text.
        mag_ratio: Image magnification ratio. Increase it may help to detect more text.
        add_margin: Additional margin to add around text during detection. Increase it may help to detect more characters at the beginning and end of the text block.
        decoder: Options are 'greedy', 'beamsearch' and 'wordbeamsearch'.
        beamWidth: How many beam to keep when decoder = 'beamsearch' or 'wordbeamsearch'
        contrast_ths: Text box with contrast lower than this value will be passed into model 2 times. First is with original image and second with contrast adjusted to 'adjust_contrast' value. The one with more confident level will be returned as a result.
        adjust_contrast: Target contrast level for low contrast text box
        filter_ths: Filter threshold.
        text_threshold: Text confidence threshold.
        link_threshold: Link confidence threshold.
        canvas_size: Maximum image size. Image bigger than this value will be resized down.
        slope_ths: Maximum slope (delta y/delta x) to considered merging. Low value means tiled boxes will not be merged.
        ycenter_ths: Maximum shift in y direction. Boxes with different level should not be merged.
        height_ths: Maximum different in box height. Boxes with very different text size should not be merged.
        width_ths: Maximum horizontal distance to merge boxes.
        y_ths: Maximum verticall distance to merge text boxes.
        x_ths: Maximum horizontal distance to merge text boxes.
        threshold: General threshold for detection.
        bbox_min_score: Minimum score for bounding boxes.
        bbox_min_size: Minimum size for bounding boxes.
        max_candidates: Maximum number of candidate detections.

    Returns:
        str: The extracted text as a single string.
    """

    global dictReader

    if len(dictReader.keys()) == 0:
        _initialize()

    listResult: list[list[list[list[int]] | str]] = dictReader[modelName].readtext(
        image=image,
        decoder=decoder,
        beamWidth=beamWidth,
        batch_size=1,
        workers=0,
        allowlist=None,
        blocklist=None,
        detail=1,
        rotation_info=None,
        paragraph=True,
        min_size=min_size,
        contrast_ths=contrast_ths,
        adjust_contrast=adjust_contrast,
        filter_ths=filter_ths,
        text_threshold=text_threshold,
        low_text=low_text,
        link_threshold=link_threshold,
        canvas_size=canvas_size,
        mag_ratio=mag_ratio,
        slope_ths=slope_ths,
        ycenter_ths=ycenter_ths,
        height_ths=height_ths,
        width_ths=width_ths,
        y_ths=y_ths,
        x_ths=x_ths,
        add_margin=add_margin,
        threshold=threshold,
        bbox_min_score=bbox_min_score,
        bbox_min_size=bbox_min_size,
        max_candidates=max_candidates,
        output_format="standard",
    )  # type: ignore
    print(listResult)

    if len(listResult) != 0:
        """strTemp = ""
        for item in listResult:
            strTemp += str(item[1])"""
        return " ".join([str(item[1]) for item in listResult])
    else:
        return ""


if __name__ == "__main__":
    print(
        get_text_with_position(
            modelName="english_default",
            image="./test.png",
            mag_ratio=4,
        )
    )
    print(
        get_text_with_position(
            modelName="english_default",
            image="./test.png",
            mag_ratio=4,
        )
    )
