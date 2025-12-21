import React from 'react';
import { ArrowUp, ArrowDown, Activity } from 'lucide-react';

export const TechCard = ({ title, value, type, subValue }) => {
  let colorClass = "text-gray-400";
  let Icon = Activity;

  if (type === "up") { colorClass = "text-crypto-up"; Icon = ArrowUp; }
  if (type === "down") { colorClass = "text-crypto-down"; Icon = ArrowDown; }

  return (
    <div className="bg-crypto-card p-4 rounded-xl border border-gray-800 shadow-lg">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-gray-500 text-xs font-medium uppercase tracking-wider">{title}</p>
          <h3 className="text-2xl font-bold mt-1 text-crypto-text">{value}</h3>
        </div>
        <div className={`p-2 rounded-lg bg-opacity-10 ${colorClass.replace('text-', 'bg-')}`}>
          <Icon size={20} className={colorClass} />
        </div>
      </div>
      {subValue && <p className="text-xs text-gray-500 mt-2">{subValue}</p>}
    </div>
  );
};
