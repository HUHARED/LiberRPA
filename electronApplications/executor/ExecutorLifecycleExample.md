# Executor Lifecycle Example

[`ExecutorLifecycleExample_1.0.0.rpa.zip`](./Example/ExecutorLifecycleExample_1.0.0.rpa.zip) is a ready-to-install Flow Project Package for learning and testing the common LiberRPA Executor workflow.

The Project opens a blocking text-input dialog. This makes it easy to keep a Run active, cancel it, let a Timeout expire, or observe recovery after an unexpected Executor termination. This walkthrough uses local Packages and Schedules. It is not intended for unattended production use.

> **Note:**
>
> Screenshots and animations in this document are provided for reference. As LiberRPA evolves, the current interface may differ slightly in appearance or wording, but these minor differences do not affect the documented workflow or functionality.

## Contents

- [Before You Start](#before-you-start)
- [Example Behavior](#example-behavior)
- [Install the Package](#install-the-package)
- [Test Run Outcomes](#test-run-outcomes)
- [Create and Edit a Schedule](#create-and-edit-a-schedule)
- [Review the Job Queue and Run History](#review-the-job-queue-and-run-history)
- [Clean Up](#clean-up)

## Before You Start

- Run `InitLiberRPA.exe` for the current LiberRPA installation.
- Ensure LiberRPA Local Server is running; the example uses its blocking dialog service.
- Use the `default` Python Environment unless another compatible environment has been prepared.
- Keep `Max Retry Count` at `0` except during the retry test, so each test produces one attempt.
- Do not perform the optional Interrupted recovery test while other Executor-managed automation is active.

## Example Behavior

| Input or action                                                                  | Project behavior                                                         | Executor result             |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | --------------------------- |
| Leave the input empty                                                            | Follow the `Empty Input` branch and finish normally.                   | `Completed`               |
| Enter ordinary text                                                              | Record the text in the Project log and finish normally.                  | `Completed`               |
| Enter `ERROR`                                                                  | Raise an intentional unhandled exception.                                | `Error`                   |
| Enter `WAIT`                                                                   | Run for about 180 seconds and write a progress message every 10 seconds. | `Completed` if left alone |
| Cancel while the dialog or `WAIT` branch is active                             | Executor terminates the Run at the user's request.                       | `Canceled`                |
| Keep the Run active beyond its configured Timeout                                | Executor terminates the Run because the limit was exceeded.              | `Timed Out`               |
| End Executor unexpectedly while a local Run is active, then start Executor again | Executor recovers the stale Running record during startup.               | `Interrupted`             |

The example does not require Components, external services, or additional resources.

## Install the Package

1. Open LiberRPA Executor.
2. Open `Packages`.
3. Click `Install Package` and select [`ExecutorLifecycleExample_1.0.0.rpa.zip`](./Example/ExecutorLifecycleExample_1.0.0.rpa.zip).
4. Select `ExecutorLifecycleExample` and version `1.0.0` if they are not already selected.
5. Review the `Description`, `Version Summary`, `Python Environment`, run settings, and `Custom Project Arguments`.
   ![1793423500911](./md_images/ExecutorLifecycleExample/1793423500911.png)
6. Keep the `default` Python Environment unless you have prepared another compatible environment. Save any changes.

For each manual test below, click `Run` on the Packages page, review the settings in the dialog, then click `Run` there. Settings changed in the dialog apply only to that run.

![1793423567874](./md_images/ExecutorLifecycleExample/1793423567874.png)

You may see a version compatibility warning when running this example with a newer version of LiberRPA. This example has been tested with `LiberRPA 0.4.0` and works correctly.

![1793423632760](./md_images/ExecutorLifecycleExample/1793423632760.png)

## Test Run Outcomes

### Complete a Normal Run

1. In `Packages`, open the `Run` dialog. Keep `Timeout (min)` set to `0` and click `Run`.
2. Enter ordinary text in the dialog and confirm it.
3. Open `Run History`.
   ![1793424151898](./md_images/ExecutorLifecycleExample/1793424151898.png)
4. Confirm that the status becomes `Completed`.
5. Click `Open Log Folder` in the `Actions` column and inspect the Project log.
   ![1793424191254](./md_images/ExecutorLifecycleExample/1793424191254.png)

Use `View Run Details > Outputs` to see the final `inputText` value.

![1793424224575](./md_images/ExecutorLifecycleExample/1793424224575.png)

![1793424249740](./md_images/ExecutorLifecycleExample/1793424249740.png)

### Produce an Error

1. Click `Run`.
2. Enter:

```text
ERROR
```

![1787987259165](./md_images/ExecutorLifecycleExample/1787987259165.png)

3. Open `Run History` and confirm that the status becomes `Error`.
   ![1787987293710](./md_images/ExecutorLifecycleExample/1787987293710.png)
4. Open the Run log folder and review the intentional exception.

### Cancel a Run

1. Click `Run`.
2. Keep the Project active by either:

   - leaving the input dialog open; or
   - entering `WAIT`, which runs for about 180 seconds.

   ![1787987358725](./md_images/ExecutorLifecycleExample/1787987358725.png)
3. While the status is `Running`, click `Stop Run` in `Run History`.
   ![1787987387967](./md_images/ExecutorLifecycleExample/1787987387967.png)
4. Confirm that the final status becomes `Canceled`.
   ![1787987455922](./md_images/ExecutorLifecycleExample/1787987455922.png)

### Test a Timeout

1. In `Packages`, set `Timeout (min)` to `1` and click `Save`.
   ![1793424456496](./md_images/ExecutorLifecycleExample/1793424456496.png)
2. Click `Run`.
3. Leave the input dialog open or enter `WAIT` so that the Project remains active longer than one minute.
4. Confirm that `Run History` shows `Timed Out` after the limit expires.
   ![1787989141380](./md_images/ExecutorLifecycleExample/1787989141380.png)
5. Set `Timeout (min)` back to `0` and click `Save` after the test.

### Test a Retry (Optional)

1. Open the `Run` dialog. Set `Max Retry Count` to `1` and `Timeout (min)` to `0`, then click `Run`.
   ![1793424626554](./md_images/ExecutorLifecycleExample/1793424626554.png)
2. Enter `ERROR` in the example dialog.
3. Open `Job Queue` and look for `Waiting for Retry` under `Current Jobs`.
   ![1793424681577](./md_images/ExecutorLifecycleExample/1793424681577.png)
4. After about one minute, the example dialog opens again. Enter ordinary text so the retry completes.
   ![1793424743350](./md_images/ExecutorLifecycleExample/1793424743350.png)
5. In `Run History`, check the two attempts: the first is `Error`, and the second is `Completed`.
   ![1793424772494](./md_images/ExecutorLifecycleExample/1793424772494.png)

To skip the second attempt, use `Cancel Retries` while it is waiting. A timeout can also trigger a retry.

![1793424822930](./md_images/ExecutorLifecycleExample/1793424822930.png)

### Test Interrupted Recovery (Optional)

Run this test only when no other Executor-managed automation is active.

1. Keep `Timeout (min)` at `0`.
2. Click `Run`, enter `WAIT`, and confirm that `Run History` shows `Running`.
3. End `Executor.exe` through Windows Task Manager. Do not use the tray `Exit` action, because normal shutdown finalizes the Run as `Canceled`.
4. Start Executor again.
5. Confirm that the previous Run is now `Interrupted` and its Ended time is `Unknown`.
   ![1793425426287](./md_images/ExecutorLifecycleExample/1793425426287.png)

The example's `WAIT` branch finishes by itself after about 180 seconds. If its Python process remains active after the forced Executor exit, wait for it to finish before continuing with other tests. This procedure demonstrates recovery of Executor's local Run History record; it is not a normal shutdown method. Console Runs have a separate recovery process; see [Unexpected Termination](./README.md#unexpected-executor-termination).

## Create and Edit a Schedule

### Create a Simple Schedule

1. Open `Schedules` and click `New Schedule`.
   ![1793425878184](./md_images/ExecutorLifecycleExample/1793425878184.png)
2. Enter a unique Schedule name, for example:

```text
Executor Lifecycle Example
```

3. Select `ExecutorLifecycleExample` and version `1.0.0`.
4. Keep `Conflict Policy` set to `Skip This Run` for this first walkthrough.
5. Set `Active From`, `Active Until`, and a Cron Expression that will trigger soon. For a simple test, `* * * * *` triggers once per minute at second `0`. Keep `Active Until` close enough to the test period to avoid repeated dialogs after you finish.
6. Keep `Max Retry Count` at `0` and `Enabled` on, then click `Save`.
   ![1793425984293](./md_images/ExecutorLifecycleExample/1793425984293.png)
7. Open `Job Queue` and find the next trigger under `Upcoming Triggers`.
   ![1793426110992](./md_images/ExecutorLifecycleExample/1793426110992.png)

When the Schedule triggers, the example dialog appears. Enter ordinary text to let the scheduled Run complete. The Schedule name is stored in `Run History`.

![1793426162920](./md_images/ExecutorLifecycleExample/1793426162920.png)

Because this example is interactive, it demonstrates Schedule mechanics rather than a fully unattended automation. See the main [Executor README](./README.md#schedules) for the complete Schedule behavior, including Cron expression formats, Time Zone handling, and the Skip, Wait, and Concurrent policies.

### Observe a Waiting Run (Optional)

1. Edit the Schedule and change `Conflict Policy` to `Wait`.
2. Configure the next trigger to occur soon and save the Schedule.
3. Start a manual Run and enter `WAIT` before the Schedule triggers.
4. When the trigger occurs, open `Job Queue` and confirm that a `Waiting` item appears under `Current Jobs`. Disable the Schedule to prevent more test triggers; the existing waiting item stays in the queue.
5. Either:
   - click `Cancel`; or
   - let the active Run finish, then complete the dialog that appears when the Waiting Run starts.

This demonstrates that a waiting Job keeps the Project version, Python Environment, run settings, and Custom Arguments from the trigger time. Editing or disabling its Schedule does not change those settings or remove the Job.

### Edit the Schedule

1. Open `Schedules`.
2. Find `Executor Lifecycle Example` and click the `Edit Schedule` pencil icon in the `Actions` column.
   ![1793426348517](./md_images/ExecutorLifecycleExample/1793426348517.png)
3. Change a setting such as the Cron Expression, active period, Enabled state, conflict policy, or run settings.
4. Click `Save`.
5. Confirm that the Schedule list reflects the saved settings. If the Schedule remains enabled, `Job Queue` shows its recalculated next trigger.

## Review the Job Queue and Run History

Use `Job Queue` to inspect current Jobs and future triggers:

- `Current Jobs` shows active Runs, waiting work, and pending retries;
- `Upcoming Triggers` shows the next calculated future trigger for each enabled local Schedule.

In `Run History`:

* type in the filter row below `Schedule`, `Project Name`, or `Project Version`, or select a `Status` or `Source`;
  ![1793426423793](./md_images/ExecutorLifecycleExample/1793426423793.png)
* click a sortable column heading to change the sort order;
* use the table footer to choose the number of rows per page or move between pages;
* open a Run log folder;
* use `View Run Details` to inspect `Inputs` and `Outputs`;
* stop a Running Run;
* run the most recently installed version of the same Project again, for an ended local Run with a confirmed end time. Review the settings in the dialog before starting it.

  ![1787989882062](./md_images/ExecutorLifecycleExample/1787989882062.png)

## Clean Up

Delete the example Schedule before deleting the installed Project version. Executor prevents Package deletion while a Schedule uses it or while one of its Jobs is starting, running, waiting, or waiting for a retry.

![1787989938313](./md_images/ExecutorLifecycleExample/1787989938313.png)

To delete the Schedule:

1. Open `Schedules`.
2. Find `Executor Lifecycle Example` and click the `Delete Schedule` trash-can icon in the `Actions` column.
   ![1793442771078](./md_images/ExecutorLifecycleExample/1793442771078.png)
3. Review the confirmation dialog and click `Delete`.
   ![1787991748386](./md_images/ExecutorLifecycleExample/1787991748386.png)
4. Confirm that the Schedule disappears from the list. Its future trigger is removed.
   ![1793426659486](./md_images/ExecutorLifecycleExample/1793426659486.png)
5. Open `Job Queue`. Cancel any waiting work or pending retries from the example, and stop any active example Run. Deleting the Schedule does not remove these items.
   ![1793426634411](./md_images/ExecutorLifecycleExample/1793426634411.png)

After the Schedule has been removed, delete the installed Project version if it is no longer needed:

1. Return to `Packages` and select `ExecutorLifecycleExample` version `1.0.0`.
2. Click `Delete`, review the confirmation dialog, and confirm the deletion.
   ![1793426687692](./md_images/ExecutorLifecycleExample/1793426687692.png)
3. Confirm that the Project version disappears from `Packages`.

The same Package can be installed again after the existing `ExecutorLifecycleExample` version `1.0.0` has been deleted.
