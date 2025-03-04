# Python Library

The conda library serves several purposes:

* Execute [Specific operations](./liberrpa) for RPA projects—only this section will be published to conda-forgeunder the name "liberrpa".
* [Initialize](./exe/InitLiberRPA) LiberRPA on computers that do not have it installed.
* Communicate with [the Chrome extension](./exe/ChromeGetLocalServerPort) to pass WebSocket initialization information.
* Create [a local Flask server](./exe/LiberRPALocalServer) to accomplish tasks that are difficult to achieve in a standalone Python project.

# Global Objects

LiberRPA creates a global object to store project-related information.

You can view its implementation in [ProjectFlowInit.py](https://github.com/HUHARED/LiberRPA/condaLibrary/FlowControl/ProjectFlowInit.py).

```python
class ProjectArguments:
    """
    A class to handle project arguments, initialization from the 'project.flow' file,
    and track elapsed time since object creation.

    Attributes:
        projectPath (str): The path of the current working directory.
        projectName (str): The name of the project (based on the directory name).
        errorObj (Exception | None): An exception object, or None if no errors occurred.
        customArgs (dict[str, Any]): A dictionary to store the custom project arguments.
        elapsedTime (float): The time elapsed since the program started (in seconds).
    """
...
PrjArgs = ProjectArguments()
CustomArgs: dict[str, Any] = PrjArgs.customArgs
```

In your RPA project, you can use the two global objects—`PrjArgs` and `CustomArgs`—as shown in the example below:

```python
print(PrjArgs)
print(PrjArgs.elapsedTime)
print(PrjArgs.customArgs)
print(PrjArgs.errorObj)
print(PrjArgs.projectPath)
print(CustomArgs)
```

These global objects provide a convenient way to access and manage key project data throughout your LiberRPA project.

# API

This section contains the code snippets you can use after installing the **"liberrpa"** library from conda-forge.

Use `Ctrl+F` to search them.

*(Automatically generated—if you notice any errors, please contact me.)*

- [Python Library](#python-library)
- [Global Objects](#global-objects)
- [API](#api)
  - [Basic](#basic)
    - [delay](#delay)
    - [new python file](#new-python-file)
    - [def a function](#def-a-function)
    - [if __main__](#if-main)
    - [File Header](#file-header)
    - [# type: ignore](#-type-ignore)
  - [LogicControl](#logiccontrol)
    - [if](#if)
    - [else](#else)
    - [elif](#elif)
    - [match case](#match-case)
    - [case](#case)
    - [for-index, item](#for-index-item)
    - [for-item](#for-item)
    - [for-counting cycle](#for-counting-cycle)
    - [while](#while)
    - [continue](#continue)
    - [break](#break)
    - [try catch](#try-catch)
    - [retry](#retry)
    - [raise an exception](#raise-an-exception)
    - [return](#return)
  - [Log](#log)
    - [verbose](#verbose)
    - [verbose\_pretty](#verbose_pretty)
    - [debug](#debug)
    - [debug\_pretty](#debug_pretty)
    - [info](#info)
    - [info\_pretty](#info_pretty)
    - [warning](#warning)
    - [warning\_pretty](#warning_pretty)
    - [error](#error)
    - [error\_pretty](#error_pretty)
    - [critical](#critical)
    - [critical\_pretty](#critical_pretty)
    - [exception\_info](#exception_info)
    - [set\_level](#set_level)
    - [add\_custom\_log\_part](#add_custom_log_part)
    - [remove\_custom\_log\_part](#remove_custom_log_part)
    - [trace](#trace)
  - [Mouse](#mouse)
    - [get\_mouse\_position](#get_mouse_position)
    - [click\_element](#click_element)
    - [move\_to\_element](#move_to_element)
    - [click](#click)
    - [move\_cursor](#move_cursor)
    - [scroll\_wheel](#scroll_wheel)
  - [Keyboard](#keyboard)
    - [write\_text](#write_text)
    - [write\_text\_into\_element](#write_text_into_element)
    - [type\_key\_in\_element](#type_key_in_element)
    - [type\_key](#type_key)
  - [Window](#window)
    - [close\_window](#close_window)
    - [check\_window\_exists](#check_window_exists)
    - [get\_active\_window](#get_active_window)
    - [activate\_element\_window](#activate_element_window)
    - [set\_window\_state](#set_window_state)
    - [get\_window\_position\_and\_size](#get_window_position_and_size)
    - [set\_window\_position](#set_window_position)
    - [set\_window\_size](#set_window_size)
    - [get\_window\_pid](#get_window_pid)
    - [get\_window\_file\_path](#get_window_file_path)
  - [UiInterface](#uiinterface)
    - [highlight](#highlight)
    - [screenshot](#screenshot)
    - [get\_image\_position](#get_image_position)
    - [check\_exists](#check_exists)
    - [wait\_appear](#wait_appear)
    - [wait\_disappear](#wait_disappear)
    - [get\_parent](#get_parent)
    - [get\_children](#get_children)
    - [get\_attr\_dictionary](#get_attr_dictionary)
    - [get\_text](#get_text)
    - [set\_text](#set_text)
    - [get\_check\_state](#get_check_state)
    - [set\_check\_state](#set_check_state)
    - [get\_selection](#get_selection)
    - [set\_selection](#set_selection)
  - [Browser](#browser)
    - [open\_browser](#open_browser)
    - [bind\_browser](#bind_browser)
    - [get\_state](#get_state)
    - [go\_backward](#go_backward)
    - [go\_forward](#go_forward)
    - [refresh](#refresh)
    - [wait\_load\_completed](#wait_load_completed)
    - [navigate](#navigate)
    - [open\_new\_tab](#open_new_tab)
    - [open\_new\_window](#open_new_window)
    - [switch\_tab](#switch_tab)
    - [close\_current\_tab](#close_current_tab)
    - [get\_download\_list](#get_download_list)
    - [get\_source\_code](#get_source_code)
    - [get\_all\_text](#get_all_text)
    - [get\_url](#get_url)
    - [get\_title](#get_title)
    - [get\_cookies](#get_cookies)
    - [set\_cookies](#set_cookies)
    - [get\_scroll\_position](#get_scroll_position)
    - [set\_scroll\_position](#set_scroll_position)
    - [execute\_js\_code](#execute_js_code)
  - [Excel](#excel)
    - [open\_Excel\_file](#open_excel_file)
    - [bind\_Excel\_file](#bind_excel_file)
    - [save](#save)
    - [save\_as\_and\_reopen](#save_as_and_reopen)
    - [close](#close)
    - [activate\_window](#activate_window)
    - [get\_last\_row](#get_last_row)
    - [get\_last\_column](#get_last_column)
    - [convert\_col\_num\_to\_str](#convert_col_num_to_str)
    - [convert\_col\_str\_to\_num](#convert_col_str_to_num)
    - [read\_cell](#read_cell)
    - [read\_row](#read_row)
    - [read\_column](#read_column)
    - [read\_range\_list](#read_range_list)
    - [read\_range\_df](#read_range_df)
    - [write\_cell](#write_cell)
    - [write\_row](#write_row)
    - [write\_column](#write_column)
    - [write\_range](#write_range)
    - [insert\_row](#insert_row)
    - [insert\_column](#insert_column)
    - [delete\_row](#delete_row)
    - [delete\_column](#delete_column)
    - [select\_range](#select_range)
    - [get\_selected\_cells](#get_selected_cells)
    - [get\_selected\_range](#get_selected_range)
    - [clear\_range](#clear_range)
    - [activate\_sheet](#activate_sheet)
    - [add\_sheet](#add_sheet)
    - [rename\_sheet](#rename_sheet)
    - [copy\_sheet](#copy_sheet)
    - [delete\_sheet](#delete_sheet)
    - [get\_activate\_sheet](#get_activate_sheet)
    - [get\_sheet\_list](#get_sheet_list)
    - [run\_macro](#run_macro)
  - [Outlook](#outlook)
    - [send\_email](#send_email)
    - [get\_folder\_list](#get_folder_list)
    - [get\_email\_list](#get_email_list)
    - [move\_email](#move_email)
    - [reply\_to\_email](#reply_to_email)
    - [delete\_email](#delete_email)
    - [download\_attachments](#download_attachments)
  - [Application](#application)
    - [run\_application](#run_application)
    - [open\_url](#open_url)
    - [check\_process\_running](#check_process_running)
    - [stop\_process](#stop_process)
  - [Database](#database)
    - [build database connection](#build-database-connection)
    - [fetch\_one](#fetch_one)
    - [fetch\_all](#fetch_all)
    - [execute](#execute)
  - [Data](#data)
    - [sanitize\_filename](#sanitize_filename)
    - [get\_length](#get_length)
    - [to\_integer](#to_integer)
    - [to\_float](#to_float)
    - [to\_decimal](#to_decimal)
    - [to\_boolean](#to_boolean)
    - [clone](#clone)
    - [get\_type](#get_type)
    - [get\_uuid](#get_uuid)
    - [get\_random\_integer](#get_random_integer)
    - [get\_random\_float](#get_random_float)
    - [json\_dumps](#json_dumps)
    - [json\_loads](#json_loads)
    - [join\_to\_str](#join_to_str)
  - [Str](#str)
    - [replace](#replace)
    - [split](#split)
    - [split\_lines](#split_lines)
    - [fill](#fill)
    - [count](#count)
    - [find\_from\_start](#find_from_start)
    - [find\_from\_end](#find_from_end)
    - [case\_to\_lower](#case_to_lower)
    - [case\_to\_upper](#case_to_upper)
    - [check\_case\_lower](#check_case_lower)
    - [check\_case\_upper](#check_case_upper)
    - [case\_swap](#case_swap)
    - [strip](#strip)
    - [remove\_prefix](#remove_prefix)
    - [remove\_suffix](#remove_suffix)
    - [check\_start](#check_start)
    - [check\_end](#check_end)
    - [is\_alpha\_and\_numeric](#is_alpha_and_numeric)
    - [is\_alpha](#is_alpha)
    - [is\_numeric](#is_numeric)
    - [is\_ascii](#is_ascii)
    - [is\_digit](#is_digit)
    - [is\_decimal](#is_decimal)
  - [List](#list)
    - [insert](#insert)
    - [append](#append)
    - [pop](#pop)
    - [remove](#remove)
    - [clear](#clear)
    - [slice](#slice)
    - [extend](#extend)
    - [count](#count-1)
    - [find](#find)
    - [reverse](#reverse)
    - [sort](#sort)
  - [Dict](#dict)
    - [clear](#clear-1)
    - [get](#get)
    - [pop](#pop-1)
    - [pop\_item](#pop_item)
    - [get\_key\_list](#get_key_list)
    - [get\_value\_list](#get_value_list)
    - [extend](#extend-1)
  - [Regex](#regex)
    - [find\_one](#find_one)
    - [find\_all](#find_all)
    - [match\_start](#match_start)
    - [match\_full](#match_full)
    - [split](#split-1)
    - [replace](#replace-1)
  - [Math](#math)
    - [round](#round)
    - [check\_float\_equal](#check_float_equal)
    - [absolute](#absolute)
    - [get\_int\_and\_fraction](#get_int_and_fraction)
  - [Time](#time)
    - [get\_unix\_time](#get_unix_time)
    - [get\_datetime\_now](#get_datetime_now)
    - [build\_datetime](#build_datetime)
    - [str\_to\_datetime](#str_to_datetime)
    - [datetime\_to\_str](#datetime_to_str)
    - [get\_datetime\_attr](#get_datetime_attr)
    - [add\_datetime](#add_datetime)
  - [File](#file)
    - [create\_folder](#create_folder)
    - [read\_file\_content](#read_file_content)
    - [write\_file](#write_file)
    - [append\_write\_file](#append_write_file)
    - [wait\_file\_download](#wait_file_download)
    - [get\_file\_fullname](#get_file_fullname)
    - [get\_file\_basename](#get_file_basename)
    - [get\_file\_suffix](#get_file_suffix)
    - [check\_file\_exists](#check_file_exists)
    - [check\_folder\_exists](#check_folder_exists)
    - [get\_parent\_folder\_path](#get_parent_folder_path)
    - [get\_file\_size](#get_file_size)
    - [get\_folder\_size](#get_folder_size)
    - [copy\_file](#copy_file)
    - [copy\_folder](#copy_folder)
    - [move\_file\_or\_folder](#move_file_or_folder)
    - [remove\_file](#remove_file)
    - [remove\_folder](#remove_folder)
    - [get\_file\_or\_folder\_list](#get_file_or_folder_list)
    - [search\_file\_or\_folder](#search_file_or_folder)
    - [zip\_create](#zip_create)
    - [zip\_extract](#zip_extract)
    - [csv\_read](#csv_read)
    - [csv\_write](#csv_write)
    - [ini\_read\_value](#ini_read_value)
    - [ini\_write\_value](#ini_write_value)
    - [ini\_get\_all\_sections](#ini_get_all_sections)
    - [ini\_get\_all\_options](#ini_get_all_options)
    - [ini\_delete\_section](#ini_delete_section)
    - [ini\_delete\_option](#ini_delete_option)
    - [pdf\_get\_page\_count](#pdf_get_page_count)
    - [pdf\_save\_pages\_as\_images](#pdf_save_pages_as_images)
    - [pdf\_extract\_images\_from\_pages](#pdf_extract_images_from_pages)
    - [pdf\_extract\_text\_from\_pages](#pdf_extract_text_from_pages)
    - [pdf\_extract\_all\_images](#pdf_extract_all_images)
    - [pdf\_extract\_all\_text](#pdf_extract_all_text)
    - [pdf\_merge](#pdf_merge)
  - [OCR](#ocr)
    - [get\_text\_with\_position](#get_text_with_position)
    - [get\_text](#get_text-1)
  - [Web](#web)
    - [set\_cookies](#set_cookies-1)
    - [set\_headers](#set_headers)
    - [get](#get-1)
    - [post](#post)
    - [download\_file](#download_file)
    - [upload\_file](#upload_file)
  - [Mail](#mail)
    - [send\_by\_SMTP](#send_by_smtp)
    - [IMAP\_login](#imap_login)
    - [get\_folder\_list](#get_folder_list-1)
    - [get\_email\_list](#get_email_list-1)
    - [search\_email](#search_email)
    - [move\_email](#move_email-1)
    - [download\_attachments](#download_attachments-1)
  - [FTP](#ftp)
    - [build FTP connection](#build-ftp-connection)
    - [create\_folder](#create_folder-1)
    - [get\_folder\_list](#get_folder_list-2)
    - [get\_file\_list](#get_file_list)
    - [check\_folder\_exists](#check_folder_exists-1)
    - [check\_file\_exists](#check_file_exists-1)
    - [download\_file](#download_file-1)
    - [download\_folder](#download_folder)
    - [upload\_file](#upload_file-1)
    - [upload\_folder](#upload_folder)
    - [delete\_file](#delete_file)
    - [delete\_folder](#delete_folder)
  - [Clipboard](#clipboard)
    - [get\_text](#get_text-2)
    - [set\_text](#set_text-1)
    - [save\_image](#save_image)
    - [set\_image](#set_image)
  - [System](#system)
    - [play\_sound](#play_sound)
    - [get\_environment\_variable](#get_environment_variable)
    - [set\_environment\_variable\_temporarily](#set_environment_variable_temporarily)
    - [get\_user\_home\_folder\_path](#get_user_home_folder_path)
    - [get\_user\_temp\_folder\_path](#get_user_temp_folder_path)
    - [get\_windows\_product\_id](#get_windows_product_id)
    - [exit](#exit)
  - [Credential](#credential)
    - [get\_windows\_credential](#get_windows_credential)
    - [write\_windows\_credential](#write_windows_credential)
    - [delete\_windows\_credential](#delete_windows_credential)
  - [ScreenPrint](#screenprint)
    - [create\_area](#create_area)
    - [display\_text](#display_text)
    - [clean\_text](#clean_text)
    - [close\_area](#close_area)
  - [Dialog](#dialog)
    - [show\_notification](#show_notification)
    - [open\_file](#open_file)
    - [open\_files](#open_files)
    - [save\_as](#save_as)
    - [show\_text\_input\_box](#show_text_input_box)
    - [show\_message\_box](#show_message_box)
## Basic

### delay

Delay some time, in milliseconds.

### new python file

The default content for a new Python file.
If you click it in LIberRPA Snippets Tree, the modules in Utils and Selector can be imported automatically.

### def a function

Define a new function.

### if __main__

The logic to run when execute the file.

### File Header

Note the file's name in comment.

### # type: ignore

Ignore the line's Pylance complain. It will be inserted into the current line's end once you clicked it.

## LogicControl

### if

No need for description.

### else

No need for description.

### elif

No need for description.

### match case

No need for description.

### case

No need for description.

### for-index, item

For-loop with enumerate and a starting index.

### for-item

Simple for loop.

### for-counting cycle

Simple for loop using range.

### while

Simple while loop.

### continue

Continue to the next cycle.

### break

End the loop.

### try catch

No need for description.

### retry

Retry until the try scope completed, or raise the error after the last try.

### raise an exception

No need for description.

### return

No need for description.

## Log

### verbose

Write a log entry at the 'VERBOSE' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### verbose_pretty

Write a log entry at the 'VERBOSE' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### debug

Write a log entry at the 'DEBUG' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### debug_pretty

Write a log entry at the 'DEBUG' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### info

Write a log entry at the 'INFO' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### info_pretty

Write a log entry at the 'INFO' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### warning

Write a log entry at the 'WARNING' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### warning_pretty

Write a log entry at the 'WARNING' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### error

Write a log entry at the 'ERROR' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### error_pretty

Write a log entry at the 'ERROR' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### critical

Write a log entry at the 'CRITICAL' level, only if the current log level allows it.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### critical_pretty

Write a log entry at the 'CRITICAL' level, only if the current log level allows it.

If the message is a value of dict,list or tuple, it will be formatted with indent(4 space) in human_read log.

Parameters:

```
message: The message to log, which can be any type that can be converted to a string.
stackLevel: Adjusts the stack level to get the correct file name, line number, and function name for the log entry.
```

### exception_info

Record the Exception object's 'type', 'message', 'fileName' and 'lineNumber' in a dict format and "ERROR" log level, only if the current log level allows it.

Parameters:

```
exObj: The Exception object to record.
```

### set_level

Set the minimum log level for the logger.

Parameters:

```
level: The minimum level to set. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
loggerType: Which logger to set the level for. Must be one of ['both', 'human', 'machine'].
```

### add_custom_log_part

Adds a new part to the log entry format.

If the name already exists, the text will be updated.

The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

Parameters:

```
name: The new part's name to be added. This will be a new key in the machine_read log entry, but it won't appear in human_read log.
text: The text of the new log part, which will be displayed in human_read log.
```

### remove_custom_log_part

Remove a custom log part by name.

If the name is not found, no action is taken.

The name cannot be one of the reserved keywords(["timestamp", "level", "message", "userName", "machineName", "processName", "fileName", "lineNo", "projectName", "logId"]) due to they are used in machine_read log.

Parameters:

```
name: The name of the custom log part to remove from both the machine_read and human_read logs.
```

### trace

This decorator logs the start and end of a function at a specified log level, default is 'DEBUG'

Parameters:

```
level: The level to record log. Must be one of ['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
```

## Mouse

### get_mouse_position

Retrieves the current physical position of the cursor on the screen.

Returns:

```
DictPosition: A dictionary like {"x": x, "y": y}
```

### click_element

Click an element.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
offsetX: Horizontal offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
offsetY: Vertical offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
button: Specifies which mouse button to click. Options are "left", "right", and "middle".
clickMode: Defines the type of click to perform. Options are "single_click", "double_click", "down", and "up".
executionMode: Options are "simulate" and "api". "simulate" will move the cursor, support all arguements of the function. "api" will not move the cursor, it can handle some situations that the target element be covered, but it supports less arguments than "simulate".
position: Specifies where on the element to click. Options are "center", "top_left", "top_right", "bottom_left", and "bottom_right". It will only work if executionMode is "simulate".
pressCtrl: If True, holds the Ctrl key during the click.
pressShift: If True, holds the Shift key during the click.
pressAlt: If True, holds the Alt key during the click.
pressWin: If True, holds the Windows key during the click.
duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to "position" immediately.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### move_to_element

Move to element.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
offsetX: Horizontal offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
offsetY: Vertical offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
position: Specifies where on the element to click. Options are "center", "top_left", "top_right", "bottom_left", and "bottom_right". It will only work if executionMode is "simulate".
duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to "position" immediately.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### click

Mouse click.

Parameters:

```
button: Specifies which mouse button to click. Options are "left", "right", and "middle".
clickMode: Defines the type of click to perform. Options are "single_click", "double_click", "down", and "up".
pressCtrl: If True, holds the Ctrl key during the click.
pressShift: If True, holds the Shift key during the click.
pressAlt: If True, holds the Alt key during the click.
pressWin: If True, holds the Windows key during the click.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### move_cursor

Move mouse.

Parameters:

```
x: The x-coordinate or horizontal offset (if relative is True) for the cursor's destination.
y: The y-coordinate or vertical offset (if relative is True) for the cursor's destination.
duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to tatget position immediately.
relative: If True, the x and y coordinates are treated as offsets from the current cursor position. If False, they are treated as absolute screen coordinates.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### scroll_wheel

Make the mouse scroll down or up.

Parameters:

```
times: The number of increments to scroll the wheel.
direction: The direction to scroll the wheel; valid values are "down" or "up".
pressCtrl: If True, holds the Ctrl key during the scroll.
pressShift: If True, holds the Shift key during the scroll.
pressAlt: If True, holds the Alt key during the scroll.
pressWin: If True, holds the Windows key during the scroll.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

## Keyboard

### write_text

Write text in the current element focused.

Parameters:

```
text: The text to be written.
executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or Capslock but "api" will not, and "uia" supports more characters.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### write_text_into_element

Focus an element then write text into it.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
text: The text to be written.
executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or Capslock but "api" will not, and "uia" supports more characters.
interval: the interval time(milliseconds) between type each character. Only works in "simulate" mode.
emptyOriginalText: Whether delete existing text(by typing ctrl+a and backspace).
validateWrittenText: Whether check the typed text, not support html element's simulate mode.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### type_key_in_element

Focus an element then type a key.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
key: The key to be typed, all supported key in the type InputKey: ['enter', 'esc', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'printscreen', 'scrolllock', 'pause', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 'add', 'subtract', 'multiply', 'divide', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'shift', 'shiftleft', 'shiftright', 'ctrl', 'ctrlleft', 'ctrlright', 'alt', 'altleft', 'altright', 'win', 'winleft', 'winright', 'volumemute', 'volumedown', 'volumeup', 'playpause', 'stop', 'nexttrack', 'prevtrack', 'browserback', 'browserfavorites', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserstop'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash)
pressCtrl: If True, holds the Ctrl key during the type.
pressShift: If True, holds the Shift key during the type.
pressAlt: If True, holds the Alt key during the type.
pressWin: If True, holds the Windows key during the type.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### type_key

Type a key in the current element focused.

Parameters:

```
key: The key to be typed, all supported key in the type InputKey: ['enter', 'esc', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'printscreen', 'scrolllock', 'pause', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 'add', 'subtract', 'multiply', 'divide', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'shift', 'shiftleft', 'shiftright', 'ctrl', 'ctrlleft', 'ctrlright', 'alt', 'altleft', 'altright', 'win', 'winleft', 'winright', 'volumemute', 'volumedown', 'volumeup', 'playpause', 'stop', 'nexttrack', 'prevtrack', 'browserback', 'browserfavorites', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserstop'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash)
typeMode: The type of keyboard action to perform. Options are:
    "click" for a single press and release,
    "key_down" for pressing the key down,
    "key_up" for releasing a pressed key.
pressCtrl: If True, holds the Ctrl key during the type.
pressShift: If True, holds the Shift key during the type.
pressAlt: If True, holds the Alt key during the type.
pressWin: If True, holds the Windows key during the type.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

## Window

### close_window

Close the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### check_window_exists

Check whether the element's window is existing.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
True if the element's window exists within the specified timeout, False otherwise.
```

### get_active_window

Get the selector of the currently active window.

Returns:

```
SelectorWindow: The selector of the currently active window.
```

### activate_element_window

Activate the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
```

### set_window_state

Set the element's window to normal, maximize or minimize.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
state: Desired window state, can be 'normal', 'maximize', or 'minimize'.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### get_window_position_and_size

Get the position and size of the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
DictPositionAndSize: {'x': <class 'int'>, 'y': <class 'int'>, 'width': <class 'int'>, 'height': <class 'int'>}
```

### set_window_position

Set the position of the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
x: The horizontal position (in pixels) where the window's upper left corner should be moved to.
y: The vertical position (in pixels) where the window's upper left corner should be moved to.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### set_window_size

Set the size of the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
width: The new width of the window in pixels.
height: The new height of the window in pixels.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### get_window_pid

Get the pid of the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
int: The pid of the window element.
```

### get_window_file_path

Get the file path of the element's window.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
str: The file path string.
```

## UiInterface

### highlight

Draw a rectangle around the element.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
color: The color of the highlight border. Available options are "red", "green", "blue", "yellow", "purple", "pink", "black".
duration: The time in milliseconds for which the highlight should remain visible on the screen.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### screenshot

Capture a screenshot of the element's area and save it.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
saveFilePath: The file path where the screenshot will be saved.
offsetX: The horizontal offset in pixels from the top-left corner of the element to start capturing the screenshot.
offsetY: The vertical offset in pixels from the top-left corner of the element to start capturing the screenshot.
width: The width of the screenshot in pixels. If None, the width of the element will be used.
height: The height of the screenshot in pixels. If None, the height of the element will be used.
override: If True, will overwrite an existing file at saveFilePath.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
str: The absolute path of the saved screenshot.
```

### get_image_position

Searches for an image on the screen and returns the coordinates of matched regions.

Parameters:

```
filePath: The path of the image file to locate.
region: A tuple (x, y, width, height) defining the search area. If None, searches the entire screen.
confidence: A float (0.0 to 1.0) indicating the required match accuracy.
grayscale: If True, searches in grayscale mode for faster detection.
limit: The maximum number of matches to return.
highlight: Whether highlight the matched position.
```

Returns:

```
DictPositionAndSize: A list of dictionaries containing the x, y, width, and height of the matched images: {'x': <class 'int'>, 'y': <class 'int'>, 'width': <class 'int'>, 'height': <class 'int'>}
```

### check_exists

Check if an element exists, raise False if it didn't appear at timeout.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
True if the element exists within the specified timeout, False otherwise.
```

### wait_appear

Wait an element to appear.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the element doesn't appear after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### wait_disappear

Wait an element to disappear.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the element doesn't disappear after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### get_parent

Get the selector of an element's parent. Only support SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
upwardLevel: The upward layer to find its parent element.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
SelectorWindow | SelectorUia | SelectorHtml: The parent element's selector.
```

### get_children

Get the direct chilren elements' selectors. Only support SelectorWindow, SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
list[SelectorUia] | list[SelectorHtml]: A list contains the selectors of the element's direct children.
```

### get_attr_dictionary

Get a dictionary contains all attributes of the element.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
DictUiaAttr | DictHtmlAttr: The attributes dictionary of the element, note some attributes with the prefix of "secondary-".
```

### get_text

Get all text of the element. Only support SelectorWindow, SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
tuple[list[str], str]: A tuple contains the all children element's text(if it's an uia element) and all text.
```

### set_text

Set an element's text by its API instead of inputting by keyboard. Only support SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
text: The text to be set.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### get_check_state

Get the check state of a checkbox or radio element. Only support SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
text: The text to be set.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
str: one of "checked", "unchecked", "indeterminate"
```

### set_check_state

Set the check state of a checkbox or radio element. Only support SelectorUia and SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
checkAction: Options are "checked", "unchecked", or "toggle". Note that if an HTML element's checked state is "indeterminate", action "toggle" will modity it to "checked" or "unchecked", depend on its previous check state, same like the mouse single click.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

### get_selection

Get the check state of a checkbox or radio element. Only support SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
selectionType: Options are "text", "value" or "index"
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

Returns:

```
str | int: Return a string if selectionType is "text" or "value", or an integer if selectionType is "index"
```

### set_selection

Get the check state of a checkbox or radio element. Only support SelectorHtml.

Parameters:

```
selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
text: set the selection by an option's text, it's mutually exclusive with value and index.
value: set the selection by an option's value, it's mutually exclusive with text and index.
index: set the selection by an option's index(start from 0), it's mutually exclusive with text and value.
timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
preExecutionDelay: Time to wait before performing the action (in milliseconds).
postExecutionDelay: Time to wait after performing the action (in milliseconds).
```

## Browser

### open_browser

Open a browser to access the url.

If the browser is running, it will open a new tab.

Parameters:

```
browserType: The type of browser to manipulate (currently only "chrome" is supported).
url: The URL to open in the browser.
path: The filesystem path to the browser exe. If not provided, it attempts to locate the browser in common directories.
params: Additional command-line parameters to pass when launching browser.

    Such as "--start-maximized".

    For Chrome, you can check all params in [List of Chromium Command Line Switches](https://peter.sh/experiments/chromium-command-line-switches/)
```

Returns:

```
BrowserObj: An object representing the browser session.
```

### bind_browser

Bind a running browser.

Parameters:

```
browserType: The type of browser to manipulate (currently only "chrome" is supported).
```

Returns:

```
BrowserObj: An object representing the browser session.
```

### get_state

Get the active tab's state.

Parameters:

```
browserObj: The browser object to manipulate.
```

Returns:

```
str: one of "unloaded", "loading", "complete"
```

### go_backward

Make the active tab go backward.

Parameters:

```
browserObj: The browser object to manipulate.
```

### go_forward

Make the active tab go forward.

Parameters:

```
browserObj: The browser object to manipulate.
```

### refresh

Make the active tab refresh.

Parameters:

```
browserObj: The browser object to manipulate.
```

### wait_load_completed

Wait for the active tab being loaded completed.

Parameters:

```
browserObj: The browser object to manipulate.
```

### navigate

Navigate the active tab to a specified url.
The url should starts with a protocol, such as http:// or https://

Parameters:

```
browserObj: The browser object to manipulate.
url: The URL to navigate to. It should starts with a protocol, such as http:// or https://
waitLoadCompleted: If True, waits for the page load to complete before returning.
timeout: The maximum time (in milliseconds) to wait for the page load to complete, applicable only if waitLoadCompleted is True.
```

### open_new_tab

Create a new tab to open a specified url.
The url should starts with a protocol, such as http:// or https://

Parameters:

```
browserObj: The browser object to manipulate.
url: The URL to access. It should starts with a protocol, such as http:// or https://
waitLoadCompleted: If True, waits for the page load to complete before returning.
timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitLoadCompleted is True.
```

### open_new_window

Create a new browser window to open a specified url.
The url should starts with a protocol, such as http:// or https://

Parameters:

```
browserObj: The browser object to manipulate.
url: The URL to access. It should starts with a protocol, such as http:// or https://
waitLoadCompleted: If True, waits for the page load to complete before returning.
timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitLoadCompleted is True.
```

### switch_tab

Switch to a specific tab of the active browser window.

Parameters:

```
browserObj: The browser object to manipulate.
titleOrIndex: The target tab's tile or index(start from 0)
```

### close_current_tab

Close the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

### get_download_list

No need for description.

### get_source_code

Get the HTML source code of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

### get_all_text

Get all text in the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

### get_url

Get the url of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

### get_title

Get the title of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

### get_cookies

Get the cookies of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

Returns:

```
list[DictCookiesOfChrome]: The list of Chrome cookies standard attributes(refer to [Types-Cookie](https://developer.chrome.com/docs/extensions/reference/api/cookies#type-Cookie)), it will be improved with more browser type be added.
```

### set_cookies

Sets a cookie to the active tab with the given cookie data; may overwrite equivalent cookies if they exist.

Parameters:

```
browserObj: The browser object to manipulate.
domain: The domain of the cookie.
name: The name of the cookie.
path: The path of the cookie.
value: The value of the cookie. If it's None, it will use the original value in browser.
expirationDate: The expiration date of the cookie as the number of seconds since the UNIX epoch. If it's None, it will use the original value in browser.
httpOnly: Whether the cookie should be marked as HttpOnly. If it's None, it will use the original value in browser.
secure: Whether the cookie should be marked as Secure. If it's None, it will use the original value in browser.
storeId: The ID of the cookie store in which to set the cookie. If it's None, it will use the original value in browser.
sameSite: The cookie's same-site status. If it's None, it will use the original value in browser.
```

Returns:

```
DictCookiesOfChrome: The updated Chrome cookies standard attributes(refer to [Types-Cookie](https://developer.chrome.com/docs/extensions/reference/api/cookies#type-Cookie)), it will be improved with more browser type be added.
```

### get_scroll_position

Get the scroll position of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
```

Returns:

```
tuple[int,int]: The scrollX and scrollY.
```

### set_scroll_position

set the scroll position of the active tab.

Parameters:

```
browserObj: The browser object to manipulate.
x: The pixel along the horizontal axis of the web page that you want displayed in the upper left.
y: The pixel along the vertical axis of the web page that you want displayed in the upper left.
```

### execute_js_code

Executes a JavaScript code string in the active tab of the specified browser.

This function allows you to run JavaScript code in the context of the current active tab's web page.

The code is executed as if it were being run directly in the browser's developer console.

Parameters:

```
browserObj: The browser object to manipulate.
jsCode: The JavaScript code to be executed.

    This can include expressions, function calls, or IIFE (Immediately Invoked Function Expressions).

    The code must be a valid JavaScript expression or function to execute correctly.
returnImmediately: If True, the function will return None immediately after execution and will not wait for a result.

    If False, the function will wait for the JavaScript execution to complete and return the result of the JavaScript code.
```

Returns:

```
the returned value of JavaScript code. It will alway be None if returnImmediately is True.

Usage Example:
    ```python
    # Example 1: Execute a simple JavaScript expression and get the result
    result = execute_js_code(browserObj, jsCode="123 + 456", returnImmediately=False)
    print(result)  # Outputs: 579

    # Example 2: Execute an IIFE that returns a string
    result = execute_js_code(browserObj, jsCode="(function(){ return 'Hello, World!'; })()", returnImmediately=False)
    print(result)  # Outputs: 'Hello, World!'

    # Example 3: Execute JavaScript without waiting for the result
    execute_js_code(browserObj, jsCode="document.body.style.backgroundColor = 'blue';", returnImmediately=True)
    ```
```

## Excel

### open_Excel_file

Opens an Excel file, or creates it if specified.

If a file have be opened, it will be opened with read-only mode.

Parameters:

```
path: The path to the Excel file.
visible: If True, opens Excel in visible mode.
password: The password for opening the workbook, if required.
writePassword: The password for write access, if required.
createIfNotExist: If True, creates a new workbook if the file does not exist.
readOnly: If True, opens the workbook in read-only mode.
```

Returns:

```
ExcelWorkbook: An object representing the opened workbook.
```

### bind_Excel_file

If there are files with same name, it will bind only one of them.

Parameters:

```
fileName: The opening Excel workbook file name.
visible: If True, opens Excel in visible mode.
password: The password for opening the workbook, if required.
writePassword: The password for write access, if required.
createIfNotExist: If True, creates a new workbook if the file does not exist.
readOnly: If True, opens the workbook in read-only mode.
```

Returns:

```
ExcelWorkbook: An object representing the opened workbook.
```

### save

Save the Excel workbook object.

Parameters:

```
excelObj: The Excel workbook object.
```

### save_as_and_reopen

Saves the workbook to a new file and reopens it under the new name.

Parameters:

```
excelObj: The Excel workbook object.
destinationPath: The path where the workbook will be saved.
password: An optional password for saving the workbook.
```

### close

Close the Excel workbook object.

Parameters:

```
excelObj: The Excel workbook object.
save: If True, saves the workbook before closing.
```

### activate_window

Brings the Excel window to the front and restores it if minimized.

Parameters:

```
excelObj: The Excel workbook object.
```

### get_last_row

Get the last row number of a given sheet.

If a specific column is provided, it returns the last row number of that column.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
col: The column (name or number) to check. If None, checks the entire sheet.
```

Returns:

```
int: The number of the last row with data in the specified sheet/column.
```

### get_last_column

Get the last column (number or name) of a given sheet.

If a specific row is provided, it returns the last column of that row.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
row: The row number to check. If None, checks the entire sheet.
```

Returns:

```
tuple[str,int]: The name and number of the last column with data in the specified sheet/row.
```

### convert_col_num_to_str

No need for description.

### convert_col_str_to_num

No need for description.

### read_cell

Read the value of a specific cell.

Can return either the actual value or the displayed value.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
cell: The cell to read, either as an address string or a [row, column] list.
returnDisplayed: If True, returns the displayed value; otherwise, returns the actual value.
```

Returns:

```
TypeOfCellData: The value of the cell.
```

### read_row

Reads an entire row in an Excel sheet starting from the specified cell.

Can return either the actual values or the displayed values of the cells in the row.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the row to be read. Can be specified as a string (e.g., 'A1') or a list indicating the row and column [row, column].
returnDisplayed: If True, returns the displayed values of the cells. If False, returns their actual values.
```

Returns:

```
list[TypeOfCellData]|None: A list of values from the specified row. Returns None if the starting cell is beyond the last column with data.
```

### read_column

Reads an entire column in an Excel sheet starting from the specified cell.

Can return either the actual values or the displayed values of the cells in the column.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the column to be read. Can be specified as a string (e.g., 'A1') or a list indicating the row and column [row, column].
returnDisplayed: If True, returns the displayed values of the cells. If False, returns their actual values.
```

Returns:

```
list[TypeOfCellData]|None: A list of values from the specified column. Returns None if the starting cell is below the last row with data.
```

### read_range_list

Reads a specified range from an Excel sheet and returns the data in the desired format.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the range.
endCell: The ending cell of the range. If None, reads till the last cell.
returnDisplayed: If True, returns the displayed values as string; otherwise, returns actual cell values(TypeOfCellData).
```

Returns:

```
list[list[str]] | list[list[TypeOfCellData]] | None: The data from the specified range in the chosen format. | None
```

### read_range_df

Reads a specified range from an Excel sheet and returns the data in the desired format.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the range.
endCell: The ending cell of the range. If None, reads till the last cell.
addTitle: If True, uses the first row as headers.
returnDisplayed: If True, returns the displayed values as string; otherwise, returns actual cell values(TypeOfCellData).
```

Returns:

```
pandas.DataFrame | None
```

### write_cell

Writes data to a specified cell in an Excel sheet.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
cell: The cell to write to, specified as a string (e.g., 'A1') or a list [row, column].
data: The data to write to the cell.
save: If True, saves the workbook immediately after writing.
```

### write_row

Writes a list of data to a row in an Excel sheet starting from a specified cell.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the row.
data: A list of data to be written to the row.
save: If True, saves the workbook immediately after writing.
```

### write_column

Writes a list of data to a column in an Excel sheet starting from a specified cell.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the column.
data: A list of data to be written to the column.
save: If True, saves the workbook immediately after writing.
```

### write_range

Writes a pandas DataFrame or a 2D list to a specified range in an Excel sheet.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell for the data range.
data: The data to write, either as a DataFrame or a 2D list.
writeTitleRow: If True, includes the DataFrame's column titles, or the first item of the 2D list.
save: If True, saves the workbook immediately after writing.
```

### insert_row

Create a new empty row and then write a list of data to a row in an Excel sheet starting from a specified cell.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the row.
data: A list of data to be written to the row.
save: If True, saves the workbook immediately after inserting.
```

### insert_column

Create a new empty row and then write a list of data to a column in an Excel sheet starting from a specified cell.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the column.
data: A list of data to be written to the column.
save: If True, saves the workbook immediately after inserting.
```

### delete_row

Delete the row of the cell and move the next row up.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
cell: A cell whthin the row to delete.
save: If True, saves the workbook immediately after deleting.
```

### delete_column

Delete the column of the cell and move the next column left.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
cell: A cell whthin the column to delete.
save: If True, saves the workbook immediately after deleting.
```

### select_range

Select the specific range.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the range.
endCell: The ending cell of the range.  If None, select till the last cell.
```

### get_selected_cells

Get the list of all selected cells of the current activated sheet.

Parameters:

```
excelObj: The Excel workbook object.
```

Returns:

```
list[str]: A list of selected ranges, with addresses in standard Excel format (e.g., 'A1:B2').
```

### get_selected_range

Get the list of all selected ranges of the current activated sheet.

Parameters:

```
excelObj: The Excel workbook object.
```

Returns:

```
list[str]: A list of selected cells, with addresses in standard Excel format (e.g., 'A1').
```

### clear_range

Clear the content or format of the range.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
startCell: The starting cell of the range.
endCell: The ending cell of the range.  If None, clear till the last cell.
clearContent: Whether clear contents of the range.
clearFormat: Whether clear format of the range.
save: If True, saves the workbook immediately after clearing.
```

### activate_sheet

Activate sheet by name or index.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
```

### add_sheet

Add a new sheet in specific position.

Parameters:

```
excelObj: The Excel workbook object.
newSheetName: The new sheet's name.
anchorSheet: The new sheet will add before or after the anchor sheet.
direction: Options are "before" and "after".
save: If True, saves the workbook immediately after adding.
```

### rename_sheet

Rename a sheet.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
newSheetName: The sheet's new name.
save: If True, saves the workbook immediately after renaming.
```

### copy_sheet

Copy a sheet.

Parameters:

```
srcExcelObj: The Excel workbook object that copy from.
srcSheet: The sheet name or index(start from 0) in the source workbook.
dstExcelObj: The Excel workbook object that copy into.
dstAnchorSheet: The new sheet will add before or after the anchor sheet in the dstExcelObj.
newSheetName: The sheet's new name.
direction: Options are "before" and "after".
save: If True, saves the workbook immediately after copying.
```

### delete_sheet

Delete a sheet.

Parameters:

```
excelObj: The Excel workbook object.
sheet: The name or index(start from 0) of the sheet.
save: If True, saves the workbook immediately after writing.
```

### get_activate_sheet

Get the current activated sheet's name.

Parameters:

```
excelObj: The Excel workbook object.
```

### get_sheet_list

Get the list of all sheets' names of the Excel workbook object.

Parameters:

```
excelObj: The Excel workbook object.
```

### run_macro

Run a macro of a xlsm file.

Parameters:

```
excelObj: The Excel workbook object(.xlsm file).
macroName: Name of Sub or Function with or without module name, e.g., 'Module1.MyMacro' or 'MyMacro'
arguments: The list of arguments that will send into the macro function.
```

Returns:

```
The returned value of the marco.
```

## Outlook

### send_email

Send an email using a specified Outlook account.

Parameters:

```
account: The email address of the account to send the email from.
to: A semicolon-separated string of the recipient(s) of the email.
subject: The subject of the email.
body: The body content of the email.
bodyFormat: The format of the email body ('text' or 'html').
attachments: Path(s) to file(s) to attach. Can be a single path, a list of paths or None.
cc: A semicolon-separated string of the CC recipient(s) of the email.
bcc: A semicolon-separated string of the BCC recipient(s) of the email.
```

### get_folder_list

Retrieves a list of all folders from the Outlook account.

Parameters:

```
account: The email account to fetch folder names from.
```

Returns:

```
list[str]: A list of folder names.
```

### get_email_list

Fetch a list of emails from a specified Outlook account and folder.

Parameters:

```
account: The email account to fetch emails from.
folder: The folder to fetch emails from.
filter: A string to filter emails based on their properties.
numToGet: Maximum number of emails to fetch.
onlyUnread: Whether to retrieve only unread emails.
markAsRead: Whether to mark retrieved emails as read.
```

Returns:

```
tuple[list[DictOutlookMailInfo],list[win32com.client.CDispatch]]:
        A list of basic information dictionaries for each email, adhering to the DictOutlookMailInfo structure.
        A list of email objects.
```

### move_email

Move an email by its uid.

Parameters:

```
account: The email account.
emailObj: The win32com.client.CDispatch objects to move.
folder: The name of the folder to move.
```

### reply_to_email

Reply an email.

Parameters:

```
emailObj: The win32com.client.CDispatch objects to reply.
body: The body content of the email.
bodyFormat: The format of the email body ('text' or 'html').
attachments: Path(s) to file(s) to attach. Can be a single path ,a list of paths or None.
replyAll: Whether to reply all recipients.
newSubject: A custom subject for the reply.
```

### delete_email

Delete an email.

Parameters:

```
emailObj: A win32com.client.CDispatch objects.
```

### download_attachments

Download all attachments of an email.

Parameters:

```
emailObj: The win32com.client.CDispatch objects to download its attachments.
downloadPath: The folder to save download files.
```

Returns:

```
list[str]: A list contains the path of all attachments.
```

## Application

### run_application

Run an application with a specified window state.

Parameters:

```
filePath: The path of the application to run.
windowState: 'default', 'maximize', 'minimize', 'hide'
```

Returns:

```
int: The application's PID.
```

### open_url

Open a file or webpage using the default application.

Parameters:

```
url: The url of the target file or webpage. It may need to start with a protocol (e.g., http:// or https://)
```

### check_process_running

Check whether an application is running by its name or PID.

Parameters:

```
nameOrPID: the process name or PID.
```

Returns:

```
bool: If the process is running, return True, otherwise return False.
```

### stop_process

Stop(kill) an application by its name or PID.

Parameters:

```
nameOrPID: the process name or PID.
```

## Database

### build database connection

You can learn how to use it in liberrpa.Database.DatabaseConnection's Docstring

### fetch_one

Execute a query and fetch a single row.

Parameters:

```
connObj: The active database connection.
query: The SQL query to be executed.

    Example: "SELECT * FROM employees WHERE employee_id = :id"
params: The parameters to bind to the query.

    This should be a dictionary where the keys correspond to the placeholders in the SQL query (e.g., ":id"). Example: {"id": 1}.

    If no parameters are required, pass None.
returnDict: Whether to return the result as a dictionary (True) or list (False).
```

Returns:

```
dict[str, Any] | list[Any] | None: The fetched row as a dictionary or list, or None if no row is found.
```

### fetch_all

Execute a query and fetch all rows.

Parameters:

```
connObj: The active database connection.
query: The SQL query to be executed.

    Example: "SELECT * FROM employees WHERE salary > :salary"
params: The parameters to bind to the query.

    This should be a dictionary where the keys correspond to the placeholders in the SQL query (e.g., ":salary").

    Example: {"salary": 50000}.

    If no parameters are required, pass None.
returnDict: Whether to return the results as dictionaries (True) or lists (False).
```

Returns:

```
list[dict[str, Any]] | list[list[Any]]: A list of rows, where each row is a dictionary or list.
```

### execute

Execute an SQL query and return the number of affected rows.

Parameters:

```
connObj: The active database connection.
query: The SQL query to be executed.

    Example: "UPDATE employees SET salary = :salary WHERE employee_id = :id"
params: The parameters to bind to the query.

    This can be a single dictionary or a list of dictionaries for bulk operations.

    Example for single operation: {"salary": 55000, "id": 1}.

    Example for bulk operation: [{"salary": 55000, "id": 1}, {"salary": 62000, "id": 2}].

    If no parameters are required, pass None.
```

Returns:

```
int: The number of rows affected by the query.
```

## Data

### sanitize_filename

Sanitize a given filename using the pathvalidate module.

Parameters:

```
filename: The original filename to sanitize.
```

Returns:

```
str: The sanitized filename.
```

### get_length

Get the length of the given value.

Parameters:

```
value: The value whose length is to be measured.
```

Returns:

```
int: The length of the value.
```

### to_integer

Convert the given value to an integer.

Parameters:

```
value: The value to convert.
```

Returns:

```
int: The converted integer value.
```

### to_float

Convert the given value to a float.

Parameters:

```
value: The value to convert.
```

Returns:

```
float: The converted float value.
```

### to_decimal

Convert the given value to a Decimal.

Parameters:

```
value: The value to convert.
```

Returns:

```
Decimal: The converted decimal value.
```

### to_boolean

Convert the given value to a boolean.

Parameters:

```
value: The value to convert.
```

Returns:

```
bool: The converted boolean value.
```

### clone

Create a deep copy of the given value.

Parameters:

```
value: The value to clone.
```

Returns:

```
T: The cloned value.
```

### get_type

Get the type name of the given value.

Parameters:

```
value: The value whose type is to be identified.
```

Returns:

```
str: The type name of the value.
```

### get_uuid

Generate a new UUID.

Returns:

```
str: The generated UUID as a string.
```

### get_random_integer

Return a random integer in the range [start, end].

Parameters:

```
start: The start of the range.
end: The end of the range.
```

Returns:

```
int: A random integer within the specified range.
```

### get_random_float

Generate a random float in the specified range.

Parameters:

```
start: The start of the range, or None for [0.0, 1.0).
end: The end of the range, or None for [0.0, 1.0).
```

Returns:

```
float: A random float within the specified range.
```

### json_dumps

Serialize an object to a JSON formatted string.

Parameters:

```
value: The object to serialize.
indent: The number of spaces to use for indentation.
```

Returns:

```
str: The JSON formatted string.
```

### json_loads

Deserialize a JSON formatted string to a Python object.

Parameters:

```
jsonStr: The JSON string to deserialize.
```

Returns:

```
Any: The deserialized Python object.
```

### join_to_str

Join a list of strings into a single string with a specified separator.

Parameters:

```
iterableObj: The iterable value of strings to join.
joinStr: The string used to separate the joined strings.
```

Returns:

```
str: The joined string.
```

## Str

### replace

Replaces occurrences of a substring with a new substring in the given string.

Parameters:

```
strObj: The original string.
old: The substring to be replaced.
new: The substring to replace with.
count: Maximum number of occurrences to replace. Default is -1 (all occurrences).
```

Returns:

```
str: The modified string.
```

### split

Splits the string into a list based on the given separator.

Parameters:

```
strObj: The string to be split.
separator: The delimiter used to split the string.
maxSplit: Maximum number of splits. Default is -1 (all occurrences).
```

Returns:

```
list[str]: A list of split strings.
```

### split_lines

Splits the string into lines.

Parameters:

```
strObj: The string to split into lines.
keepends: If True, line breaks are included in the resulting list.
```

Returns:

```
list[str]: A list of lines from the string.
```

### fill

Pads the string with a specified character to the desired width.

Parameters:

```
strObj: The original string.
width: The desired total width of the string after padding.
character: The character to use for padding. Default is '0'.
```

Returns:

```
str: The padded string.
```

### count

Counts occurrences of a substring within the string.

Parameters:

```
strObj: The string to search in.
subStr: The substring to count.
start: The starting index for the search. Default is None (start from the beginning).
end: The ending index for the search. Default is None (search to the end).
```

Returns:

```
int: The number of occurrences of the substring.
```

### find_from_start

Finds the first occurrence of a substring starting from the beginning of the string.

Return -1 if the substring is not found.

Parameters:

```
strObj: The string to search in.
subStr: The substring to find.
start: The starting index for the search. Default is None (start from the beginning).
end: The ending index for the search. Default is None (search to the end).
```

Returns:

```
int: The index of the first occurrence. Return -1 if the substring is not found.
```

### find_from_end

Finds the last occurrence of a substring starting from the end of the string.

Return -1 if the substring is not found.

Parameters:

```
strObj: The string to search in.
subStr: The substring to find.
start: The starting index for the search. Default is None (start from the beginning).
end: The ending index for the search. Default is None (search to the end).
```

Returns:

```
int: The index of the last occurrence. Return -1 if the substring is not found.
```

### case_to_lower

Converts all characters in the string to lowercase.

Parameters:

```
strObj: The string to convert.
```

Returns:

```
str: The string in lowercase.
```

### case_to_upper

Converts all characters in the string to uppercase.

Parameters:

```
strObj: The string to convert.
```

Returns:

```
str: The string in uppercase.
```

### check_case_lower

Checks if all characters in the string are lowercase.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if all characters are lowercase, False otherwise.
```

### check_case_upper

Checks if all characters in the string are uppercase.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if all characters are uppercase, False otherwise.
```

### case_swap

Swaps the case of each character in the string.

Parameters:

```
strObj: The string to modify.
```

Returns:

```
str: The string with swapped cases.
```

### strip

Removes specified characters from the string based on the given direction.

Parameters:

```
strObj: The string to modify.
characters: A list of characters to strip. If None, strips whitespace.
direction: The direction to strip characters. Options are "start", "end", or "both". Default is "start".
```

Returns:

```
str: The modified string.
```

### remove_prefix

Removes a specified prefix from the beginning of a string if it exists.

Parameters:

```
strObj: The string from which to remove the prefix.
prefix: The prefix to remove.
```

Returns:

```
str: The string after removing the specified prefix.
```

### remove_suffix

Removes a specified suffix from the end of a string if it exists.

Parameters:

```
strObj: The string from which to remove the suffix.
suffix: The suffix to remove.
```

Returns:

```
str: The string after removing the specified suffix.
```

### check_start

Checks if the string starts with the specified substring.

Parameters:

```
strObj: The string to check.
subStr: The substring to look for at the start.
```

Returns:

```
bool: True if the string starts with subStr, False otherwise.
```

### check_end

Checks if the string ends with the specified substring.

Parameters:

```
strObj: The string to check.
subStr: The substring to look for at the end.
```

Returns:

```
bool: True if the string ends with subStr, False otherwise.
```

### is_alpha_and_numeric

Checks if the string contains only alphanumeric characters.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if the string is alphanumeric, False otherwise.
```

### is_alpha

Checks if the string contains only alphabetic characters.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if the string is alphabetic, False otherwise.
```

### is_numeric

Checks if the string contains only numeric characters.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if the string is numeric, False otherwise.
```

### is_ascii

Checks if the string is empty or all characters in the string are ASCII.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if all characters are ASCII or the string is empty, False otherwise.
```

### is_digit

Checks if the string contains only digit characters.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if the string is composed of digits, False otherwise.
```

### is_decimal

Checks if the string represents a decimal number.

Parameters:

```
strObj: The string to check.
```

Returns:

```
bool: True if the string is a decimal number, False otherwise.
```

## List

### insert

Insert a value into a list at a specified index.

Parameters:

```
listObj: The list to modify.
index: The index at which to insert the value.
value: The value to insert.
```

### append

Append a value to the end of a list.

Parameters:

```
listObj: The list to modify.
value: The value to append.
```

### pop

Remove and return an item from a list at a specified index.

Parameters:

```
listObj: The list to modify.
index: The index of the item to remove. Default is -1 (last item).
```

Returns:

```
T: The removed item.
```

### remove

Remove the first occurrence of a value from a list.

Parameters:

```
listObj: The list to modify.
value: The value to remove.
```

### clear

Clear all items from a list.

Parameters:

```
listObj: The list to clear.
```

### slice

Return a slice of the list between start and end indices.

Parameters:

```
listObj: The list to slice.
start: The starting index of the slice.
end: The ending index of the slice.
```

Returns:

```
list[T]: The sliced list.
```

### extend

Extend the list by appending elements from another list.

Parameters:

```
listObj: The list to modify.
listToExtend: The list of elements to append.
```

### count

Count occurrences of a value in the list.

Parameters:

```
listObj: The list to search.
value: The value to count.
```

Returns:

```
int: The number of occurrences.
```

### find

Return the first index of a value in the list.
Raises ValueError if the value is not present.

Parameters:

```
listObj: The list to search.
value: The value to find.
start: The starting index for the search.
stop: The ending index for the search. If it's None, use sys.maxsize
```

Returns:

```
int: The index of the value.
```

### reverse

Reverse the order of items in a list.

Parameters:

```
listObj: The list to reverse.
```

### sort

Sort the items in a list.

Parameters:

```
listObj: The list to sort.
keyFunc: Optional function to specify the sort order.
reverse: If True, sort in descending order.
```

## Dict

### clear

Clear all items from the specified dictionary.

Parameters:

```
dictObj: The dictionary to clear.
```

### get

Retrieve the value associated with a specified key from the dictionary.

If the key is not found, return the default.

Parameters:

```
dictObj: The dictionary to search.
key: The key whose value is to be retrieved.
default: The value to return if the key is not found.
```

Returns:

```
T2 | None: The value associated with the key or the default value if not found.
```

### pop

Remove a specified key from the dictionary and return its corresponding value.

If the key is not found, return the default.

Parameters:

```
dictObj: The dictionary to modify.
key: The key to remove from the dictionary.
default: The value to return if the key is not found.
```

Returns:

```
T2 | None: The value associated with the removed key or the default value if not found.
```

### pop_item

Remove a specified key from the dictionary and return its corresponding value.

Raise KeyError if dictObj is empty.

Parameters:

```
dictObj: The dictionary to modify.
key: The key to remove from the dictionary.
default: The value to return if the key is not found.
```

Returns:

```
T2 | None: The value associated with the removed key or the default value if not found.
```

### get_key_list

Retrieve a list of keys from the specified dictionary.

Parameters:

```
dictObj: The dictionary from which to get the keys.
```

Returns:

```
list[T]: A list of keys in the dictionary.
```

### get_value_list

Retrieve a list of values from the specified dictionary.

Parameters:

```
dictObj: The dictionary from which to get the values.
```

Returns:

```
list[T]: A list of values in the dictionary.
```

### extend

Retrieve a list of values from the specified dictionary.

Parameters:

```
dictObj: The dictionary from which to get the values.
```

Returns:

```
list[T]: A list of values in the dictionary.
```

## Regex

### find_one

Finds the first occurrence of a pattern in the given string.

Parameters:

```
strObj: The string to search.
pattern: The regex pattern to match.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
str | None: The matched string or None if no match is found.
```

### find_all

Finds all occurrences of a pattern in the given string.

Parameters:

```
strObj: The string to search.
pattern: The regex pattern to match.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
list[str]: A list of all matched strings.
```

### match_start

Checks for a match only at the start of the string.

Parameters:

```
strObj: The string to check.
pattern: The regex pattern to match.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
str | None: The matched string or None if no match is found.
```

### match_full

Checks for a match that covers the entire string.

Parameters:

```
strObj: The string to check.
pattern: The regex pattern to match.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
str | None: The matched string or None if no match is found.
```

### split

Splits the string at each occurrence of the pattern.

Parameters:

```
strObj: The string to split.
pattern: The regex pattern to use for splitting.
maxSplit: The maximum number of splits to perform; 0 means no limit.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
list[str]: A list of substrings after splitting.
```

### replace

Replaces occurrences of the pattern in the string with a new string.

Parameters:

```
strObj: The original string.
pattern: The regex pattern to match.
newStr: The string to replace matches with.
count: The maximum number of replacements to perform; 0 means all.
ignoreCase: If True, match case-insensitively.
multiLine: If True, treat input as multiple lines.
dotAll: If True, '.' matches any character, including newline.
verbose: If True, allows for more readable regex patterns.
ascii: If True, restricts matching to ASCII characters.
local: If True, uses locale-dependent matching.
```

Returns:

```
str: The modified string with replacements made.
```

## Math

### round

Rounds a number to a specified precision in fractional digits.
fraction may be negative.

Parameters:

```
value: The number to be rounded (int, float, or Decimal).
fraction: The number of decimal places to round to. Can be negative.
```

Returns:

```
The rounded value, with the same type as the input number.
```

### check_float_equal

Checks if two floating-point numbers are approximately equal.

Parameters:

```
value1: The first float to compare.
value2: The second float to compare.
```

Returns:

```
True if the values are close, False otherwise.
```

### absolute

Computes the absolute value of a number.

Parameters:

```
value: The number for which to compute the absolute value.
```

Returns:

```
The absolute value of the input number.
```

### get_int_and_fraction

Splits a number into its integer and fractional parts.

Parameters:

```
value: The number to split (int, float, or Decimal).
```

Returns:

```
tuple[int, float]: A tuple containing the integer part and the fractional part.
```

## Time

### get_unix_time

Returns the current time in Unix timestamp format.

Returns:

```
float: The current time in seconds since the epoch (January 1, 1970).
```

### get_datetime_now

Returns the current local date and time.

Returns:

```
datetime: The current local date and time.
```

### build_datetime

Builds a datetime object from the provided components.

Parameters:

```
year: Year of the datetime.
month: Month of the datetime.
day: Day of the datetime.
hour: Hour of the datetime.
minute: Minute of the datetime.
second: Second of the datetime.
microsecond: Microsecond of the datetime.
```

Returns:

```
datetime: The constructed datetime object.
```

### str_to_datetime

Converts a string representation of a date and time into a datetime object.

Check the format codes in [strftime() and strptime() Format Codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes)

Parameters:

```
strObj: The string representation of the date and time.
format: The format of the string.
```

Returns:

```
datetime: The corresponding datetime object.
```

### datetime_to_str

Converts a datetime object into a string representation.

Check the format codes in [strftime() and strptime() Format Codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes)

Parameters:

```
datetimeObj: The datetime object to convert.
format: The format for the output string (default is "%Y-%m-%d %H:%M:%S").
```

Returns:

```
str: The string representation of the datetime object.
```

### get_datetime_attr

Retrieves a specific attribute from a datetime object.

Parameters:

```
datetimeObj: The datetime object from which to retrieve the attribute.
attr: The attribute to retrieve (one of "year", "month", "day", "hour", "minute", "second", "millisecond", "microsecond").
```

Returns:

```
int: The value of the requested attribute.
```

### add_datetime

Adds a specified amount of time to a datetime object.

Parameters:

```
datetimeObj: The original datetime object.
week: Number of weeks to addfraction.
day: Number of days to addfraction.
hour: Number of hours to addfraction.
minute: Number of minutes to addfraction.
second: Number of seconds to addfraction.
millisecond: Number of milliseconds to addfraction.
microsecond: Number of microseconds to addfraction.
```

Returns:

```
datetime: The new datetime object after adding the specified time.
```

## File

### create_folder

Creates a folder at the specified path.

Parameters:

```
folderPath: The path where the folder will be created.
createParent: If True, creates all missing parent directories. If False, an error is raised if a parent directory is missing.
errorIfExisted: If True, raises an error if the folder already exists; otherwise, does nothing if the folder exists.
```

### read_file_content

Reads the content of a file using the specified encoding.

Parameters:

```
filePath: The path of the file to read.
encoding: The encoding to use for reading the file. If None, uses the system default.
```

Returns:

```
str: The content of the file as a string.
```

### write_file

Overwrites the content of a specified file with the given text, using the specified encoding.
A new file will be created if "filePath" doesn't exist.

Parameters:

```
filePath: The path of the file whose content is to be overwritten.
text: The text to write into the file.
encoding: The encoding to use for writing the text to the file. Defaults to "utf-8".
```

### append_write_file

Appends text to the end of a specified file without overwriting its existing content, using the specified encoding.
A new file will be created if "filePath" doesn't exist.

Parameters:

```
filePath: The path of the file to which the text is to be appended.
text: The text to append to the file.
encoding: The encoding to use for writing the text to the file. Defaults to "utf-8".
```

### wait_file_download

Waits for a file to finish downloading by checking its size. It will throw a TimeoutError If the file does not reach the expected size within the given attempts.

Parameters:

```
- filePath: The path of the file to check.
- retryTimes: The number of times to check before timing out.
- retryInterval: The time(in seconds) to wait between retries.
- threshold: The minimum file size(in bytes) to consider the download complete.
```

### get_file_fullname

Get the final path component(basename and suffix).

Parameters:

```
filePath: The filePath path.
```

Returns:

```
str: The file's name
```

### get_file_basename

Get the final path component, minus its last suffix.

Parameters:

```
filePath: The filePath path.
```

Returns:

```
str: The file's basename(without suffix)
```

### get_file_suffix

Get the file's suffix(contains the dot).

Parameters:

```
filePath: The filePath path.
```

Returns:

```
str: The file's suffix(contains the dot)
```

### check_file_exists

Whether this path is a regular file (also True for symlinks pointing to regular files).

Parameters:

```
filePath: The path of the folder to check.
```

Returns:

```
bool: If the path is not exists, it will return False.
```

### check_folder_exists

Whether this path is a directory.

Parameters:

```
folderPath: The path of the folder to check.
```

Returns:

```
bool: If the path is not exists, it will return False.
```

### get_parent_folder_path

Returns the absolute path of the parent folder for a given path.

Parameters:

```
path: The path for which to retrieve the parent directory.
```

Returns:

```
str: The absolute path of the parent folder.
```

### get_file_size

Returns the size of the specified file in bytes.

Parameters:

```
filePath: The path to the file whose size is to be determined.
```

Returns:

```
int: The size of the file in bytes.
```

### get_folder_size

Calculates the total size of all files within the specified folder and its subfolders.

Parameters:

```
folderPath: The path of the folder for which the total file size is to be calculated.
```

Returns:

```
int: The total size of all files in the specified folder, measured in bytes.
```

### copy_file

Copies a file from a source path to a destination path and returns the absolute path of the destination file.

Optionally allows overwriting of an existing file at the destination.

Parameters:

```
srcFilePath: The path of the source file to copy.
dstFilePath: The path where the source file should be copied to.
overwriteIfExist: If set to True, the destination file will be overwritten if it already exists;

    if False, a FileExistsError will be raised if the destination file exists.
```

Returns:

```
str: The absolute path of the copied file at the destination.
```

### copy_folder

Recursively copy a directory tree. The destination directory must not already exist.

Parameters:

```
srcFolderPath: The path of the source folder to copy.
dstFolderPath: The path where the source folder should be copied to. This path must not already exist.
```

Returns:

```
str: The absolute path of the destination folder after copying.
```

### move_file_or_folder

Recursively move a file or directory to another location. This is similar to the Unix "mv".

Return the file or directory's destination. It will overwrite the destination file by default if it exists.

Parameters:

```
srcPath: The path of the file or folder to move.
dstPath: The path where the file or folder should be moved to.
```

Returns:

```
str: The absolute path of the dstPath.
```

### remove_file

No need for description.

### remove_folder

No need for description.

### get_file_or_folder_list

Retrieves a list of files or folders from a specified directory based on a filter.

Parameters:

```
folderPath: The directory path from which to list files or folders.
filter: Specifies the type of items to list; "file" for files only, "folder" for folders only, or "both" for all items.
getAbsolutePath: If True, returns absolute paths; if False, returns only the names.
ignorePrefixes: A list of path prefixes to ignore. Any item starting with one of these prefixes won't be included in the result.
ignoreSuffixes: A list of path suffixes to ignore. Any item ending with one of these prefixes won't be included in the result.
```

Returns:

```
list[str]: A list of file or folder paths or names, depending on `getAbsolutePath`, filtered as specified.
```

### search_file_or_folder

Searches for files or folders within a given directory based on a name or pattern.

Parameters:

```
folderPath: The directory path within which to search.
name: The name or wildcard pattern to match against file or folder names. Patterns are Unix shell style:
* matches everything
? matches any single character
[seq] matches any character in seq
[!seq] matches any char not in seq
deepIterate: If True, searches recursively through all subdirectories; if False, searches only in the specified directory.
```

Returns:

```
list[str]: A list of paths to the files or folders that match the specified name or pattern.
```

### zip_create

Create a ZIP file from a file or folder, with optional password protection.

Parameters:

```
srcPath: Path to the file or folder to be zipped.
dstPath: Path where the ZIP file will be saved.
password: Password for the ZIP file, If it's empty string, means have no password.
```

Returns:

```
str: The absolute path to the created ZIP file.
```

### zip_extract

Extract a ZIP file, with optional password protection.

Parameters:

```
zipPath: Path to the ZIP file.
dstFolderPath: Path where the contents will be extracted.
password: Password for the ZIP file, If it's empty string, means have no password.
```

Returns:

```
str: The absolute path to the created ZIP file.
```

### csv_read

Reads a CSV file and returns its contents as a list of lists.

Parameters:

```
filePath: The path to the CSV file.
separator: The character used to separate values.
header: Row number(s) to use as the column names, or None.
indexColumn: Column to set as index; can be column number or name.
encoding: The encoding to use for reading the file.
```

Returns:

```
list[list[Any]]: The contents of the CSV file as a list of rows, where each row is a list of values.
```

### csv_write

Writes a list of lists to a CSV file.

Parameters:

```
listObj: The data to write, as a list of lists.
filePath: The path to the CSV file where data will be saved.
separator: The character used to separate values.
addHeader: Whether to write column names.
addIndexColumn: Whether to write row names (index).
encoding: The encoding to use for writing the file.
overwriteIfExist: If False, raises an error if the file already exists.
```

### ini_read_value

Reads and returns the value of a given option under a specified section in an INI file.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section within the INI file where the option resides.
optionName: The name of the option to read.
encoding: The character encoding of the INI file.
```

Returns:

```
str: The value of the specified option.
```

### ini_write_value

Writes a value to a specific option under a certain section in an INI file.

If the section does not exist, it will be created.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section within the INI file to modify or create.
optionName: The name of the option to modify or create.
optionValue: The value to write to the option.
encoding: The character encoding of the INI file.
```

### ini_get_all_sections

Retrieves a list of all option names within a specific section of an INI file.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section within the INI file.
encoding: The character encoding of the INI file.
```

Returns:

```
list[str]: A list of option names within the specified section.
```

### ini_get_all_options

Deletes a specific section from an INI file.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section to be removed.
encoding: The character encoding of the INI file.
```

### ini_delete_section

Deletes a specific section from an INI file.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section to be removed.
encoding: The character encoding of the INI file.
```

### ini_delete_option

Deletes a specific option from a section in an INI file.

Parameters:

```
filePath: The path to the INI file.
sectionName: The section from which the option will be removed.
optionName: The option to be removed.
encoding: The character encoding of the INI file.
```

### pdf_get_page_count

Returns the total number of pages in a PDF file.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
```

Returns:

```
int: The total number of pages in the PDF.
```

### pdf_save_pages_as_images

Saves specified pages of a PDF file as images in a specified folder.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
saveFolderPath: The directory to save the image files.
startPage: The first page to convert to an image.
endPage: The last page to convert to an image.
scale: Scaling factor to increase resolution.
```

Returns:

```
list[str]: A list of paths to the saved image files.
```

### pdf_extract_images_from_pages

Extracts images from specified pages of a PDF and saves them in a specified format and folder.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
saveFolderPath: The directory to save the extracted images.
format: The image format for saving extracted images. Can be 'png', 'jpg', 'jpeg', or 'bmp'.
startPage: The first page to extract images from.
endPage: The last page to extract images from.
```

Returns:

```
list[str]: A list of paths to the extracted image files.
```

### pdf_extract_text_from_pages

Extracts text from specified pages of a PDF file.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
startPage: The first page to extract text from.
endPage: The last page to extract text from.
```

Returns:

```
str: The extracted text from specified pages.
```

### pdf_extract_all_images

Extracts images in a PDF and saves them in a specified format and folder.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
saveFolderPath: The directory to save the extracted images.
format: The image format for saving extracted images. Can be 'png', 'jpg', 'jpeg', or 'bmp'.
```

Returns:

```
list[str]: A list of paths to the extracted image files.
```

### pdf_extract_all_text

Extracts all text in a PDF.

Parameters:

```
filePath: The path to the PDF file.
password: The password for the PDF file if it is encrypted. If it's empty string, means have no password.
```

Returns:

```
str: The text in the PDF file.
```

### pdf_merge

Merges multiple PDF files into a single PDF file and saves it to a specified path.

Parameters:

```
listFilePath: A list of paths to the PDF files to be merged.
savePath: The path to save the merged PDF file.
```

Returns:

```
str: The absolute path to the saved merged PDF file.
```

## OCR

### get_text_with_position

Perform OCR on an image and returns text blocks with their positions.
Note that it bases on EasyOCR, calculate by CPU in local machine, so the handle time will increase significantly with image's size.
The first run will take some time to initialize.

min_size, low_text, mag_ratio,add_margin are most useful generally.
If you don't know the arguments' meaning, refer to [EasyOCR api](https://www.jaided.ai/easyocr/documentation/)

The default model "english_default" is actually "english_g2" of EasyOCR. You can add your custom model into the path 'LiberRPA/envs/ocr', put the .pth file in 'model', the .yaml and .py file in '/model/CustomModel', then add the information into 'ocr.jsonc'. Restart LiberRPA Local Server, it will load the model automatically.

Parameters:

```
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
```

Returns:

```
list[DictTextBlock]: A list of dictionaries containing the detected text and their positions: {'text': <class 'str'>,
'top_left_x': <class 'int'>,
'top_left_y': <class 'int'>,
'top_right_x': <class 'int'>,
'top_right_y': <class 'int'>,
'bottom_left_x': <class 'int'>,
'bottom_left_y': <class 'int'>,
'bottom_right_x': <class 'int'>,
'bottom_right_y': <class 'int'>}
```

### get_text

Perform OCR on an image and returns the extracted text as a single string.
Note that it bases on EasyOCR, calculate by CPU in local machine, so the handle time will increase significantly with image's size.
The first run will take some time to initialize.

min_size, low_text, mag_ratio,add_margin are most useful generally.
If you don't know the arguments' meaning, refer to [EasyOCR api](https://www.jaided.ai/easyocr/documentation/)

Parameters:

```
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
```

Returns:

```
str: The extracted text as a single string.
```

## Web

### set_cookies

Sets the cookies to be used in subsequent HTTP requests.

Parameters:

```
cookies (dict[str, str]): A dictionary of cookies to set.
```

### set_headers

Sets the headers to be used in subsequent HTTP requests.

Parameters:

```
headers (dict[str, str]): A dictionary of headers to set.
```

### get

Sends an HTTP GET request to the given URL with the specified parameters, headers, and cookies.

Parameters:

```
url: The URL to send the GET request to.
params: The query parameters to include in the request.
timeout: The timeout duration for the request, in seconds.
```

Returns:

```
str: The response body as a string if the request is successful.
```

### post

Sends an HTTP POST request to the given URL with the specified data, JSON, files, and query parameters.

Parameters:

```
url: The URL to send the POST request to.
data: The form data to include in the body of the request. Can be a string, bytes, dictionary, or list of tuples.
json: The JSON data to include in the body of the request.
files: Files to upload via multipart form data. Should be a dictionary where each key is a file field name and the value is a tuple (filename, file-object, file-type).
params: The query parameters to include in the request. Can be a dictionary, list of tuples, string, or bytes.
timeout: The timeout duration for the request, in seconds.
```

Returns:

```
str: The response body as a string if the request is successful.
```

### download_file

Downloads a file from the given URL and saves it to the specified folder.

Parameters:

```
url: The URL of the file to download.
folderPath: The directory where the file will be saved.
params: Optional query parameters to include in the request.
timeout: Timeout duration for the request, in seconds.
stream: Whether to stream the download (useful for large files, to avoid excessive memory usage).
overwriteIfExist: If set to True, the destination file will be overwritten if it already exists; if False, a FileExistsError will be raised if the destination file exists.
```

Returns:

```
str: The absolute path of the downloaded file.
```

### upload_file

Send a POST request to the given URL with a file, data, and other optional parameters.

Parameters:

```
url: The URL to send the request to.
filePath: The path to the file to be uploaded.
data: Optional form data to include in the request.
json: Optional JSON data to include in the request body.
params: Optional query parameters to include in the request URL.
timeout: The request timeout duration in seconds.
```

Returns:

```
str: The server's response text.
```

## Mail

### send_by_SMTP

Sends an email via SMTP with optional attachments and HTML content.

Parameters:

```
user: The SMTP username.
password: The SMTP password.
to: Recipient email address or list of addresses.
subject: Email subject.
content: Main email body content. Can be plain text or HTML.
host: SMTP server host.
port: SMTP server port.
attachments: File path or list of file paths to be attached.
cc: Email address or list of addresses for CC.
bcc: Email address or list of addresses for BCC.
bodyFormat: The format of the email body ('text' or 'html').
ssl: Use SSL for the SMTP connection.
encoding: Character encoding for the email.
```

### IMAP_login

Log into an IMAP server and return the IMAP client object.

Parameters:

```
username: The IMAP username.
password: The IMAP password.
host: IMAP server host.
port: IMAP server port.
ssl: Use SSL for the IMAP connection.
```

Returns:

```
IMAPClient: An authenticated IMAP client instance.
```

### get_folder_list

Retrieves a list of all folders from an IMAP server.

Parameters:

```
imapObj: The authenticated IMAP client object.
```

Returns:

```
list[str]: A list of folder names available on the IMAP server.
```

### get_email_list

Retrieve a list of emails from the specified IMAP folder.

Parameters:

```
imapObj: An instance of the IMAPClient connected to the email server.
folder: The name of the folder to fetch emails from.
numToGet: The maximum number of emails to retrieve.
onlyUnread: Whether to retrieve only unread emails.
markAsRead: Whether to mark retrieved emails as read.
charset: The charset to use for the search criteria.
```

Returns:

```
tuple[list[int],list[DictMailInfo],list[MailParser]]:
        A list of unique identifiers (UIDs) of the fetched emails.
        A list of basic information dictionaries for each email, adhering to the DictMailInfo structure.
        A list of MailParser objects representing the fetched emails.
```

### search_email

Search for emails in the specified folder based on given criteria.

Parameters:

```
imapObj: An instance of the IMAPClient connected to the email server.
folder: The name of the folder to search.
criteria: The search criteria in IMAP format.
charset: The charset to use for the search criteria.
```

Returns:

```
tuple[list[int],list[DictMailInfo],list[MailParser]]:
        A list of unique identifiers (UIDs) of the fetched emails.
        A list of basic information dictionaries for each email, adhering to the DictMailInfo structure.
        A list of MailParser objects representing the fetched emails.
```

### move_email

Move an email by its uid.

Parameters:

```
imapObj: An instance of the IMAPClient connected to the email server.
uid: The unique identifiers (UIDs) of the fetched emails.
folder: The name of the folder to move.
```

### download_attachments

Download all attachments of an email.

Parameters:

```
emailObj: A MailParser objects.
downloadPath: The folder to save download files.
```

Returns:

```
list[str]: A list contains the path of all attachments.
```

## FTP

### build FTP connection

It's an alias of ftputil.FTPHost, so you can search how to use ftputil.FTPHost.

### create_folder

Creates a folder on the FTP server at the specified path.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
folderPath: The path where the folder will be created.
```

### get_folder_list

Retrieves a list of folders from the specified path on the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
folderPath: The path from which to list the folders.
```

Returns:

```
list[str]: A list of absolute folder paths.
```

### get_file_list

Retrieves a list of files from the specified path on the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
folderPath: The path from which to list the files.
```

Returns:

```
list[str]: A list of absolute file paths.
```

### check_folder_exists

Checks if a folder exists on the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
folderPath: The path to check for existence.
```

Returns:

```
bool: True if the folder exists, False otherwise.
```

### check_file_exists

Checks if a file exists on the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
filePath: The path to check for existence.
```

Returns:

```
bool: True if the file exists, False otherwise.
```

### download_file

Downloads a file from the FTP server to the local machine.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
remoteFilePath: The path of the file on the FTP server.
localFilePath: The path where the file will be saved locally.
overwriteIfExist: If True, allows overwriting an existing file.
```

### download_folder

Downloads a folder from the FTP server to the local machine.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
remoteFolderPath: The path of the folder on the FTP server.
localFolderPath: The path where the folder will be saved locally.
overwriteIfExist: If True, allows overwriting existing files.
```

### upload_file

Uploads a file from the local machine to the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
localFilePath: The path of the file on the local machine.
remoteFilePath: The path where the file will be uploaded on the FTP server.
```

### upload_folder

Uploads a local folder and its contents to the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
localFolderPath: The path of the local folder to upload.
remoteFolderPath: The path on the FTP server where the folder will be uploaded.
```

### delete_file

Deletes a file from the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
remoteFilePath: The path of the file on the FTP server to be deleted.
```

### delete_folder

Deletes a folder and its contents from the FTP server.

Parameters:

```
ftpObj: The FTPHost object for making FTP connections.
remoteFolderPath: The path of the folder on the FTP server to be deleted.
```

## Clipboard

### get_text

Retrieves text from the clipboard.

Returns:

```
str: The text currently stored in the clipboard.
```

### set_text

Places a string into the clipboard, making it the current clipboard text.

Parameters:

```
text: The string to be set to the clipboard.
```

### save_image

Saves an image from the clipboard to a specified path.

If there are multiple or no images, it throws an exception.

Parameters:

```
savePath: The file path where the image should be saved.
```

### set_image

Places an image from a specified file into the clipboard.

Parameters:

```
imagePath: The path to the image file to be set to the clipboard.
```

## System

### play_sound

Plays a sound file specified by the soundPath parameter using the Windows Sound API.
Only support waveform audio files (WAV).

### get_environment_variable

No need for description.

### set_environment_variable_temporarily

It only affects the environment variables of the current process (and any child processes spawned by it after the variable is set).

It does not change the environment variables system-wide or for other processes running.

### get_user_home_folder_path

No need for description.

### get_user_temp_folder_path

No need for description.

### get_windows_product_id

Unique to each Windows installation but can change with major system updates or reinstallation.

Returns:

```
str: The product id.
```

### exit

No need for description.

## Credential

### get_windows_credential

Reads a credential from the Windows Credential Manager.

Parameters:

```
credentialType: The type of the credential to be read.
targetName: The name used to identify the credential.
```

Returns:

```
DictCredential: A dictionary containing the 'username' and 'password' from the credential.
```

### write_windows_credential

Writes a credential to the Windows Credential Manager.

Parameters:

```
credentialType: The type of the credential to be stored. Options:
    'GENERIC': General-purpose credentials (most common).
    'DOMAIN_PASSWORD': Standard domain password (used for domain authentication).
    'DOMAIN_CERTIFICATE': Credentials backed by a certificate.
    'DOMAIN_VISIBLE_PASSWORD': A domain password that is visible and retrievable.
targetName: The name used to identify the credential.
userName: The username associated with the credential.
credentialBlob: The secret (password or data) to be stored.
persist: Determines how long the credential persists. Options:
    'SESSION': The credential persists for the current logon session only.
    'LOCAL_MACHINE': The credential persists on the local machine (default).
    'ENTERPRISE': The credential persists across the enterprise (domain-wide persistence).
```

### delete_windows_credential

Delete a credential from the Windows Credential Manager.

Parameters:

```
credentialType: The type of the credential to be deleted.
targetName: The name used to identify the credential.
```

## ScreenPrint

### create_area

Creates and displays a floating text display area.

Parameters:

```
x: The x-coordinate of the top-left corner of the window.
y: The y-coordinate of the top-left corner of the window.
width: The width of the window.
height: The height of the window.
fontFamily: The font family for displaying text.
fontSize: The font size of the text.
fontColor: The text color. Must be one of ["red", "green", "blue", "yellow", "purple", "pink", "black"].
```

Returns:

```
ScreenPrintObj: An instance of the floating text display window.
```

### display_text

Displays the specified text in the floating text display area.

Parameters:

```
screenPrintObj: The ScreenPrintObj instance where the text will be displayed.
text: The text to display.
```

### clean_text

Clears all text from the floating text display area.

Parameters:

```
screenPrintObj: The ScreenPrintObj instance to be cleared.
```

### close_area

Closes the floating text display window.

Parameters:

```
screenPrintObj: The ScreenPrintObj instance to be closed.
```

## Dialog

### show_notification

Show a notification on at bottom-right of the primary screen.

Parameters:

```
title: The notification's title.
message: The notification's content. If it's too long, some text may be invisible.
duration: Duration to show the notification (seconds).
wait: Whether to wait the notification disappear.
```

### open_file

Opens a file dialog to select a file.
A Value Error will be raised if no file selected.

Parameters:

```
folder: The directory that the dialog opens in. If None, defaults to the current working directory.
title: The title of the dialog window.
filetypes: A list of tuples defining the file types to display.

    Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.
```

Returns:

```
str: The file path selected by the user. Returns an empty string if the dialog is cancelled.
```

### open_files

Open a file dialog to select files.
A Value Error will be raised if no files selected.

Parameters:

```
folder: The directory that the dialog opens in. If None, defaults to the current working directory.
title: The title of the dialog window.
filetypes: A list of tuples defining the file types to display.

    Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.
```

Returns:

```
list[str]: The files' paths selected by the user. Returns an empty list if the dialog is cancelled.
```

### save_as

Open a file dialog to save file. It just return the save path string, then you should use other logic to save a file by the path.
A Value Error will be raised if no file name specified.

Parameters:

```
folder: The directory that the dialog opens in. If None, defaults to the current working directory.
title: The title of the dialog window.
filetypes: A list of tuples defining the file types to display.

    Each tuple contains a descriptive string and a file pattern, e.g., ("Text Files", "*.txt") where "Text Files" is the option's name, and "*.txt" filters all .txt files.
```

Returns:

```
str: The file path selected by the user. Returns an empty string if the dialog is cancelled.
```

### show_text_input_box

Displays a dialog box that prompts the user to enter text.
A Value Error will be raised if no text input.

Parameters:

```
title: The title of the dialog box.
prompt: The text prompt displayed within the dialog box.
initialvalue: The initial placeholder text within the input field.
```

Returns:

```
str | None: The text entered by the user, or None if the dialog is closed without an entry.
```

### show_message_box

Shows a message box with specified title, message, icon, and button type.

The function displays a message box and returns the user's response.

The 'type' parameter changes the icon shown in the message box.

The 'infoButton' parameter only has an effect when 'type' is 'info'; it changes the set of buttons available.

Parameters:

```
title: The title of the dialog window.
message: The main content of the dialog window.
type: The icon type of the message box, one of ['info', 'warning', 'error', 'question'].
infoButton: The button type when 'type' is 'info', one of ['ok', 'okcancel', 'yesno', 'retrycancel'].
```

Returns:

```
"ok"|"yes"|"no"|True|False:
        For button types like 'okcancel', 'yesno', 'retrycancel', indicating the user's choice, it will return bool;
        For the 'ok' button type, and for 'question' with responses like "yes" or "no", it will return str.
```