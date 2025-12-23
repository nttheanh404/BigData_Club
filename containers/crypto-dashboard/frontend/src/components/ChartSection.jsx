import React, { useEffect, useRef } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";

// ===================== COLORS =====================
const COLORS = {
  UP: "#0ECB81",
  DOWN: "#F6465D",
  EMA_9: "#F0B90B",
  EMA_20: "#3B82F6",
  EMA_50: "#A855F7",
  BB: "rgba(0, 150, 255, 0.5)", // Bollinger
  GRID: "#2B3139",
  BG: "#0B0E11",
  TEXT: "#848E9C",
};
const formatDisplaySymbol = (symbol) => {
  if (!symbol) return "";
  if (symbol.endsWith("USDT")) return symbol.replace("USDT", "/USDT");
  return symbol;
};
export function ChartSection({ data, showBB, activeSubIndicator }) {
  const chartRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    // 1. CLEAN DATA
    const cleanData = (rawData) => {
      const map = new Map();
      rawData.forEach((d) => {
        if (!d.timestamp) return;
        const ts = new Date(d.timestamp).getTime() / 1000;
        if (isNaN(ts)) return;
        map.set(ts, { ...d, time: ts });
      });
      return Array.from(map.values()).sort((a, b) => a.time - b.time);
    };

    const sortedData = cleanData(data);
    if (sortedData.length === 0) return;

    // 2. CREATE CHART
    if (chartRef.current) chartRef.current.remove();

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' }, // Allow container bg to show
        textColor: COLORS.TEXT,
      },
      grid: {
        vertLines: { color: "rgba(43, 49, 57, 0.5)" },
        horzLines: { color: "rgba(43, 49, 57, 0.5)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { borderColor: COLORS.GRID, timeVisible: true },
      rightPriceScale: {
        borderColor: COLORS.GRID,
        scaleMargins: { top: 0.1, bottom: 0.3 }, // Leave room for sub-indicator
      },
    });

    chartRef.current = chart;

    // ===================== MAIN SERIES =====================
    const candleSeries = chart.addCandlestickSeries({
      upColor: COLORS.UP, downColor: COLORS.DOWN,
      borderUpColor: COLORS.UP, borderDownColor: COLORS.DOWN,
      wickUpColor: COLORS.UP, wickDownColor: COLORS.DOWN,
    });
    
    candleSeries.setData(sortedData.map(d => ({
      time: d.time, open: d.open, high: d.high, low: d.low, close: d.close
    })));

    // EMAs
    const addLine = (color, width) => chart.addLineSeries({ color, lineWidth: width, priceScaleId: 'right' });
    const ema9 = addLine(COLORS.EMA_9, 1);
    const ema20 = addLine(COLORS.EMA_20, 1);
    const ema50 = addLine(COLORS.EMA_50, 1);

    ema9.setData(sortedData.map(d => ({ time: d.time, value: d.ema_9 })));
    ema20.setData(sortedData.map(d => ({ time: d.time, value: d.ema_20 })));
    ema50.setData(sortedData.map(d => ({ time: d.time, value: d.ema_50 })));

    // BOLLINGER BANDS (Optional)
    if (showBB) {
      const bbUpper = addLine(COLORS.BB, 1);
      const bbLower = addLine(COLORS.BB, 1);
      bbUpper.setData(sortedData.filter(d => d.bb_upper).map(d => ({ time: d.time, value: d.bb_upper })));
      bbLower.setData(sortedData.filter(d => d.bb_lower).map(d => ({ time: d.time, value: d.bb_lower })));
    }

    // ===================== SUB INDICATORS =====================
    // We use a separate scale ID "sub" to position it at the bottom
    const subScaleOptions = {
        scaleMargins: { top: 0.75, bottom: 0 },
    };

    if (activeSubIndicator === 'vol') {
        const volumeSeries = chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'sub', 
        });
        chart.priceScale('sub').applyOptions(subScaleOptions);
        volumeSeries.setData(sortedData.map(d => ({
            time: d.time, value: d.volume,
            color: d.close >= d.open ? 'rgba(14, 203, 129, 0.5)' : 'rgba(246, 70, 93, 0.5)'
        })));
    } 
    else if (activeSubIndicator === 'rsi') {
        const rsiSeries = chart.addLineSeries({ color: '#A855F7', lineWidth: 2, priceScaleId: 'sub' });
        chart.priceScale('sub').applyOptions(subScaleOptions);
        // Add 70/30 lines logic could go here (using Extra series or just understanding the levels)
        rsiSeries.setData(sortedData.filter(d => d.rsi_14).map(d => ({ time: d.time, value: d.rsi_14 })));
    }
    else if (activeSubIndicator === 'macd') {
        const macdHist = chart.addHistogramSeries({ priceScaleId: 'sub' });
        const macdLine = chart.addLineSeries({ color: '#3B82F6', lineWidth: 1, priceScaleId: 'sub' });
        const macdSig = chart.addLineSeries({ color: '#F6465D', lineWidth: 1, priceScaleId: 'sub' });
        
        chart.priceScale('sub').applyOptions(subScaleOptions);

        macdHist.setData(sortedData.filter(d => d.macd_hist).map(d => ({
            time: d.time, value: d.macd_hist,
            color: d.macd_hist >= 0 ? 'rgba(14, 203, 129, 0.4)' : 'rgba(246, 70, 93, 0.4)'
        })));
        macdLine.setData(sortedData.filter(d => d.macd_line).map(d => ({ time: d.time, value: d.macd_line })));
        macdSig.setData(sortedData.filter(d => d.macd_signal).map(d => ({ time: d.time, value: d.macd_signal })));
    }
    else if (activeSubIndicator === 'stoch') {
        const stochK = chart.addLineSeries({ color: '#3B82F6', lineWidth: 1, priceScaleId: 'sub' });
        const stochD = chart.addLineSeries({ color: '#F6465D', lineWidth: 1, priceScaleId: 'sub' });
        chart.priceScale('sub').applyOptions(subScaleOptions);
        
        stochK.setData(sortedData.filter(d => d.stoch_k).map(d => ({ time: d.time, value: d.stoch_k })));
        stochD.setData(sortedData.filter(d => d.stoch_d).map(d => ({ time: d.time, value: d.stoch_d })));
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [data, showBB, activeSubIndicator]);

  return <div ref={containerRef} className="w-full h-full" />;
}
