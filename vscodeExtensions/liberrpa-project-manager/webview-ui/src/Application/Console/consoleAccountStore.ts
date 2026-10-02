// FileName: consoleAccountStore.ts

import { defineStore } from "pinia";

import {
  ConsoleAction,
  ConsoleConnection,
  type EditorSessionInfo,
  type ConsoleAccountState,
} from "../../Domain/Console/consoleTypes";

export const useConsoleAccountStore = defineStore("consoleAccount", {
  state: () => {
    return {
      accountState: {
        url: "" as string,
        connection: ConsoleConnection.SignedOut as ConsoleConnection,
        signedIn: false as boolean,
        account: null as EditorSessionInfo | null,
        lastContactAt: null as string | null,
        message: "" as string,
      },
      showAddress: false as boolean,
      showSignIn: false as boolean,
      addressError: "" as string,
      signInError: "" as string,
    };
  },
  actions: {
    load(state: ConsoleAccountState): void {
      this.accountState = state;
    },
    finishAction(action: ConsoleAction, error: string | null): void {
      if (action === ConsoleAction.ChangeAddress) {
        this.addressError = error ?? "";
        this.showAddress = error !== null;
      }
      if (action === ConsoleAction.SignIn) {
        this.signInError = error ?? "";
        this.showSignIn = error !== null;
      }
    },
  },
});
