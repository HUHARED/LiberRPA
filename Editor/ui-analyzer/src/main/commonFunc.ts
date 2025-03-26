// FileName: commonFunc.ts
import path from "path";
import fs from "fs";
import * as os from "os";
import * as jsoncParser from "jsonc-parser";

interface DictBasicConfig {
  version: string;
  LiberRPAPath: string;
  outputLogPath: string;
  localServerPort: string;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: "true" | "false";
}

const strLiberRPAEnvPath = process.env.LiberRPA;
console.log(`strLiberRPAEnvPath= ${strLiberRPAEnvPath}`);

export function getBasicConfigDict(): DictBasicConfig {
  if (strLiberRPAEnvPath) {
    const strSettingPath = path.join(strLiberRPAEnvPath, "./configFiles/basic.jsonc");

    try {
      let data = fs.readFileSync(strSettingPath, { encoding: "utf-8" });
      console.log(data);

      const dictReplaceKeywords: { [key: string]: string } = {
        "${LiberRPA}": strLiberRPAEnvPath.replace(/\\/g, "\\\\"),
        "${UserName}": os.userInfo().username,
        "${HostName}": os.hostname(),
        "${ToolName}": "BuildinTools",
      };

      console.log(dictReplaceKeywords);

      for (const keyName of Object.keys(dictReplaceKeywords)) {
        // Escape special regex characters in keyName
        const safeKeyName = keyName.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");

        data = data.replace(new RegExp(safeKeyName, "g"), dictReplaceKeywords[keyName]);
      }
      console.log(data);

      const dictSettings = jsoncParser.parse(data) as DictBasicConfig;
      console.log("dictSettings=", JSON.stringify(dictSettings));
      return dictSettings;
    } catch (e) {
      throw new Error(`Error reading or parsing file: ${e}`);
    }
  } else {
    throw new Error(
      "Not found 'LiberRPA' in User Envirnment Variables, you should add it before using LiberRPA UI Analyzer."
    );
  }
}
