// FileName: validators.ts

import type { JsonValueInput as JsonValue } from "../api/generated/browserApi";

export function validatePathName(value: string | null): true | string {
  // NOTE: Keep this rule aligned with backend/organizations/validators.py; do not rewrite user input.
  if (!value) return "Enter a name.";
  if (/^\p{White_Space}|\p{White_Space}$/u.test(value))
    return "The name must not start or end with whitespace.";
  if (value.endsWith(".")) return "The name must not end with a period.";
  if (/[\\/\p{Cc}\p{Cs}]/u.test(value))
    return "The name must not contain path separators, control characters, or invalid Unicode.";
  if (Array.from(value).length > 128) return "Use at most 128 characters.";
  if (Array.from(value.normalize("NFC")).length > 128)
    return "The normalized name exceeds 128 characters.";
  return true;
}

export function validateEnvironmentName(value: string | null): true | string {
  // NOTE: Keep this rule aligned with backend/console_project/validators.py; do not rewrite user input.
  if (!value) return "Enter an environment name.";
  if (/^\p{White_Space}|\p{White_Space}$/u.test(value))
    return "The environment name must not start or end with whitespace.";
  if (value.endsWith(".")) return "The environment name must not end with a period.";
  if (
    /[<>:"/\\|?*\p{Cs}]/u.test(value) ||
    Array.from(value).some((strCharacter) => strCharacter.charCodeAt(0) < 32)
  )
    return "Use a valid Windows folder name without control characters or invalid Unicode.";
  if (value.length > 255) return "Use at most 255 UTF-16 code units.";
  if (/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(value))
    return "The environment name must not use a reserved Windows device name.";
  return true;
}

export function validateJsonValue(value: JsonValue): void {
  // NOTE: Keep these value rules aligned with backend/console_project/validators.py; size limits belong to the resource.
  function validateText(text: string): void {
    if (text.includes("\0")) throw new Error("JSON text must not contain NUL characters.");
    if (/\p{Cs}/u.test(text)) throw new Error("Use valid Unicode text.");
  }

  function validateChild(child: JsonValue, depth: number): void {
    if (depth > 64) throw new Error("JSON must not exceed 64 levels of nesting.");
    if (
      typeof child === "number" &&
      (!Number.isFinite(child) || (Number.isInteger(child) && !Number.isSafeInteger(child)))
    )
      throw new Error("Use finite numbers and integers within the safe integer range.");
    if (typeof child === "string") validateText(child);
    else if (Array.isArray(child))
      for (const entry of child) validateChild(entry, depth + 1);
    else if (child !== null && typeof child === "object")
      for (const [strKey, entry] of Object.entries(child)) {
        validateText(strKey);
        validateChild(entry, depth + 1);
      }
  }

  validateChild(value, 0);
}
