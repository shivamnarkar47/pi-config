/**
 * Re-applies k/M/B token formatting to the @marshal/pi-turn-stats extension.
 *
 * Pi installs that extension straight from npm, so any package update brings back
 * the upstream fmtTokens() (which only knows "k"). Run this after updating:
 *
 *   node ~/.pi/agent/patches/pi-turn-stats-units.mjs [path-to-turn-stats.ts]
 *
 * Then run /reload in pi.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export const ORIGINAL = `function fmtTokens(n: number): string {
	if (n < 1000) return \`\${Math.round(n)}\`;
	return \`\${(n / 1000).toFixed(1)}k\`;
}

function fmtThroughput(tps: number): string {
	if (tps <= 0) return "—";
	if (tps < 1000) return \`\${Math.round(tps)} tok/s\`;
	return \`\${(tps / 1000).toFixed(1)}k tok/s\`;
}`;

export const PATCHED = `/** Token magnitudes, largest first: 1,550,200 → "1.6M", 2,100,000,000 → "2.1B". */
const TOKEN_UNITS: readonly (readonly [number, string])[] = [
	[1_000_000_000, "B"],
	[1_000_000, "M"],
	[1_000, "k"],
];

function fmtTokens(n: number): string {
	if (n < 1000) return \`\${Math.round(n)}\`;
	for (const [scale, suffix] of TOKEN_UNITS) {
		if (n >= scale) return \`\${(n / scale).toFixed(1)}\${suffix}\`;
	}
	return \`\${Math.round(n)}\`;
}

function fmtThroughput(tps: number): string {
	if (tps <= 0) return "—";
	return \`\${fmtTokens(tps)} tok/s\`;
}`;

/** @returns {"patched" | "already" | "failed"} */
export function patchTurnStats(target) {
	if (!existsSync(target)) return "failed";
	const src = readFileSync(target, "utf8");
	if (src.includes("TOKEN_UNITS")) return "already";
	if (!src.includes(ORIGINAL)) return "failed";
	writeFileSync(target, src.replace(ORIGINAL, PATCHED));
	return "patched";
}

if (import.meta.url.endsWith((process.argv[1] ?? "").replace(/\\/g, "/"))) {
	const target =
		process.argv[2] ??
		join(
			homedir(),
			".pi",
			"agent",
			"npm",
			"node_modules",
			"@marshal",
			"pi-turn-stats",
			"extensions",
			"turn-stats.ts",
		);
	const result = patchTurnStats(target);
	if (result === "failed") {
		console.error(`could not patch ${target} (extension changed upstream? patch it by hand)`);
		process.exit(1);
	}
	console.log(
		result === "already"
			? `already patched: ${target}`
			: `patched ${target} (token counts now use k / M / B)`,
	);
	console.log("run /reload in pi to pick it up");
}
