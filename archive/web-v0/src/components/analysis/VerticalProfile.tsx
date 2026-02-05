import { useRef, useEffect } from "react";
import type { VerticalPoint } from "../../api/routes";

interface Props {
  points: VerticalPoint[];
}

const WIDTH = 340;
const HEIGHT = 160;
const PADDING = { top: 10, right: 10, bottom: 30, left: 50 };

export default function VerticalProfile({ points }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || points.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = WIDTH - PADDING.left - PADDING.right;
    const h = HEIGHT - PADDING.top - PADDING.bottom;

    const maxDist = Math.max(...points.map((p) => p.distance_nm), 1);
    const maxAlt = Math.max(...points.map((p) => p.altitude_ft), 500);

    const toX = (nm: number) => PADDING.left + (nm / maxDist) * w;
    const toY = (ft: number) => PADDING.top + h - (ft / maxAlt) * h;

    ctx.clearRect(0, 0, WIDTH, HEIGHT);

    // Grid lines
    ctx.strokeStyle = "#e0e0e0";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = PADDING.top + (h / 4) * i;
      ctx.beginPath();
      ctx.moveTo(PADDING.left, y);
      ctx.lineTo(WIDTH - PADDING.right, y);
      ctx.stroke();
    }

    // Profile fill
    ctx.fillStyle = "rgba(0,120,215,0.15)";
    ctx.beginPath();
    ctx.moveTo(toX(points[0].distance_nm), toY(0));
    for (const p of points) {
      ctx.lineTo(toX(p.distance_nm), toY(p.altitude_ft));
    }
    ctx.lineTo(toX(points[points.length - 1].distance_nm), toY(0));
    ctx.closePath();
    ctx.fill();

    // Profile line
    ctx.strokeStyle = "#0078d7";
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((p, i) => {
      const fn = i === 0 ? ctx.moveTo : ctx.lineTo;
      fn.call(ctx, toX(p.distance_nm), toY(p.altitude_ft));
    });
    ctx.stroke();

    // Waypoint markers
    ctx.fillStyle = "#333";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    for (const p of points) {
      if (p.waypoint_name) {
        ctx.beginPath();
        ctx.arc(toX(p.distance_nm), toY(p.altitude_ft), 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillText(p.waypoint_name, toX(p.distance_nm), toY(p.altitude_ft) - 8);
      }
    }

    // Axes labels
    ctx.fillStyle = "#888";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const alt = Math.round((maxAlt / 4) * (4 - i));
      ctx.fillText(`${alt}`, PADDING.left - 4, PADDING.top + (h / 4) * i + 3);
    }
    ctx.textAlign = "center";
    ctx.fillText("ft", PADDING.left - 4, PADDING.top - 2);
    ctx.fillText("NM", WIDTH - PADDING.right, HEIGHT - 4);
    ctx.fillText("0", toX(0), HEIGHT - 4);
    ctx.fillText(maxDist.toFixed(0), toX(maxDist), HEIGHT - 4);
  }, [points]);

  return (
    <canvas
      ref={canvasRef}
      width={WIDTH}
      height={HEIGHT}
      style={{ width: WIDTH, height: HEIGHT, borderRadius: 4, background: "#fafafa" }}
    />
  );
}
