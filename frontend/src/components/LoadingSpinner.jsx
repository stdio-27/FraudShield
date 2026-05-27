import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ message = 'Loading data...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="relative">
        <div className="absolute inset-0 rounded-full bg-emerald-500/20 blur-xl animate-pulse" />
        <Loader2 className="w-10 h-10 text-emerald-400 animate-spin relative z-10" />
      </div>
      <p className="text-sm text-slate-400 font-medium">{message}</p>
    </div>
  );
}
