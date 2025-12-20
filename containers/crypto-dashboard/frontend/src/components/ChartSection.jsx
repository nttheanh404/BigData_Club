import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';

export const ChartSection = ({ data, symbol }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 1. Initialize Chart with Professional Styling
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#161A25' }, // Dark Exchange Background
        textColor: '#D9D9D9',
      },
      grid: {
        vertLines: { color: 'rgba(43, 43, 67, 0.4)' },
        horzLines: { color: 'rgba(43, 43, 67, 0.4)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      crosshair: {
        mode: CrosshairMode.Magnet, // Snaps to data points
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2B2B43',
      },
      rightPriceScale: {
        borderColor: '#2B2B43',
        scaleMargins: {
          top: 0.1,    // Leave some space at the top
          bottom: 0.2, // Leave space at bottom for volume
        },
      },
    });

    chartRef.current = chart;

    // 2. Add Candlestick Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#089981',         // Professional Teal
      downColor: '#F23645',       // Professional Crimson
      borderVisible: true,
      wickUpColor: '#089981',
      wickDownColor: '#F23645',
      borderUpColor: '#089981',
      borderDownColor: '#F23645',
    });

    // 3. Add Volume Series (Histogram)
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // Overlay mode
    });

    // Force volume to the bottom 15% of the chart
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85, 
        bottom: 0,
      },
    });

    // 4. Add Technical Indicators
    const emaSeries = chart.addLineSeries({ 
      color: '#F1C40F', 
      lineWidth: 2, 
      title: 'EMA 20',
      crosshairMarkerVisible: false 
    });

    const bbUpperSeries = chart.addLineSeries({ 
      color: 'rgba(41, 98, 255, 0.6)', 
      lineWidth: 1, 
      title: 'BB Up' 
    });
    
    const bbLowerSeries = chart.addLineSeries({ 
      color: 'rgba(41, 98, 255, 0.6)', 
      lineWidth: 1, 
      title: 'BB Low' 
    });

    // 5. Format & Set Data
    if (data && data.length > 0) {
      // Map base data with timestamps
      const baseData = data.map(d => {
        const time = new Date(d['@timestamp']).getTime() / 1000;
        return { ...d, time };
      });

      // Set Candle Data (Price is always > 0)
      candleSeries.setData(baseData.map(d => ({
        time: d.time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close
      })));

      // Set Volume Data
      volumeSeries.setData(baseData.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(8, 153, 129, 0.5)' : 'rgba(242, 54, 69, 0.5)',
      })));

      // --- CRITICAL FIX: Filter out ZEROS ---
      // This prevents the chart from scaling down to 0 when indicators are empty
      
      const validEma = baseData
        .filter(d => d.ema_20 > 0)
        .map(d => ({ time: d.time, value: d.ema_20 }));

      const validBbUp = baseData
        .filter(d => d.bb_upper > 0)
        .map(d => ({ time: d.time, value: d.bb_upper }));

      const validBbLow = baseData
        .filter(d => d.bb_lower > 0)
        .map(d => ({ time: d.time, value: d.bb_lower }));

      emaSeries.setData(validEma);
      bbUpperSeries.setData(validBbUp);
      bbLowerSeries.setData(validBbLow);
    }

    // 6. Handle Resize
    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  return (
    <div className="relative w-full h-full">
      {/* Overlay Title */}
      <div className="absolute top-2 left-2 z-10 bg-[#1e2329]/90 backdrop-blur-sm p-2 rounded border border-gray-700 text-xs text-gray-300 pointer-events-none shadow-md">
        <span className="font-bold text-white text-sm mr-2">{symbol}</span> 
        <span className="text-gray-400">Technical Analysis</span>
      </div>
      
      {/* Chart Container */}
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};
