import React, { useEffect, useState } from 'react';
import { TechCard } from './components/TechCard';
import { ChartSection } from './components/ChartSection';
import { RefreshCw, TrendingUp, Clock } from 'lucide-react';

const API_URL = "/api";

function App() {
  const [latestData, setLatestData] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [techData, setTechData] = useState([]); 
  const [timeframe, setTimeframe] = useState("1m"); 
  const [loading, setLoading] = useState(false);

  // 1. Fetch Live Assets Table
  const fetchLatest = async () => {
    try {
      const res = await fetch(`${API_URL}/latest?size=20`);
      const data = await res.json();
      setLatestData(data);
      if (!selectedSymbol && data.length > 0) {
          console.log("[DEBUG 1] Auto-selecting symbol:", data[0].symbol); // LOG 1
          setSelectedSymbol(data[0].symbol);
      }
    } catch (e) {
      console.error("Fetch latest error", e);
    }
  };

  // 2. Fetch Technical Analysis Data
  const fetchTechnical = async (symbol, tf) => {
    if (!symbol) return;
    console.log(`[DEBUG 2] Fetching technical for: ${symbol} (${tf})`); // LOG 2
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/technical?symbol=${symbol}&timeframe=${tf}&limit=100`);
      const data = await res.json();
      
      console.log("[DEBUG 3] Chart Data Received:", data); // LOG 3
      if (data.length === 0) console.warn("[WARN] Received EMPTY data array for chart!");

      setTechData(data);
    } catch (e) {
      console.error("Fetch technical error", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatest();
    const interval = setInterval(fetchLatest, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedSymbol) {
        fetchTechnical(selectedSymbol, timeframe);
    }
  }, [selectedSymbol, timeframe]);

  const currentDetails = techData.length > 0 ? techData[techData.length - 1] : null;
  const currentTable = latestData.find(d => d.symbol === selectedSymbol) || {};

  return (
    <div className="min-h-screen bg-[#0b0e11] text-[#eaecef] p-6 font-sans">
      <header className="max-w-7xl mx-auto flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Spark AI Crypto Stream
          </h1>
          <p className="text-gray-500 text-sm mt-1">Real-time PySpark Analysis • EMA • MACD • Bollinger Bands</p>
        </div>
        <button onClick={fetchLatest} className="p-2 bg-gray-800 rounded-full hover:bg-gray-700 transition">
          <RefreshCw size={20} className="text-gray-300" />
        </button>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: List of Assets */}
        <div className="lg:col-span-1 space-y-4">
           <div className="bg-[#1e2329] rounded-xl border border-gray-800 overflow-hidden">
             <div className="p-4 border-b border-gray-800 bg-[#1e2329]">
               <h3 className="font-semibold text-gray-200">Live Assets</h3>
             </div>
             <div className="max-h-[80vh] overflow-y-auto">
               <table className="w-full text-left">
                 <thead className="text-xs text-gray-500 bg-[#1e2329] sticky top-0">
                   <tr>
                     <th className="p-3">Symbol</th>
                     <th className="p-3 text-right">Price</th>
                     <th className="p-3 text-right">RSI</th>
                   </tr>
                 </thead>
                 <tbody className="divide-y divide-gray-800">
                   {latestData.map((item) => {
                     const isSelected = selectedSymbol === item.symbol;
                     const rsiVal = item.rsi_14 || item.rsi;
                     const isBullish = rsiVal > 70 || item.close > item.ema_20;
                     
                     return (
                       <tr 
                        key={item.symbol} 
                        onClick={() => setSelectedSymbol(item.symbol)}
                        className={`cursor-pointer transition hover:bg-gray-800 ${isSelected ? 'bg-blue-900/20 border-l-2 border-blue-500' : ''}`}
                       >
                         <td className="p-3 font-medium">
                           <div className="flex items-center gap-2">
                             {item.symbol}
                             {isBullish && <TrendingUp size={14} className="text-green-500" />}
                           </div>
                         </td>
                         <td className="p-3 text-right text-gray-300">${item.close?.toFixed(2)}</td>
                         <td className={`p-3 text-right font-mono ${rsiVal > 70 ? 'text-red-400' : rsiVal < 30 ? 'text-green-400' : 'text-gray-500'}`}>
                           {rsiVal?.toFixed(1)}
                         </td>
                       </tr>
                     )
                   })}
                 </tbody>
               </table>
             </div>
           </div>
        </div>

        {/* Right Column: Charts & Details */}
        <div className="lg:col-span-2">
          {selectedSymbol && (
             <>
                <div className="grid grid-cols-3 gap-4 mb-6">
                   {(() => {
                      const price = currentDetails?.close || currentTable.close;
                      const rsi = currentDetails?.rsi_14 || currentTable.rsi;
                      const bbUpper = currentDetails?.bb_upper;
                      
                      let signalType = "neutral";
                      let signalText = "Neutral";
                      
                      if (rsi > 70) { signalType = "down"; signalText = "Overbought"; }
                      else if (rsi < 30) { signalType = "up"; signalText = "Oversold"; }
                      
                      return (
                        <>
                          <TechCard title="Price" value={`$${price?.toFixed(2)}`} />
                          <TechCard 
                            title="RSI (14)" 
                            value={rsi?.toFixed(1) || "--"} 
                            type={signalType} 
                            subValue={signalText}
                          />
                          <TechCard 
                            title="Bollinger Upper" 
                            value={bbUpper ? `$${bbUpper.toFixed(2)}` : "--"}
                            type="neutral"
                            subValue="Volatility"
                           />
                        </>
                      )
                   })()}
                </div>

                <div className="flex justify-between items-center mb-4 bg-[#1e2329] p-2 rounded-lg border border-gray-800">
                    <div className="flex items-center gap-2 px-2">
                        <Clock size={16} className="text-gray-400" />
                        <span className="text-sm font-medium text-gray-300">Timeframe</span>
                    </div>
                    <div className="flex gap-1">
                        {["1m", "5m", "15m", "1h"].map((tf) => (
                            <button
                                key={tf}
                                onClick={() => setTimeframe(tf)}
                                className={`px-3 py-1 text-xs font-bold rounded transition ${
                                    timeframe === tf 
                                    ? "bg-blue-600 text-white shadow-lg" 
                                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                                }`}
                            >
                                {tf.toUpperCase()}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="bg-[#1e2329] border border-gray-800 rounded-xl p-4 h-[500px]">
                    {loading ? (
                        <div className="h-full flex items-center justify-center text-gray-500 animate-pulse">
                            Loading Analysis...
                        </div>
                    ) : (
                        // Check console log 3 to ensure data is passed here
                        <ChartSection data={techData} symbol={selectedSymbol} />
                    )}
                </div>
             </>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
