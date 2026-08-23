import cronstrue from "cronstrue";

import { useInformationStore } from "../Store/informationStore";

export function validateCron(cron: string): boolean {
  const informationStore = useInformationStore();

  try {
    informationStore.information = cronstrue.toString(cron, {
      use24HourTimeFormat: true,
      throwExceptionOnParseError: true,
      verbose: true,
    });
    informationStore.showAlert = false;
    return true;
  } catch (e) {
    informationStore.showAlertMessage(`Cron error: ${String(e)}`);
    return false;
  }
}
