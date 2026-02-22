interface AudioVisualizerProps {
  isActive: boolean;
  audioLevel: number;
}

export function AudioVisualizer({ isActive, audioLevel }: AudioVisualizerProps) {
  if (!isActive) return null;

  return (
    <div className="flex items-center justify-center gap-1 h-8 px-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="w-1 bg-primary-500 rounded-full transition-all"
          style={{
            height: `${Math.max(4, audioLevel * (0.5 + Math.random() * 0.5) * 32)}px`,
          }}
        />
      ))}
    </div>
  );
}
