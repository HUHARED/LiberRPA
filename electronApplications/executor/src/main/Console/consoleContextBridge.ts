// FileName: consoleContextBridge.ts

import { createHash, randomUUID } from "node:crypto";
import { createServer, type Server, type Socket } from "node:net";

export interface ConsoleCredentialSnapshot {
  consoleUrl: string;
  token: string;
}

const STR_CONTEXT_REQUEST_PREFIX = "LIBERRPA_CONSOLE_CONTEXT_V1 ";
const INT_REQUEST_MAX_BYTES = 128;
const INT_SOCKET_TIMEOUT_MS = 3000;

let pipeServer: Server | undefined;
let strPipePath: string | undefined;
const setClientSocket = new Set<Socket>();
let getCurrentCredential: (() => ConsoleCredentialSnapshot | null) | undefined;

function getCredentialIdentity(credential: ConsoleCredentialSnapshot): string {
  // This identifier binds a launch to one credential; it does not authorize requests.
  return createHash("sha256")
    .update(JSON.stringify([credential.consoleUrl, credential.token]))
    .digest("hex");
}

export function getConsoleContextEnvironment(): Record<string, string | undefined> {
  const credentialSnapshot = getCurrentCredential?.() ?? null;
  return {
    LIBERRPA_CONSOLE_PIPE: pipeServer?.listening ? strPipePath : undefined,
    LIBERRPA_CONSOLE_HOST_PID: pipeServer?.listening ? String(process.pid) : undefined,
    LIBERRPA_CONSOLE_CREDENTIAL_ID:
      pipeServer?.listening && credentialSnapshot !== null
        ? getCredentialIdentity(credentialSnapshot)
        : undefined,
  };
}

export function stopConsoleContextBridge(): void {
  for (const clientSocket of setClientSocket) {
    clientSocket.destroy();
  }
  setClientSocket.clear();
  if (pipeServer?.listening) {
    pipeServer.close();
  }
  pipeServer = undefined;
  strPipePath = undefined;
  getCurrentCredential = undefined;
}

export async function startConsoleContextBridge(
  getCredentialSnapshot: () => ConsoleCredentialSnapshot | null,
): Promise<void> {
  if (process.platform !== "win32") {
    return;
  }

  getCurrentCredential = getCredentialSnapshot;
  strPipePath = `\\\\.\\pipe\\LiberRPA-Console-executor-${randomUUID()}`;
  const server = createServer((clientSocket) => {
    setClientSocket.add(clientSocket);
    clientSocket.setTimeout(INT_SOCKET_TIMEOUT_MS, () => clientSocket.destroy());
    clientSocket.on("error", () => clientSocket.destroy());
    clientSocket.on("close", () => setClientSocket.delete(clientSocket));
    let requestBuffer = Buffer.alloc(0);
    let boolReplied = false;

    clientSocket.on("data", (requestChunk: Buffer) => {
      if (
        boolReplied ||
        requestBuffer.length + requestChunk.length > INT_REQUEST_MAX_BYTES
      ) {
        clientSocket.destroy();
        return;
      }
      requestBuffer = Buffer.concat([requestBuffer, requestChunk]);
      if (!requestBuffer.includes(0x0a)) {
        return;
      }
      const strRequest = requestBuffer.toString("utf8");
      // The default Windows pipe ACL permits read-only access for some identities.
      // Require this write before returning credentials; never send on connection alone.
      boolReplied = true;
      const credentialSnapshot = getCredentialSnapshot();
      const boolOriginalCredential =
        credentialSnapshot !== null &&
        strRequest ===
          `${STR_CONTEXT_REQUEST_PREFIX}${getCredentialIdentity(credentialSnapshot)}\n`;
      clientSocket.end(
        JSON.stringify({
          version: 1,
          context: boolOriginalCredential
            ? { ...credentialSnapshot, clientType: "executor" }
            : null,
        }) + "\n",
      );
    });
  });
  pipeServer = server;

  await new Promise<void>((resolve, reject) => {
    server.on("error", () => {
      if (pipeServer === server) {
        stopConsoleContextBridge();
      }
      reject(new Error("The local Console credential pipe could not be started."));
    });

    // Keep the operating system's default ACL; do not grant access to other users.
    server.listen({ path: strPipePath, readableAll: false, writableAll: false }, () => {
      if (pipeServer !== server) {
        server.close();
      }
      resolve();
    });
  });
}
