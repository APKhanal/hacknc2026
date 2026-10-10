import type { SimPath } from "@/lib/types";
import { computeWeeklyBand, sampleRepresentativePaths } from "@/lib/fanchart";

const WIDTH = 920;
const HEIGHT = 360;
const PAD = { top: 16, right: 16, bottom: 28, left: 64 };
const REPRESENTATIVE_PATH_COUNT = 20;

function buildScales(
  weeks: number,
  minY: number,
  maxY: number
): { x: (week: number) => number; y: (value: number) => number } {
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (week: number) => PAD.left + (week / Math.max(weeks - 1, 1)) * innerW;
  const y = (value: number) =>
    PAD.top + innerH - ((value - minY) / Math.max(maxY - minY, 1e-6)) * innerH;
  return { x, y };
}

export function FanChart({
  paths,
  breachThreshold,
}: {
  paths: SimPath[];
  breachThreshold: number;
}) {
  const band = computeWeeklyBand(paths);
  if (band.length === 0) {
    return <p className="muted">No path data for this run.</p>;
  }

  const representative = sampleRepresentativePaths(paths, REPRESENTATIVE_PATH_COUNT);
  const weeks = band.length;

  const allValues = band.flatMap((b) => [b.p10, b.p90]).concat(breachThreshold);
  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const { x, y } = buildScales(weeks, minY, maxY);

  const bandTop = band.map((b) => `${x(b.week)},${y(b.p90)}`).join(" L ");
  const bandBottom = band
    .slice()
    .reverse()
    .map((b) => `${x(b.week)},${y(b.p10)}`)
    .join(" L ");
  const bandPath = `M ${bandTop} L ${bandBottom} Z`;
  const medianPath = `M ${band.map((b) => `${x(b.week)},${y(b.p50)}`).join(" L ")}`;

  const yTicks = [minY, (minY + maxY) / 2, maxY];

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="fan-chart"
      role="img"
      aria-label="500 simulated balance paths over the horizon, shown as a p10-p90 band with median"
    >
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(v)} y2={y(v)} className="gridline" />
          <text x={PAD.left - 8} y={y(v)} className="axis-label" textAnchor="end" dominantBaseline="middle">
            ${v.toFixed(0)}
          </text>
        </g>
      ))}

      <line
        x1={PAD.left}
        x2={WIDTH - PAD.right}
        y1={y(breachThreshold)}
        y2={y(breachThreshold)}
        className="breach-line"
      />
      <text x={WIDTH - PAD.right} y={y(breachThreshold) - 6} className="axis-label" textAnchor="end">
        breach threshold
      </text>

      <path d={bandPath} className="band" />

      {representative.map((p) => (
        <polyline
          key={p.path_id}
          points={p.balances.map((v, w) => `${x(w)},${y(v)}`).join(" ")}
          className="representative-path"
        />
      ))}

      <path d={medianPath} className="median-path" />

      <text x={PAD.left} y={HEIGHT - 6} className="axis-label">
        week 0
      </text>
      <text x={WIDTH - PAD.right} y={HEIGHT - 6} className="axis-label" textAnchor="end">
        week {weeks - 1}
      </text>
    </svg>
  );
}
