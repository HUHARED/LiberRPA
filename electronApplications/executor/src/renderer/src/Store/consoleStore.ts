// FileName: consoleStore.ts

import { defineStore } from "pinia";

import {
  ConsoleConnection,
  type ConsoleSessionInfo,
  type ConsoleAccountState,
} from "../../../shared/consoleAccount";

export const useConsoleStore = defineStore("console", {
  state: () => {
    return {
      account: {
        consoleUrl: "" as string,
        connection: ConsoleConnection.SignedOut as ConsoleConnection,
        sessionInfo: null as ConsoleSessionInfo | null,
        message: "" as string,
        hasCredential: false as boolean,
        hasActiveRun: false as boolean,
        busy: false as boolean,
      },
      boolWorking: false as boolean,
    };
  },
  actions: {
    setAccount(account: ConsoleAccountState): void {
      this.account = account;
    },
  },
});
