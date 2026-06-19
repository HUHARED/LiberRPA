// FileName: utils.ts

export type ExecuteMode = "Run" | "Debug";

export type WebviewToExtensionMessage =
  | { command: "ready" }
  | { command: "update"; data: string }
  | { command: "open"; path: string }
  | { command: "execute"; data: { pyFile: string; executeMode: ExecuteMode } }
  | { command: "executeProject"; data: { executeMode: ExecuteMode } };

function isExecuteMode(value: unknown): value is ExecuteMode {
  return value === "Run" || value === "Debug";
}

export function isWebviewMessage(value: unknown): value is WebviewToExtensionMessage {
  if (!value || typeof value !== "object") {
    return false;
  }

  const msg = value as Record<string, unknown>;

  if (msg.command === "ready") {
    return true;
  }

  if (msg.command === "update") {
    return typeof msg.data === "string";
  }

  if (msg.command === "open") {
    return typeof msg.path === "string";
  }

  if (msg.command === "execute" || msg.command === "executeProject") {
    const data = msg.data as Record<string, unknown> | undefined;

    if (!data || typeof data !== "object") {
      return false;
    }

    if (msg.command === "execute") {
      return typeof data.pyFile === "string" && isExecuteMode(data.executeMode);
    }

    return isExecuteMode(data.executeMode);
  }

  return false;
}
