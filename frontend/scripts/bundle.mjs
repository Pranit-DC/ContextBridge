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
