// FileName: index.ts

import { app, dialog } from "electron";

import { getErrorDetails } from "../shared/error";

let boolFatalErrorHandled = false;

function handleFatalError(error: unknown): void {
  if (boolFatalErrorHandled) {
    return;
  }
  boolFatalErrorHandled = true;

  const strErrorDetails = getErrorDetails(error);
  console.error(strErrorDetails);

  try {
    dialog.showErrorBox("UI Analyzer failed to start", strErrorDetails);
  } finally {
    app.exit(1);
  }
}

process.on("uncaughtException", handleFatalError);
process.on("unhandledRejection", handleFatalError);

void import("./application")
  .then(({ bootstrapUiAnalyzer }) => bootstrapUiAnalyzer())
  .catch(handleFatalError);
