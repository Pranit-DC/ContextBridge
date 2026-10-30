import { cp, mkdir, readFile, readdir, writeFile, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
const hashes = new Set();
async function scan(path) {
  for (const item of await readdir(path, { withFileTypes: true })) {
    const file = `${path}/${item.name}`;
    if (item.isDirectory()) await scan(file);
    else if (item.name.endsWith(".html")) {
      const html = await readFile(file, "utf8");
      for (const match of html.matchAll(
        /<script([^>]*)>([\s\S]*?)<\/script>/g,
      )) {
        if (!/\bsrc=/.test(match[1]))
          hashes.add(
            `'sha256-${createHash("sha256").update(match[2]).digest("base64")}'`,
          );
      }
    }
  }
}
await scan("out");
await mkdir("../src/contextbridge/product/web", { recursive: true });
// Remove obsolete chunks so release packages never accumulate old builds.
for (const entry of await readdir("../src/contextbridge/product/web")) {
  if (entry !== ".gitignore")
    await rm(`../src/contextbridge/product/web/${entry}`, {
      recursive: true,
      force: true,
    });
}
await cp("out", "../src/contextbridge/product/web", { recursive: true });
await writeFile(
  "../src/contextbridge/product/web/csp.json",
  JSON.stringify([...hashes]),
);

// Keep upstream license/notice texts alongside the distributed static assets.
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
const notices = [
  "Third-party notices for ContextBridge's frontend and build dependencies.\n",
];
async function licenseTexts(directory, recursive = false) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = `${directory}/${entry.name}`;
    if (entry.isDirectory() && recursive) await licenseTexts(file, true);
    else if (
      entry.isFile() &&
      /^(licen[cs]e|notice)(\..*)?$/i.test(entry.name)
    ) {
      notices.push(`\n--- ${file} ---\n${await readFile(file, "utf8")}\n`);
    }
  }
}
for (const [directory, metadata] of Object.entries(lock.packages)) {
  if (directory && !metadata.dev) {
    try {
      await licenseTexts(directory);
    } catch (error) {
      if (!(metadata.optional && error.code === "ENOENT")) throw error;
    }
  }
}
await licenseTexts("node_modules/next/dist/compiled", true);
await writeFile(
  "../src/contextbridge/product/web/THIRD_PARTY_NOTICES.txt",
  notices.join("\n"),
);
