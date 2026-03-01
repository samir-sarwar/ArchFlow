const BAR_SCALES = [0.6, 1.0, 0.85, 0.95, 0.7];

interface AudioVisualizerProps {
  isActive: boolean;
  audioLevel: number;
}

export function AudioVisualizer({ isActive, audioLevel }: AudioVisualizerProps) {
  if (!isActive) return null;

  // Ensure bars are always visible while recording — minimum 8px with
  // a subtle breathing effect so the user knows recording is active
  const minHeight = 8;

  return (
    <div className="flex items-center justify-center gap-1 h-8 px-4">
      {BAR_SCALES.map((scale, i) => {
        const audioHeight = audioLevel * scale * 32;
        const showPulse = audioHeight < minHeight;

        return (
          <div
            key={i}
            className={`w-1 bg-primary-500 rounded-full transition-all duration-100 ${
              showPulse ? 'animate-pulse' : ''
            }`}
            style={{
              height: `${Math.max(minHeight, audioHeight)}px`,
              animationDelay: showPulse ? `${i * 150}ms` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}
