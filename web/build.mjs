// Build the static dashboard into web/dist: check results.json has the shape
// index.html reads, then copy both files. No dependencies.
import { copyFileSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const dist = join(root, "dist");

const results = JSON.parse(readFileSync(join(root, "results.json"), "utf8"));
const problems = [];
const summary = results.summary ?? {};
for (const key of ["decisions", "eval", "tokens"]) {
  if (!summary[key]) problems.push(`summary.${key} is missing`);
}
if (!Array.isArray(results.items)) problems.push("items is not an array");
for (const [i, item] of (results.items ?? []).entries()) {
  if (!["approve", "flag", "reject"].includes(item.decision)) problems.push(`items[${i}].decision is ${item.decision}`);
  if (!item.clause) problems.push(`items[${i}].clause is missing`);
}
if (problems.length) {
  console.error(`results.json is not dashboard-ready:\n- ${problems.join("\n- ")}`);
  process.exit(1);
}

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist);
for (const file of ["index.html", "results.json"]) copyFileSync(join(root, file), join(dist, file));
console.log(`Built web/dist with ${results.items.length} line items.`);
