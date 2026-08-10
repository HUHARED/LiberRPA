// FileName: componentRequirement.ts

export function getSuggestedComponentRequirement(version: string): string {
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(version);
  if (match === null) {
    return `==${version}`;
  }

  const intMajor = Number(match[1]);
  if (intMajor === 0) {
    const intMinor = Number(match[2] ?? "0");
    return `>=${version},<0.${String(intMinor + 1)}`;
  }

  return `>=${version},<${String(intMajor + 1)}`;
}
