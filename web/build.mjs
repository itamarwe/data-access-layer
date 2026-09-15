import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const source = resolve(root, "src");
const target = resolve(root, "../dal/api/static");

await rm(target, { recursive: true, force: true });
await mkdir(resolve(target, "assets"), { recursive: true });
await cp(resolve(source, "index.html"), resolve(target, "index.html"));
await cp(resolve(source, "styles.css"), resolve(target, "assets/styles.css"));
await cp(resolve(source, "app.js"), resolve(target, "assets/app.js"));
await cp(resolve(source, "lib"), resolve(target, "assets/lib"), { recursive: true });
await cp(resolve(source, "views"), resolve(target, "assets/views"), { recursive: true });
