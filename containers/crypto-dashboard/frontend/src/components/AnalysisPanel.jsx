import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export const AnalysisPanel = ({ data }) => {
  if (!data) return null;

  const { close, ema_200, rsi_14, macd_hist, adx } = data;

  // Simple Logic Rules
  const trend = close > ema_200 ? 'Bullish' : 'Bearish';
  const momentum = rsi_14 > 55 ? 'Strong' : rsi_14 < 45 ? 'Weak' : 'Neutral';
  const macdStatus = macd_hist > 0 ? 'Positive' : 'Negative';

  const SignalBadge = ({ type, text }) => {
    const color = type === 'Bullish' || type === 'Positive' || type === 'Strong' 
        ? 'text-green-400 bg-green-400/10 border-green-400/20' 
        : type === 'Neutral' 
        ? 'text-gray-400 bg-gray-400/10 border-gray-400/20'
        : 'text-red-400 bg-red-400/10 border-red-400/20';
    return (
        <span className={`px-2 py-1 rounded text-xs border ${color} font-mono`}>{text}</span>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-[#1e2329]/50 backdrop-blur-sm p-4 rounded-xl border border-white/5">
        <h4 className="text-gray-400 text-xs uppercase mb-2">Trend (EMA 200)</h4>
        <div className="flex items-center gap-2">
            {trend === 'Bullish' ? <TrendingUp className="text-green-500"/> : <TrendingDown className="text-red-500"/>}
            <span className="text-xl font-bold text-white">{trend}</span>
        </div>
        <div className="text-xs text-gray-500 mt-1">Price is {trend === 'Bullish' ? 'above' : 'below'} EMA200</div>
      </div>

      <div className="bg-[#1e2329]/50 backdrop-blur-sm p-4 rounded-xl border border-white/5">
         <h4 className="text-gray-400 text-xs uppercase mb-2">Momentum Signals</h4>
         <div className="space-y-2">
            <div className="flex justify-between text-sm">
                <span className="text-gray-400">RSI Strength</span>
                <SignalBadge type={momentum} text={momentum} />
            </div>
            <div className="flex justify-between text-sm">
                <span className="text-gray-400">MACD Hist</span>
                <SignalBadge type={macdStatus} text={macdStatus} />
            </div>
         </div>
      </div>
    </div>
  );
};
