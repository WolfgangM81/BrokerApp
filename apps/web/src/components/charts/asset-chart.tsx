"use client";

import { CandlestickSeries, createChart, type IChartApi, type Time } from "lightweight-charts";
import * as React from "react";
import type { BarOut } from "@brokerapp/api-client";

export function AssetChart({ bars }: { bars: BarOut[] }) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);

  React.useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: "#525252",
        fontFamily: "var(--font-sans, system-ui)",
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
      timeScale: { borderColor: "#e5e5e5" },
      rightPriceScale: { borderColor: "#e5e5e5" },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
      borderVisible: false,
    });
    series.setData(
      bars.map((b) => ({
        time: (Math.floor(new Date(b.time).getTime() / 1000) as unknown) as Time,
        open: Number(b.open),
        high: Number(b.high),
        low: Number(b.low),
        close: Number(b.close),
      })),
    );
    chartRef.current = chart;
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [bars]);

  return <div ref={containerRef} className="h-full w-full" />;
}
