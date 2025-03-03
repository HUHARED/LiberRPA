// FileName: logger.ts
import { format, transports, createLogger } from "winston";
import path from "path";
// import * as path from "path";
import { shell } from "electron";
import moment from "moment";

import { getBasicConfigDict } from "./commonFunc.js";

// console.log(new Date().toISOString());
// console.log(moment().format("YYYY-MM-DD_HHmmss"));

export const strLogPath = path.join(
  getBasicConfigDict()["outputLogPath"],
  "_UiAnalyzer",
  `${moment().format("YYYY-MM-DD")}.log`
);

console.log("strLogPath=" + strLogPath);

const logFormat = format.printf(({ level, message, timestamp }) => {
  return `[${timestamp}][${level.toUpperCase()}] ${message}`;
});

export const loggerMain = createLogger({
  format: format.combine(
    format.timestamp({
      format: () => moment().format("YYYY-MM-DD HH:mm:ss"),
    }),
    format.errors({ stack: true })
  ),
  transports: [
    new transports.File({
      filename: strLogPath,
      level: "debug",
      format: logFormat, // Apply custom format for file transport
    }),
    new transports.Console({
      level: "debug",
      format: format.combine(
        format.colorize(),
        format.printf((info) => {
          return `${info.message}`;
        })
      ),
    }),
  ],
});

export const openLogPath = () => {
  shell.openPath(strLogPath).catch((error) => {
    loggerMain.log("error", `Error opening log file: ${strLogPath}` + error);
  });
};
