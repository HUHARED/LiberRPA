# LiberRPA Console HTTP API

Use the Console HTTP API to start automation from another application, follow its results, and work with shared Assets, Data Queues, and Shared Files.

The public service is available at `https://console.liberrpa.com`. For your own deployment, replace this address with your Console URL.

For automation running in LiberRPA Editor or Executor, the [`liberrpa.Console` module](../docs/Reference.md#console) provides functions that use your current Console sign-in. This guide describes direct HTTP requests authenticated with an API Key.

- [Connect to Console](#connect-to-console)
- [Check access](#check-access)
- [Start and manage Jobs](#start-and-manage-jobs)
- [Read Run results](#read-run-results)
- [Assets](#assets)
- [Data Queues](#data-queues)
- [Shared Files](#shared-files)
- [Errors and retries](#errors-and-retries)

## Connect to Console

Open `API Keys` in Console and create a key. Give it a useful name, and choose its expiry time. Copy the key when it is created; Console shows the full value once.

Send the key in every request:

```http
Authorization: Bearer liberrpa_api_xxxxxxxxxxxx
```

The key acts as its owner with `Operator` access in the departments that account can currently use. Changes to the account's access also affect the key. Keys created by an `OrgAdmin` still use the API's `Operator` actions. Manage members, departments, Packages, Asset definitions, and Data Queue definitions in Console.

It is recommended to keep your API Key out of source files and use an environment variable or another private configuration source. Avoid including a real key in shared examples or logs. The examples below use the `LIBERRPA_API_KEY` environment variable.

### Request conventions

- Use the exact method and path shown below, including the final `/`.
- JSON requests use `Content-Type: application/json`. `Web.post(..., json=...)` sets this header for you.
- Use JSON numbers and booleans rather than strings such as `"3"` and `"true"`. Unknown request fields are rejected.
- Job creation, Asset, Data Queue, and Shared File JSON bodies are limited to 2 MiB. Individual values and stored resources have additional limits.
- IDs are UUID strings. Resource paths identify departments and resource names, such as `/General/ApiTests/DispatchLabel`; they do not include the organization name. Use the paths shown in Console. Name matching is case-insensitive.
- Date-time values use ISO 8601. Include `Z` or a UTC offset when supplying a date and time.
- Paginated lists return `page`, `page_size`, `total_count`, and `total_pages`. Pages start at `1`; use the returned values when requesting more pages.
- Shared JSON values support up to 64 levels of nesting. Integers must be between `-9007199254740991` and `9007199254740991`; numbers must be finite.

### First request with liberrpa.Web

Run this in the LiberRPA Python environment. For the Asset example, use the path of an existing ordinary Asset:

```python
import json
import os

from requests import HTTPError

from liberrpa import Web

console_url = os.environ.get(
    "LIBERRPA_CONSOLE_URL", "https://console.liberrpa.com"
).rstrip("/")

Web.set_headers({"Authorization": f"Bearer {os.environ['LIBERRPA_API_KEY']}"})

try:
    access = json.loads(Web.get(url=f"{console_url}/api/v1/access/"))
    print(access["organization"]["name"])

    result = json.loads(
        Web.post(
            url=f"{console_url}/api/v1/assets/get_value/",
            json={"path": "/General/ApiTests/DispatchLabel"},
        )
    )
    print(result["value"])
except HTTPError as e:
    response = e.response
    if response is not None:
        print(response.text)
    raise
```

`Web.get` and `Web.post` return the response body as text. Use `json.loads` to read a JSON response.

For HTTP errors, `response.text` shows Console's explanation, including any field errors. The example prints that response, then uses `raise` to stop execution. Connection failures and timeouts raise other exceptions and are not caught by this `HTTPError` handler. See [Errors and retries](#errors-and-retries) for status codes and retry guidance.

## Check access

`GET /api/v1/access/`

Send no query parameters. A successful response contains:

```json
{
  "api_key": {
    "id": "9b4af2e7-76cc-4343-9119-f8060fc80e47",
    "expires_at": "2027-01-31T23:59:59Z"
  },
  "user_id": "9626dd11-596f-4680-a35b-f4d453b0e591",
  "organization": {
    "id": "11e7124f-4e24-410e-bd1f-5943535dd89d",
    "name": "Harbor Services"
  },
  "role": "operator",
  "departments": [
    {
      "id": "7e039d13-3c86-4b52-8a67-d3ffb0db967f",
      "name": "ApiTests",
      "path": "General/ApiTests",
      "role": "operator"
    }
  ]
}
```

The IDs above are examples. Use this endpoint to confirm the account, organization, expiry time, and current department access before testing writes.

The returned department `path` has no leading `/`. For a resource request, use the full path with its resource name, such as `/General/ApiTests/DispatchLabel`.

## Start and manage Jobs

A Job represents a request to execute a Package. A Run represents one execution attempt. A Job may have more than one Run when retries are enabled.

### Start a Package

`POST /api/jobs/`

| Field            | Required               | Meaning                                                                                                                                     |
| ---------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `request_id`   | Yes                    | A UUID for one execution request. Keep it unchanged if you resend that request after a timeout; use a new UUID for a new execution request. |
| `package_id`   | Yes                    | The Package to run.                                                                                                                         |
| `executor_ids` | Choose one target form | A list of one or more unique Executor IDs. Creates one Job per Executor.                                                                    |
| `group_id`     | Choose one target form | One Executor Group ID. Creates one Job for an eligible group member.                                                                        |
| `custom_args`  | No                     | An object containing the input names and JSON values to override.                                                                           |
| `settings`     | No                     | An object containing run settings to override for this request.                                                                             |

Choose `executor_ids` or `group_id`. The Package and targets must belong to the same department. Selected Executors must be online, associated, and accepting `Console Dispatch`. For a group, at least one eligible member must be available.

Copy a Package or target UUID from its details page URL in Console:

| Object | Details page URL path |
| --- | --- |
| Package | `/packages/{package_id}` |
| Executor | `/executors/{executor_id}` |
| Executor Group | `/executors/groups/{group_id}` |
| Job | `/jobs/{job_id}` |
| Run | `/runs/{run_id}` |

Job and Run IDs are also returned in API responses, so your application can keep them for later requests.

```json
{
  "request_id": "d17d4da9-5cf5-4c6d-b92e-b639a0cd7749",
  "package_id": "0cda3af5-1834-4beb-b32e-19a4ac87a54b",
  "executor_ids": ["2e3e69ac-ceea-45bd-b00f-76de2e15ede8"],
  "custom_args": {
    "DispatchDate": "2026-10-31"
  },
  "settings": {
    "priority": "normal",
    "max_retry_count": 0
  }
}
```

An input must be enabled in the Package's `API Input Keys` before it can appear in `custom_args`. Other Custom Arguments keep their saved settings. An API value replaces the Asset binding for that argument for this request. The resulting Custom Arguments remain subject to the shared limit of 100 entries and 64 KiB of JSON.

For an Executor Group, replace `executor_ids` with:

```json
{"group_id": "5f877fec-5c52-41ef-afee-0d6db9075400"}
```

Success returns HTTP `201` with `request_id`, `job_request_id`, and a `jobs` array. Each Job includes its `id`, `state`, target, and other fields described below. This confirms acceptance; follow the Job to learn whether execution succeeds.

For example, Console may create the Jobs but your connection may time out before you receive the response. Send the same `request_id` and unchanged request body again. While Console still has the original request record, it returns HTTP `200` with the existing Jobs instead of creating duplicates. If the first request never arrived, it creates the Jobs normally.

Use a new `request_id` when you intend to start new work, even if the other inputs are identical. Reusing an ID with different content returns `request_conflict`. Resending an HTTP request is separate from retrying a failed Run.

### Run setting overrides

Omitted settings use the Package's saved values. These settings apply to this request:

| Field                     | Values                                                                     |
| ------------------------- | -------------------------------------------------------------------------- |
| `max_retry_count`       | Integer from `0` to `3`.                                               |
| `timeout_min`           | Integer from `0` to `35791`; `0` disables the time limit.            |
| `builtin_log_level`     | `VERBOSE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `builtin_record_video`  | Boolean.                                                                   |
| `builtin_stop_shortcut` | Boolean.                                                                   |
| `builtin_highlight_ui`  | Boolean.                                                                   |
| `run_conflict_policy`   | `skip`, `wait`, or `concurrent`.                                     |
| `priority`              | `high`, `normal`, or `low`.                                          |
| `run_email`             | Email settings described below.                                            |

Supply API inputs through `custom_args`. The API rejects `settings.custom_prj_args` and `settings.custom_arg_assets`.

You can save the recipients and email templates in the Package's `Settings` in Console, then omit `run_email` from the API request to use those saved values.

To override them for this request, supply the desired complete `run_email` configuration. It contains `recipient_ids` (up to five existing Run Email Recipient IDs) and `on_start`, `on_completed`, and `on_error`. Each event is an object with `enabled`, `subject`, and `body`:

```json
{
  "recipient_ids": [],
  "on_start": {"enabled": false, "subject": "", "body": ""},
  "on_completed": {"enabled": false, "subject": "", "body": ""},
  "on_error": {"enabled": false, "subject": "", "body": ""}
}
```

Each entry in `recipient_ids` is the UUID of a Run Email Recipient record. Both member addresses and verified external addresses use this format, such as `44ba0bda-86ed-4f2c-814c-c46bba254f64`. It is not a member's user ID. Email addresses cannot be used directly in `recipient_ids`.

To copy a recipient ID, open `Organization Settings` > `Run Email Recipients` in Console and use the copy button in the `Recipient ID` column. Job and Run details also return `run_email_recipients`, containing the IDs and email addresses selected for that Job.

See the [Console guide](./README.md#organization-settings) for recipient setup and email templates.

### List and inspect Jobs

| Method and path             | Result                                                                |
| --------------------------- | --------------------------------------------------------------------- |
| `GET /api/jobs/`          | A paginated `jobs` array. Defaults to active Jobs.                  |
| `GET /api/jobs/{job_id}/` | A `job` object, including its Runs, events, and saved run settings. |

List filters are query parameters:

| Parameter         | Meaning                                                                                             |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| `page`          | Page number; defaults to `1`.                                                                     |
| `department_id` | Department UUID. Repeat to select several departments.                                              |
| `project_name`  | Match part of the Project name.                                                                     |
| `schedule_name` | Match part of the Schedule name.                                                                    |
| `executor_id`   | Match a directly targeted Executor. Group targets are separate from this filter.                    |
| `state`         | Job state. Repeat to select several active states. Use `finished` by itself to see finished Jobs. |

Job states are `waiting`, `preparing`, `starting`, `running`, `stopping`, `waiting_retry`, `needs_review`, and `finished`.

Useful Job fields include:

- Identity: `id`, `job_request_id`, `department_id`, `package_id`, `project_name`, and `project_version`.
- Source: `source` (`manual`, `api`, or `schedule`), `schedule_id`, `schedule_name`, and `scheduled_at`.
- Target: `target_type` (`executor` or `group`), `target_id`, `target_name`, and the currently assigned `executor_id` and `executor_name` when present.
- Progress: `state`, `reason`, `priority`, `queued_at`, `retry_at`, `stop_requested_at`, `closed_at`, and `ended_at`.
- Available controls: `can_cancel`, `can_stop`, and `can_close`.

The details response also includes `runs`, `events`, `run_snapshot`, and `run_email_recipients`. Use each Run's `status` to read its outcome; `finished` is a Job state, not a successful Run result.

### Cancel, stop, or close a Job

`POST /api/jobs/{job_id}/control/`

```json
{"action": "cancel"}
```

| `action` | Use                                                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------- |
| `cancel` | Cancel queued work or remaining retries.                                                                            |
| `stop`   | Request that active execution stop.                                                                                 |
| `close`  | Close a Job in `needs_review` after checking its Executor. Closing does not confirm that its process has stopped. |

Check `can_cancel`, `can_stop`, or `can_close` before offering the action. The response contains the updated `job`. Follow its state after requesting a stop.

## Read Run results

| Method and path                   | Result                                                                  |
| --------------------------------- | ----------------------------------------------------------------------- |
| `GET /api/runs/`                | A paginated `runs` array.                                             |
| `GET /api/runs/{run_id}/`       | A `run` object with outputs, execution details, and its Job.          |
| `POST /api/runs/{run_id}/stop/` | Request a stop; send `{}`. Returns the updated `run`.               |
| `GET /api/runs/{run_id}/rerun/` | Target and Package information for submitting a new Job.                |
| `GET /api/runs/current/`        | A paginated list of current Runs and `updated_at`.                    |
| `GET /api/runs/statistics/`     | Result counts and execution durations for a date range.                 |
| `GET /api/runs/departments/`    | A `departments` array for filtering accessible history.               |
| `GET /api/runs/selection/`      | A `run_ids` array matching the Run history filters, up to 20,000 IDs. |

### Run history and outputs

`GET /api/runs/` accepts `page`, `department_id`, `project_name`, `schedule_name`, and `executor_id`. Repeat `department_id` or `status` to match several values. The additional filters are:

| Parameter         | Meaning                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------- |
| `status`        | `running`, `completed`, `error`, `canceled`, `timed_out`, or `interrupted`. |
| `started_from`  | Include Runs started at or after this ISO date-time.                                    |
| `started_until` | Include Runs started before this ISO date-time.                                         |

`GET /api/runs/selection/` uses these history filters without pagination.

Each Run includes `id`, `job_id`, `department_id`, `project_name`, `project_version`, `schedule_name`, `executor_id`, `executor_name`, `account_name`, `computer_name`, `attempt_number`, `started_at`, `ended_at`, `status`, and `reason`. It also includes `outputs_status`, `stop_requested`, `can_rerun`, and `can_stop`.

The details response adds `outputs`, `outputs_reason`, `outputs_unavailable_keys`, `error_summary`, `job`, and `other_runs`, along with the department, run settings, email recipients, and file availability. `outputs` is a list of name/value pairs, or `null` when unavailable:

```json
{
  "outputs_status": "complete",
  "outputs": [
    ["ProcessedCount", 12],
    ["ReportPath", "/General/DispatchReport.csv"]
  ],
  "outputs_reason": "",
  "outputs_unavailable_keys": []
}
```

This is an excerpt of the Run details. `outputs_status` may be `waiting`, `complete`, `partial`, or `unavailable`. For `partial`, inspect `outputs_unavailable_keys`. `ended_at` can be `null` when the exact end time is unknown. Review the recorded `status` and `reason` as well as the time.

To run again, read `/api/runs/{run_id}/rerun/`. It returns `package_id`, `executor_ids`, `group_id`, and `original_job_active`. The Package is the most recently uploaded version of the same Project in the same department. If `original_job_active` is `true`, check the original Job before creating more work. Review the returned values and submit a new request to `/api/jobs/` with a new `request_id`. Reading rerun options does not start execution.

### Current Runs and statistics

`GET /api/runs/current/` accepts `page`, `project_name`, and repeated `department_id` values. Entries contain `id`, `project_name`, `project_version`, `executor_id`, `executor_name`, and `started_at`.

`GET /api/runs/statistics/` requires `date_from` and `date_until` in `YYYY-MM-DD` format. Both dates are included, with a maximum range of 366 days. Optional filters are `project_name`, repeated `department_id`, and `executor_page`.

Statistics use the account's time zone and include ended Runs with known end times. The response contains `date_from`, `date_until`, `time_zone`, `updated_at`, `total_count`, `total_duration_seconds`, `results`, `daily`, and `executors`. Each `results` array contains `{ "status": "completed", "count": 12 }` entries. `daily` groups those counts by date; `executors` is a paginated `entries` list with each Executor's ID, name, count, duration, and result counts.

The history departments response contains each department's `id`, `name`, `path`, and `deleted_at`. This allows existing history to remain identifiable after a department is deleted.

Use Console's Run details page to read log entries and download Run files.

## Assets

Create the Asset in Console first. The API reads and changes its current value while keeping its name and type.

| Method and path                    | JSON body                                                                    | Success response                  |
| ---------------------------------- | ---------------------------------------------------------------------------- | --------------------------------- |
| `POST /api/v1/assets/get_value/` | `{"path": "/General/ApiTests/DispatchLabel"}`                              | `{"value": "Morning dispatch"}` |
| `POST /api/v1/assets/set_value/` | `{"path": "/General/ApiTests/DispatchLabel", "value": "Evening dispatch"}` | `{"value": "Evening dispatch"}` |

These requests accept no query parameters. Use the JSON type matching the Asset:

| Asset type  | Example value                                 |
| ----------- | --------------------------------------------- |
| `Text`    | `"Morning dispatch"`                        |
| `Integer` | `3`                                         |
| `Number`  | `0.85`                                      |
| `Boolean` | `true`                                      |
| `JSON`    | `{"region": "North", "priority": "normal"}` |

Asset values are subject to the Console instance's value size limit. A type mismatch is rejected rather than converted.

`Secret Text` and `Credential` values are read through signed-in Editor or Executor sessions using `liberrpa.Console`. API Keys cannot read these values. Requests with an API Key to `/api/v1/assets/get_secret_text/` or `/api/v1/assets/get_credential/` return HTTP `403`; `get_value` and `set_value` reject secret Asset types with `asset_type_mismatch`.

## Data Queues

Create the Data Queue in Console first. Queue items contain JSON data and have two states: `unclaimed` and `claimed`. Claiming an item reserves it for processing; your automation decides when to reset or delete it.

All endpoints below use `POST` with a JSON body and accept no query parameters.

### Query items

`POST /api/v1/data-queues/query/`

| Field              | Required/default | Meaning                                                               |
| ------------------ | ---------------- | --------------------------------------------------------------------- |
| `queue_path`     | Required         | Full Data Queue path.                                                 |
| `status`         | `all`          | `all`, `unclaimed`, or `claimed`.                               |
| `order`          | `oldest_first` | `oldest_first` or `newest_first`.                                 |
| `item_id`        | `null`         | Restrict the query to one item UUID. The status filter still applies. |
| `count`          | `50`           | Maximum number of items, from `1` to `100`.                       |
| `after_sequence` | `null`         | Cursor from the previous response.                                    |

```json
{
  "queue_path": "/General/ApiTests/DispatchRequests",
  "status": "unclaimed",
  "order": "oldest_first",
  "count": 50
}
```

The response contains `items` and `next_after_sequence`. Each item includes `id`, `sequence`, `status`, `data`, `data_summary`, `uploaded_by_id`, `uploaded_by_name`, `uploaded_at`, `last_claimed_by_id`, `last_claimed_by_name`, and `last_claimed_at`.

Pass `next_after_sequence` as `after_sequence` in the next request, keeping the same filters and order. Stop when it is `null`. A response may contain fewer than `count` items to stay within the 2 MiB response limit. Querying leaves item states unchanged.

### Upload, claim, reset, and delete items

Every change request requires `request_id` (a UUID) and `queue_path`. Use a new UUID for each operation. To retry an uncertain request, send the same ID and content again.

| Path                                  | Additional fields                                                              | Result                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| `/api/v1/data-queues/upload/`       | `items`: array of 1–100 JSON values.                                        | Adds `unclaimed` items.                                |
| `/api/v1/data-queues/claim/`        | Optional `status`, `order`, `item_id`, and `count`.                    | Returns selected data and marks those items `claimed`. |
| `/api/v1/data-queues/reset/`        | `item_ids`: array of 1–100 UUIDs.                                           | Changes selected `claimed` items to `unclaimed`.     |
| `/api/v1/data-queues/delete_items/` | `item_ids`, or an explicit `status` and `count` with optional `order`. | Permanently deletes selected items.                      |

Upload example:

```json
{
  "request_id": "34ce973b-285d-4ba2-868d-63e9645e9249",
  "queue_path": "/General/ApiTests/DispatchRequests",
  "items": [
    {"dispatch_id": "HS-20261031-001", "destination": "North Depot"},
    {"dispatch_id": "HS-20261031-002", "destination": "West Depot"}
  ]
}
```

Claim example:

```json
{
  "request_id": "5148b6db-325b-4614-a911-4b6b12093017",
  "queue_path": "/General/ApiTests/DispatchRequests",
  "status": "unclaimed",
  "order": "oldest_first",
  "count": 1
}
```

Claim defaults are `status: "unclaimed"`, `order: "oldest_first"`, and `count: 1`; `count` can be `1`–`100`. Use `unclaimed` for normal work distribution. Selecting `claimed` or `all` can return items that have already been claimed.

To reset or delete specific items, use their returned IDs:

```json
{
  "request_id": "b4f59936-7711-408e-91f6-c67910148ae5",
  "queue_path": "/General/ApiTests/DispatchRequests",
  "item_ids": ["a76f0bed-cb81-4571-862e-5b55b2f06684"]
}
```

For deletion by filter, supply `status` and `count` explicitly. `count` is `1`–`100`; `order` defaults to `oldest_first`. Do not combine `item_ids` with `status`, `count`, or `order`.

All four change endpoints return:

| Field            | Meaning                                                                                                     |
| ---------------- | ----------------------------------------------------------------------------------------------------------- |
| `request_id`   | Your request UUID.                                                                                          |
| `accepted_at`  | When the original operation was accepted.                                                                   |
| `item_ids`     | IDs affected by the operation.                                                                              |
| `missing_ids`  | Requested IDs that were not found. A replayed claim can also report items deleted since the original claim. |
| `skipped_ids`  | Items already `unclaimed` when resetting.                                                                 |
| `items`        | Claim results as `{ "id": "...", "data": ... }`; empty for other operations.                              |
| `deduplicated` | `true` when returning a saved result for a repeated request.                                              |

The same request ID with different content returns `idempotency_conflict`. Saved results are retained for the instance's configured period. Do not reuse old IDs for new work. Item sizes, item counts, and total stored data are subject to the organization's limits.

## Shared Files

Shared File paths combine an existing department path with a filename, such as `/General/ApiTests/DispatchTemplate.csv`.

### List and inspect files

`POST /api/v1/shared-files/list/`

| Field               | Default         | Meaning                                                     |
| ------------------- | --------------- | ----------------------------------------------------------- |
| `department_path` | `null`        | One department, or all accessible departments when omitted. |
| `name`            | `""`          | Match part of a filename.                                   |
| `sort_by`         | `uploaded_at` | `name`, `size`, or `uploaded_at`.                     |
| `order`           | `desc`        | `asc` or `desc`.                                        |
| `page`            | `1`           | Page number.                                                |

The response contains `files`, `department_path`, pagination fields, and `usage`. Usage contains `used_bytes`, `reserved_bytes`, `pending_cleanup_bytes`, `limit_bytes`, and `max_file_bytes`.

`POST /api/v1/shared-files/query/` reads one file's information:

```json
{"path": "/General/ApiTests/DispatchTemplate.csv"}
```

File information is returned directly, without a surrounding `file` key:

```json
{
  "path": "/General/ApiTests/DispatchTemplate.csv",
  "name": "DispatchTemplate.csv",
  "department_path": "/General/ApiTests",
  "size_bytes": 42,
  "sha256": "a1b2c3d4e5f60718a1b2c3d4e5f60718a1b2c3d4e5f60718a1b2c3d4e5f60718",
  "uploaded_by_name": "Harbor Operations",
  "uploaded_at": "2026-10-31T09:00:00Z"
}
```

The hash above is illustrative. Use the actual SHA-256 of the file's bytes when uploading or checking a download.

### Upload a file

An upload has three steps: create an upload, send its bytes, then complete it.

1. `POST /api/v1/shared-files/uploads/` with a JSON body:

   ```json
   {
     "request_id": "c60bf5c7-0678-4dc1-bfe7-580ba56550ba",
     "path": "/General/ApiTests/DispatchTemplate.csv",
     "size_bytes": 42,
     "sha256": "a1b2c3d4e5f60718a1b2c3d4e5f60718a1b2c3d4e5f60718a1b2c3d4e5f60718",
     "overwrite": false
   }
   ```

   `size_bytes` is the total byte count; `sha256` is the lowercase 64-character SHA-256 hash of the whole file. `overwrite` defaults to `false`. Success returns HTTP `201` and an upload response containing `upload_id`, `state`, `offset`, `size_bytes`, `chunk_bytes`, `expires_at`, and `file`.
2. For each chunk, send `PUT /api/v1/shared-files/uploads/{upload_id}/chunks/{offset}/` with the raw bytes. Set `Content-Type: application/octet-stream` and `X-Chunk-SHA256` to the lowercase SHA-256 hash of that chunk. Keep the `Authorization` header.

   Start at the returned `offset`. Send a non-empty chunk no larger than `chunk_bytes` (currently 4 MiB), then use the new `offset` from the response. Continue until it equals `size_bytes`.
3. `POST /api/v1/shared-files/uploads/{upload_id}/complete/` with `{}`. Console checks the complete file and publishes it. The returned upload state is `completed`, with the saved file information in `file`.

For an empty file, use `size_bytes: 0` and the SHA-256 of empty bytes, then go directly to completion.

Upload status and cancellation:

| Method and path                                           | Body   | Result                                                       |
| --------------------------------------------------------- | ------ | ------------------------------------------------------------ |
| `GET /api/v1/shared-files/uploads/{upload_id}/`         | None   | Current upload response, including its confirmed `offset`. |
| `POST /api/v1/shared-files/uploads/{upload_id}/cancel/` | `{}` | Cancels a receiving upload and returns its state.            |

Upload states are `receiving`, `completed`, `failed`, `expired`, and `canceled`. `file` is `null` until completion. Repeating upload creation with the same `request_id` and content returns the same upload. Repeating a confirmed chunk with the same offset, size, and hash is accepted. Repeating completion returns the completed result.

If a chunk request times out, read the upload status before continuing. Resume at its confirmed offset. An expired or failed upload requires a new upload request.

The current `liberrpa.Web` module provides GET and POST requests. Sending non-empty file chunks requires an HTTP client with PUT support. Within a signed-in LiberRPA Project, use `Console.shared_file_upload` to handle the complete upload.

### Download a file

1. `POST /api/v1/shared-files/downloads/` with `{"path": "/General/ApiTests/DispatchTemplate.csv"}`.
2. Read `transfer_id`, `expires_at`, and `file` from the HTTP `201` response.
3. `GET /api/v1/shared-files/downloads/{transfer_id}/` with the same API Key. Save the binary response before the transfer expires.

For example:

```python
transfer = json.loads(
    Web.post(
        url=f"{console_url}/api/v1/shared-files/downloads/",
        json={"path": "/General/ApiTests/DispatchTemplate.csv"},
    )
)
downloaded_path = Web.download_file(
    url=f"{console_url}/api/v1/shared-files/downloads/{transfer['transfer_id']}/",
    folderPath="./Downloads",
    stream=True,
    overwrite=False,
)
```

Each transfer is for one complete download. If it fails after starting, create a new transfer. To cancel a transfer that has not started, send `POST /api/v1/shared-files/downloads/{transfer_id}/cancel/` with `{}`; success returns `{}`.

### Delete files

`POST /api/v1/shared-files/deletion/`

```json
{
  "request_id": "35f26e36-846a-44bd-8918-487e24d23680",
  "paths": ["/General/ApiTests/DispatchTemplate.csv"]
}
```

Supply 1–100 paths. The response contains `request_id`, `deleted_paths`, `missing_paths`, and `deleted_count`. Repeating the same request returns its saved result while that result is retained. Use a fresh request ID to perform a new deletion.

## Errors and retries

API errors normally use this JSON structure:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "One or more request fields are invalid.",
    "fields": {
      "count": ["Input should be less than or equal to 100"]
    }
  }
}
```

`fields` is present when there is field-specific information. Check the HTTP status and `error.code`; use `message` to explain the problem to a person. Some HTTP errors, such as a wrong method or an upstream service failure, may return a non-JSON body.

| HTTP status       | What to check                                                                         |
| ----------------- | ------------------------------------------------------------------------------------- |
| `400`           | Request fields, JSON types, paths, IDs, or an unavailable Job target.                 |
| `401`           | Missing, expired, revoked, or invalid API Key.                                        |
| `403`           | Current account/department access, or an operation unavailable to API Keys.           |
| `404`           | Resource, Job, Run, or transfer unavailable to this account.                          |
| `405`           | Request method.                                                                       |
| `409`           | Conflicting request ID, Asset type, queue capacity, file state, or existing filename. |
| `410`           | Upload or download no longer available.                                               |
| `413`           | Request or file too large.                                                            |
| `415`           | Incorrect `Content-Type`.                                                           |
| `429`           | Request limit reached. Wait for `Retry-After` when present.                         |
| `500` / `503` | Service problem or temporary unavailability.                                          |

Different endpoint groups can use different error codes for similar problems. In particular, Job request conflicts return `400` with `request_conflict`; queue request conflicts return `409` with `idempotency_conflict`.

After a timeout on a change request, the server may already have accepted it. Retry with the original `request_id` and original content where that field is supported. For uploads, use the confirmed offset. For downloads, create a fresh transfer after a started transfer fails. Keep retries bounded and respect `Retry-After`; changing the request ID on every retry can create duplicate work.

Return to the [Console guide](./README.md).
