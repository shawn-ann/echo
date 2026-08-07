import fs from "fs";
import path from "path";

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const WIREFRAMES_DIR = __dirname;

function escapeXml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function parseRoundness(roundness, w, h) {
  if (!roundness) return 0;
  if (roundness.type === 3) return Math.min(w, h) * 0.18;
  if (roundness.type === 2) return Math.min(w, h) / 2;
  if (roundness.type === 1) return roundness.value || 0;
  return 0;
}

function renderElement(el) {
  const { type, x, y, width, height } = el;
  const stroke =
    el.strokeStyle === "dashed" ? 'stroke-dasharray="8 4"' : "";
  const sw = el.strokeWidth || 2;
  const opacity = el.opacity != null ? `opacity="${el.opacity / 100}"` : "";
  const common = `x="${x}" y="${y}" width="${width}" height="${height}" ${opacity}`;

  if (type === "rectangle") {
    const fill =
      el.backgroundColor && el.backgroundColor !== "transparent"
        ? el.backgroundColor
        : "none";
    const rx = parseRoundness(el.roundness, width, height);
    return `<rect ${common} rx="${rx}" ry="${rx}" fill="${escapeXml(fill)}" stroke="${escapeXml(
      el.strokeColor
    )}" stroke-width="${sw}" ${stroke}/>`;
  }

  if (type === "ellipse") {
    const fill =
      el.backgroundColor && el.backgroundColor !== "transparent"
        ? el.backgroundColor
        : "none";
    return `<ellipse cx="${x + width / 2}" cy="${y + height / 2}" rx="${
      width / 2
    }" ry="${height / 2}" fill="${escapeXml(fill)}" stroke="${escapeXml(
      el.strokeColor
    )}" stroke-width="${sw}" ${stroke}/>`;
  }

  if (type === "text") {
    const fontSize = el.fontSize || 20;
    const weight = el.fontWeight ? ` font-weight="${el.fontWeight}"` : "";
    const anchor = el.textAlign === "center" ? "middle" : "start";
    const tx = el.textAlign === "center" ? x + width / 2 : x;
    const ty = y + height / 2 + fontSize * 0.35;
    return `<text ${opacity} x="${tx}" y="${ty}" text-anchor="${anchor}" font-size="${fontSize}"${weight} font-family="sans-serif" fill="${escapeXml(
      el.strokeColor
    )}">${escapeXml(el.text || "")}</text>`;
  }

  return "";
}

function getBounds(elements) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const el of elements) {
    minX = Math.min(minX, el.x);
    minY = Math.min(minY, el.y);
    maxX = Math.max(maxX, el.x + (el.width || 0));
    maxY = Math.max(maxY, el.y + (el.height || 0));
  }
  return { minX, minY, maxX, maxY };
}

function convert(inputFile) {
  const scene = JSON.parse(fs.readFileSync(inputFile, "utf8"));
  const elements = scene.elements.filter((el) => !el.isDeleted);
  const { minX, minY, maxX, maxY } = getBounds(elements);
  const pad = 20;
  const w = Math.ceil(maxX - minX + pad * 2);
  const h = Math.ceil(maxY - minY + pad * 2);
  const body = elements.map(renderElement).join("\n  ");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${Math.floor(
    minX - pad
  )} ${Math.floor(minY - pad)} ${w} ${h}" width="${w}" height="${h}">
  ${body}
</svg>
`;
  return svg;
}

const files = fs
  .readdirSync(WIREFRAMES_DIR)
  .filter((f) => f.endsWith(".excalidraw") && !f.endsWith(".svg"));

if (files.length === 0) {
  console.log("No .excalidraw source files found.");
  process.exit(0);
}

for (const f of files) {
  const input = path.join(WIREFRAMES_DIR, f);
  const output = path.join(WIREFRAMES_DIR, f + ".svg");
  const svg = convert(input);
  fs.writeFileSync(output, svg);
  console.log(`✓ ${f} -> ${f}.svg (${Buffer.byteLength(svg)} bytes)`);
}
