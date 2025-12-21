import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';

export const ChartSection = ({ data, symbol }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  
  // Refs to hold series instances so we can update them later
  const seriesRef = useRef({
    candle: null,
    volume: null,
    ema: null,
    bbUpper: null,
    bbLower: null,
  });

  /* =========================================
     1️⃣ INITIALIZE CHART (Runs Once)
  ========================================= */
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create Chart Instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#161A25' },
        textColor: '#D9D9D9',
      },
      grid: {
        vertLines: { color: 'rgba(43, 43, 67, 0.4)' },
        horzLines: { color: 'rgba(43, 43, 67, 0.4)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      crosshair: { mode: CrosshairMode.Magnet },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2B2B43',
      },
      rightPriceScale: {
        borderColor: '#2B2B43',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
    });

    // Create Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#089981',
      downColor: '#F23645',
      borderVisible: false,
      wickUpColor: '#089981',
      wickDownColor: '#F23645',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '', // Overlay mode
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const emaSeries = chart.addLineSeries({
      color: '#F1C40F',
      lineWidth: 2,
      title: 'EMA 20',
      crosshairMarkerVisible: false,
    });

    const bbUpperSeries = chart.addLineSeries({
      color: 'rgba(41, 98, 255, 0.6)',
      lineWidth: 1,
      title: 'BB Upper',
    });

    const bbLowerSeries = chart.addLineSeries({
      color: 'rgba(41, 98, 255, 0.6)',
      lineWidth: 1,
      title: 'BB Lower',
    });

    // Save references
    chartRef.current = chart;
    seriesRef.current = {
      candle: candleSeries,
      volume: volumeSeries,
      ema: emaSeries,
      bbUpper: bbUpperSeries,
      bbLower: bbLowerSeries,
    };

    // Resize Handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, []); // Empty dependency array ensures this runs once

  /* =========================================
     2️⃣ HANDLE DATA UPDATES
  ========================================= */
  useEffect(() => {
    if (!chartRef.current || !data) return;

    if (Array.isArray(data) && data.length > 0) {
      
      // A. Map & Sanitize
      let cleanData = data
        .map((d) => {
          // 1. Timestamp Validation
          if (!d['@timestamp']) return null;
          const time = Math.floor(new Date(d['@timestamp']).getTime() / 1000);
          if (!Number.isFinite(time)) return null;

          // 2. Value Parsing
          let open = parseFloat(d.open);
          let high = parseFloat(d.high);
          let low = parseFloat(d.low);
          let close = parseFloat(d.close);
          const volume = parseFloat(d.volume);

          if (
            !Number.isFinite(open) ||
            !Number.isFinite(high) ||
            !Number.isFinite(low) ||
            !Number.isFinite(close)
          ) {
            return null;
          }

          // 3. Fix OHLC Logic (Low <= High)
          // Lightweight charts crashes if Low > High or Close outside range
          const maxOC = Math.max(open, close);
          const minOC = Math.min(open, close);
          
          if (high < maxOC) high = maxOC;
          if (low > minOC) low = minOC;

          return {
            time, // UNIX timestamp
            open,
            high,
            low,
            close,
            volume: Number.isFinite(volume) ? volume : 0,
            ema_20: parseFloat(d.ema_20),
            bb_upper: parseFloat(d.bb_upper),
            bb_lower: parseFloat(d.bb_lower),
          };
        })
        .filter(Boolean); // Remove nulls

      // B. SORTING (CRITICAL FIX)
      // Lightweight charts requires strictly ascending time order
      cleanData.sort((a, b) => a.time - b.time);

      // C. DEDUPLICATION (CRITICAL FIX)
      // Remove duplicate timestamps
      const uniqueData = [];
      const seenTimes = new Set();
      for (const item of cleanData) {
        if (!seenTimes.has(item.time)) {
          seenTimes.add(item.time);
          uniqueData.push(item);
        }
      }
      cleanData = uniqueData;

      console.log(`[Chart] Processing ${cleanData.length} candles`);

      // D. Update Series
      if (seriesRef.current.candle) {
        seriesRef.current.candle.setData(
          cleanData.map(d => ({
            time: d.time,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
          }))
        );
      }

      if (seriesRef.current.volume) {
        seriesRef.current.volume.setData(
          cleanData
            .filter(d => d.volume > 0)
            .map(d => ({
              time: d.time,
              value: d.volume,
              color: d.close >= d.open 
                ? 'rgba(8, 153, 129, 0.5)' 
                : 'rgba(242, 54, 69, 0.5)',
            }))
        );
      }

      // E. Update Indicators
      if (seriesRef.current.ema) {
        const emaData = cleanData
          .filter(d => Number.isFinite(d.ema_20) && d.ema_20 > 0)
          .map(d => ({ time: d.time, value: d.ema_20 }));
        seriesRef.current.ema.setData(emaData);
      }

      if (seriesRef.current.bbUpper && seriesRef.current.bbLower) {
        const bbUpData = cleanData
          .filter(d => Number.isFinite(d.bb_upper) && d.bb_upper > 0)
          .map(d => ({ time: d.time, value: d.bb_upper }));
          
        const bbLowData = cleanData
          .filter(d => Number.isFinite(d.bb_lower) && d.bb_lower > 0)
          .map(d => ({ time: d.time, value: d.bb_lower }));

        seriesRef.current.bbUpper.setData(bbUpData);
        seriesRef.current.bbLower.setData(bbLowData);
      }

      // F. Fit Content (Optional - if you want to auto-zoom on data load)
      // chartRef.current.timeScale().fitContent();
    }
  }, [data]);

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-2 left-2 z-10 bg-[#1e2329]/90 backdrop-blur-sm p-2 rounded border border-gray-700 text-xs text-gray-300 pointer-events-none shadow-md">
        <span className="font-bold text-white text-sm mr-2">{symbol}</span>
        <span className="text-gray-400">Technical Analysis</span>
      </div>
      
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};
