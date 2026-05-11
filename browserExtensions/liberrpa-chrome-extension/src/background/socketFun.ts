// FileName: socketFun.ts
import io from "socket.io-client";
import { handleCommand } from "./handleCommand";
import { setSocketConnected } from "./icon";

import type { DictCommandFromFlask, DictResultToFlask } from "./interface";

let intServerPort: number | null = null;
let socket: ReturnType<typeof io> | null = null;

// Function to connect to native messaging host and receive server port
async function getServerPort(): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    // It should run only once to get port from native messaging host.
    if (intServerPort) {
      resolve(intServerPort);
      return;
    }

    // If serverPort is null, get it from native messaging host.
    // \HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost
    const strHostName = "com.liberrpa.chrome.msghost";
    console.info("Connected to native messaging host:", strHostName);

    const nativeTemp = chrome.runtime.connectNative(strHostName);

    nativeTemp.onMessage.addListener((msg: Record<string, number>) => {
      console.log("Receive message from native messaging host:", msg);
      intServerPort = msg.port;
      console.log(`serverPort=${intServerPort}`);
      resolve(intServerPort);
    });

    nativeTemp.onDisconnect.addListener(() => {
      const error = chrome.runtime.lastError;

      if (!intServerPort) {
        reject(new Error(error ? error.message : "Disconnected without receiving port."));
      }

      console.info(
        "Disconnected:",
        error ? error.message : "Unknown Chrome runtime error."
      );
    });

    console.log("Post message start.");
    nativeTemp.postMessage({ command: "get_port" });
    console.log("Post message done.");
  });
}

export async function setupSocket(): Promise<void> {
  await setSocketConnected(false);

  try {
    const port = await getServerPort();
    const url = `http://localhost:${port}`;
    socket = io(url, { transports: ["websocket"] });

    socket.on("connect", () => {
      console.log("Socket.IO connection established.", socket?.id);
      socket?.emit(
        "chrome_extension_connect",
        JSON.stringify("The message for recording sid.")
      );
      void setSocketConnected(true);
    });

    socket.on("disconnect", () => {
      console.log("Socket.IO connection disconnected");
      // socket = null;
      void setSocketConnected(false);
    });

    socket.on("connect_error", (e: Error) => {
      console.error("Socket.IO connection error:", e);
      // socket = null;
      void setSocketConnected(false);
    });

    socket.on("message_flask_to_chrome", async (data: string) => {
      console.log("--message_flask_to_chrome--");
      console.log(data);

      try {
        const parseData = JSON.parse(data) as DictCommandFromFlask;
        const result = await handleCommand(parseData);

        sendResultToFlask(result);
      } catch (e) {
        console.error("Error handling  message from server:", e);
      }
    });
  } catch (e) {
    console.error("Failed to setup socket:", e);
    await setSocketConnected(false);
  }
}

function sendResultToFlask(data: DictResultToFlask) {
  console.log("--sendResultToFlask--");

  if (socket?.connected) {
    // Here doesn't need try-catch for json, due to handleCommand() has done it.
    socket.emit("result_chrome_to_flask", JSON.stringify(data));
  } else {
    console.error("Socket is not connected.");
  }
}
