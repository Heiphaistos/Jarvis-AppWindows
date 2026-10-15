import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";

const store = new Map<string, string>();
(globalThis as any).localStorage = {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
};
const { readAutoUpdate, writeAutoUpdate } = await import("./updater");

describe("réglage de mise à jour automatique", () => {
  beforeEach(() => store.clear());
  it("est actif par défaut", () => expect(readAutoUpdate()).toBe(true));
  it("se coupe puis se réactive", () => {
    writeAutoUpdate(false);
    expect(readAutoUpdate()).toBe(false);
    writeAutoUpdate(true);
    expect(readAutoUpdate()).toBe(true);
  });
});

describe("version", () => {
  it("est identique dans package.json, tauri.conf.json et Cargo.toml", () => {
    const pkg = JSON.parse(readFileSync("package.json", "utf8")).version;
    const tauri = JSON.parse(readFileSync("src-tauri/tauri.conf.json", "utf8")).version;
    const cargo = readFileSync("src-tauri/Cargo.toml", "utf8").match(/^version = "([^"]+)"/m)?.[1];
    expect(tauri).toBe(pkg);
    expect(cargo).toBe(pkg);
  });
});
